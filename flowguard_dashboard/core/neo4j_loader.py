# flowguard_dashboard/core/neo4j_loader.py
# ─── Classe Neo4jDataLoader : toutes les requêtes Cypher vers Neo4j ───

import logging
import pandas as pd
from neo4j import GraphDatabase

from core.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, AGENCY_ID_TO_KEY
from core.cache import cached

logger = logging.getLogger(__name__)

# Maps raw agency values (A/B/C or Agency_A etc.) to canonical keys
_AGENCY_MAP = {}
_AGENCY_MAP.update(AGENCY_ID_TO_KEY)                           # A -> Agency_A
_AGENCY_MAP.update({v: v for v in AGENCY_ID_TO_KEY.values()})  # Agency_A -> Agency_A


def _normalize_agency_col(df, col="agency"):
    """Normalize agency column to canonical keys (Agency_A, Agency_B, Agency_C).
    Also drops rows where agency is null."""
    if col not in df.columns:
        return df
    df = df.dropna(subset=[col]).copy()
    df[col] = df[col].map(_AGENCY_MAP).fillna(df[col])
    return df


class Neo4jDataLoader:
    """Singleton de chargement de données depuis Neo4j."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._driver = None
        return cls._instance

    def _get_driver(self):
        if self._driver is None:
            try:
                self._driver = GraphDatabase.driver(
                    NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
                )
            except Exception as e:
                logger.error(f"Erreur connexion Neo4j: {e}")
                return None
        return self._driver

    def _run_query(self, query, parameters=None):
        """Exécute une requête Cypher et retourne une liste de dicts."""
        driver = self._get_driver()
        if driver is None:
            return []
        try:
            with driver.session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Erreur requête Neo4j: {e}")
            return []

    def check_connection(self):
        """Vérifie la connexion Neo4j. Retourne True si OK."""
        driver = self._get_driver()
        if driver is None:
            return False
        try:
            with driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception:
            return False

    # ─────────────────────────────────────────────
    # KPIs
    # ─────────────────────────────────────────────
    @cached(ttl=8)
    def get_kpis(self):
        query = """
        CALL {
            MATCH (t:Transaction) RETURN count(t) AS total_txn
        }
        CALL {
            MATCH (a:Alert) RETURN count(a) AS total_alerts
        }
        CALL {
            MATCH (t:Transaction)
            RETURN CASE WHEN count(t) = 0 THEN 0
                        ELSE toFloat(sum(CASE WHEN t.is_fraud = true OR t.is_fraud = 1 THEN 1 ELSE 0 END)) / count(t)
                   END AS global_fraud_rate
        }
        CALL {
            MATCH (fr:FederatedRound) RETURN count(fr) AS total_fl_rounds
        }
        CALL {
            MATCH (a:Alert) RETURN avg(a.score) AS avg_score
        }
        CALL {
            MATCH (ag:Agency) RETURN count(ag) AS total_agencies
        }
        RETURN total_txn, total_alerts, global_fraud_rate,
               total_fl_rounds, avg_score, total_agencies
        """
        records = self._run_query(query)
        if not records:
            return pd.DataFrame()
        return pd.DataFrame(records)

    # ─────────────────────────────────────────────
    # Transactions timeseries (24h)
    # ─────────────────────────────────────────────
    @cached(ttl=8)
    def get_transaction_timeseries(self):
        query = """
        MATCH (t:Transaction)
        WHERE t.agency IS NOT NULL AND t.hour_of_day IS NOT NULL
        RETURN t.hour_of_day AS hour_of_day, t.agency AS agency, count(*) AS cnt
        ORDER BY hour_of_day
        """
        records = self._run_query(query)
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        return _normalize_agency_col(df)

    # ─────────────────────────────────────────────
    # Alertes récentes
    # ─────────────────────────────────────────────
    @cached(ttl=8)
    def get_recent_alerts(self, limit=100):
        query = """
        MATCH (t:Transaction)-[:TRIGGERED]->(a:Alert)
        RETURN a.alert_id AS alert_id,
               a.agency AS agency,
               a.transaction_id AS transaction_id,
               a.score AS score,
               a.threshold AS threshold,
               t.merchant_category AS merchant_category,
               a.timestamp AS timestamp,
               a.created_at AS created_at
        ORDER BY a.created_at DESC
        LIMIT $limit
        """
        records = self._run_query(query, {"limit": limit})
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df = _normalize_agency_col(df)
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df

    # ─────────────────────────────────────────────
    # Alertes par minute (dernière heure)
    # ─────────────────────────────────────────────
    @cached(ttl=8)
    def get_alerts_per_minute(self, minutes=60):
        query = """
        MATCH (a:Alert)
        WHERE a.agency IS NOT NULL
        WITH a,
             substring(toString(a.created_at), 0, 16) AS minute_bucket
        RETURN minute_bucket, a.agency AS agency, count(*) AS cnt
        ORDER BY minute_bucket
        """
        records = self._run_query(query)
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df = _normalize_agency_col(df)
        if "minute_bucket" in df.columns:
            df["minute_bucket"] = pd.to_datetime(df["minute_bucket"], errors="coerce")
        return df

    # ─────────────────────────────────────────────
    # Distribution des scores d'alerte
    # ─────────────────────────────────────────────
    @cached(ttl=8)
    def get_score_distribution(self):
        query = """
        MATCH (a:Alert)
        WHERE a.score IS NOT NULL AND a.agency IS NOT NULL
        RETURN a.score AS score, a.agency AS agency
        ORDER BY a.score
        """
        records = self._run_query(query)
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        return _normalize_agency_col(df)

    # ─────────────────────────────────────────────
    # Historique des modèles
    # ─────────────────────────────────────────────
    @cached(ttl=8)
    def get_models_history(self):
        query = """
        MATCH (m:Model)
        WHERE m.agency IS NOT NULL AND m.version IS NOT NULL
        RETURN m.model_id AS model_id,
               m.agency AS agency,
               m.version AS version,
               m.created_at AS created_at,
               m.train_samples AS train_samples,
               m.threshold AS threshold,
               m.accuracy AS accuracy,
               m.precision AS model_precision,
               m.recall AS recall,
               m.f1 AS f1,
               m.fraud_rate AS fraud_rate,
               m.artifact_path AS artifact_path,
               m.last_trained_at AS last_trained_at
        ORDER BY m.agency, m.version
        """
        records = self._run_query(query)
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df = _normalize_agency_col(df)
        for col in ["created_at", "last_trained_at"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df

    # ─────────────────────────────────────────────
    # Dernière version de chaque agence
    # ─────────────────────────────────────────────
    @cached(ttl=8)
    def get_latest_model_per_agency(self):
        query = """
        MATCH (m:Model)
        WHERE m.agency IS NOT NULL AND m.version IS NOT NULL
        WITH m.agency AS agency, max(m.version) AS max_version
        MATCH (m2:Model {agency: agency, version: max_version})
        RETURN m2.model_id AS model_id,
               m2.agency AS agency,
               m2.version AS version,
               m2.created_at AS created_at,
               m2.train_samples AS train_samples,
               m2.threshold AS threshold,
               m2.accuracy AS accuracy,
               m2.precision AS model_precision,
               m2.recall AS recall,
               m2.f1 AS f1,
               m2.fraud_rate AS fraud_rate,
               m2.artifact_path AS artifact_path,
               m2.last_trained_at AS last_trained_at
        ORDER BY agency
        """
        records = self._run_query(query)
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df = _normalize_agency_col(df)
        for col in ["created_at", "last_trained_at"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df

    # ─────────────────────────────────────────────
    # Rounds de Federated Learning
    # ─────────────────────────────────────────────
    @cached(ttl=8)
    def get_federated_rounds(self):
        query = """
        MATCH (fr:FederatedRound)
        RETURN fr.round_id AS round_id,
               fr.created_at AS created_at,
               fr.global_version AS global_version,
               fr.aggregated_agencies AS aggregated_agencies,
               fr.base_local_versions AS base_local_versions,
               fr.accuracy AS accuracy,
               fr.precision AS fl_precision,
               fr.recall AS recall,
               fr.f1 AS f1,
               fr.fraud_rate AS fraud_rate,
               fr.artifact_path AS artifact_path
        ORDER BY fr.global_version
        """
        records = self._run_query(query)
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        return df

    # ─────────────────────────────────────────────
    # Transactions filtrées
    # ─────────────────────────────────────────────
    @cached(ttl=8)
    def get_transactions_filtered(self, agency=None, is_fraud=None, is_online=None,
                                   is_foreign=None, amount_min=None, amount_max=None,
                                   limit=200):
        conditions = []
        params = {"limit": limit}

        if agency is not None and agency != "All":
            # Support both "Agency_A" and "A" in Neo4j
            from core.config import AGENCY_KEY_TO_ID
            short = AGENCY_KEY_TO_ID.get(agency, agency)
            conditions.append("(t.agency = $agency OR t.agency = $agency_short)")
            params["agency"] = agency
            params["agency_short"] = short
        if is_fraud is not None and is_fraud != "All":
            val = True if is_fraud == "Fraude" else False
            conditions.append("t.is_fraud = $is_fraud")
            params["is_fraud"] = val
        if is_online is not None and is_online != "All":
            val = True if is_online == "Oui" else False
            conditions.append("t.is_online = $is_online")
            params["is_online"] = val
        if is_foreign is not None and is_foreign != "All":
            val = True if is_foreign == "Oui" else False
            conditions.append("t.is_foreign = $is_foreign")
            params["is_foreign"] = val
        if amount_min is not None:
            conditions.append("t.amount >= $amount_min")
            params["amount_min"] = float(amount_min)
        if amount_max is not None:
            conditions.append("t.amount <= $amount_max")
            params["amount_max"] = float(amount_max)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
        MATCH (t:Transaction)
        {where_clause}
        RETURN t.transaction_id AS transaction_id,
               t.agency AS agency,
               t.amount AS amount,
               t.merchant_category AS merchant_category,
               t.location AS location,
               t.hour_of_day AS hour_of_day,
               t.day_of_week AS day_of_week,
               t.is_online AS is_online,
               t.is_foreign AS is_foreign,
               t.score AS score,
               t.prediction AS prediction,
               t.is_fraud AS is_fraud,
               t.timestamp AS timestamp,
               t.created_at AS created_at,
               t.model_version AS model_version
        ORDER BY t.created_at DESC
        LIMIT $limit
        """
        records = self._run_query(query, params)
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df = _normalize_agency_col(df)
        for col in ["timestamp", "created_at"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df

    # ─────────────────────────────────────────────
    # Heatmap : count par (hour, day_of_week)
    # ─────────────────────────────────────────────
    @cached(ttl=8)
    def get_heatmap_data(self):
        query = """
        MATCH (t:Transaction)
        RETURN t.hour_of_day AS hour_of_day,
               t.day_of_week AS day_of_week,
               count(*) AS cnt
        ORDER BY day_of_week, hour_of_day
        """
        records = self._run_query(query)
        if not records:
            return pd.DataFrame()
        return pd.DataFrame(records)

    # ─────────────────────────────────────────────
    # Boxplot montants
    # ─────────────────────────────────────────────
    @cached(ttl=8)
    def get_amount_boxplot(self):
        query = """
        MATCH (t:Transaction)
        WHERE t.amount IS NOT NULL AND t.agency IS NOT NULL AND t.is_fraud IS NOT NULL
        RETURN t.amount AS amount, t.agency AS agency, t.is_fraud AS is_fraud
        ORDER BY t.created_at DESC
        LIMIT 1000
        """
        records = self._run_query(query)
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        return _normalize_agency_col(df)

    # ─────────────────────────────────────────────
    # Top 10 catégories marchands
    # ─────────────────────────────────────────────
    @cached(ttl=8)
    def get_top_merchant_categories(self):
        query = """
        MATCH (t:Transaction)
        WITH t.merchant_category AS category,
             count(*) AS txn_count,
             toFloat(sum(CASE WHEN t.is_fraud = true OR t.is_fraud = 1 THEN 1 ELSE 0 END)) / count(*) AS fraud_rate
        RETURN category, txn_count, fraud_rate
        ORDER BY txn_count DESC
        LIMIT 10
        """
        records = self._run_query(query)
        if not records:
            return pd.DataFrame()
        return pd.DataFrame(records)

    # ─────────────────────────────────────────────
    # Scatter : score vs montant
    # ─────────────────────────────────────────────
    @cached(ttl=8)
    def get_scatter_score_amount(self):
        query = """
        MATCH (t:Transaction)
        WHERE t.score IS NOT NULL AND t.amount IS NOT NULL AND t.agency IS NOT NULL
        RETURN t.score AS score,
               t.amount AS amount,
               t.agency AS agency,
               t.transaction_id AS transaction_id
        ORDER BY t.created_at DESC
        LIMIT 500
        """
        records = self._run_query(query)
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        return _normalize_agency_col(df)

    def close(self):
        """Ferme la connexion Neo4j."""
        if self._driver:
            self._driver.close()
            self._driver = None


# ─── Instance globale singleton ───
loader = Neo4jDataLoader()
