"""
Neo4j Writer - Gère toutes les écritures Neo4j pour FlowGuard.
Transactions, Alertes, Modèles, Rounds FL.
"""

import logging
import json
from datetime import datetime
from neo4j import GraphDatabase
import config

logger = logging.getLogger(__name__)


class Neo4jWriter:
    """Classe pour interagir avec Neo4j de manière thread-safe."""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
            connection_timeout=config.NEO4J_CONNECTION_TIMEOUT
        )
        self._init_schema()
    
    def close(self):
        """Fermer la connexion au driver Neo4j."""
        self.driver.close()
    
    def _init_schema(self):
        """Initialiser les index et constraints Neo4j."""
        with self.driver.session() as session:
            try:
                # Créer les constraints d'unicité
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:Transaction) REQUIRE t.transaction_id IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Alert) REQUIRE a.alert_id IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (ag:Agency) REQUIRE ag.agency_id IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Model) REQUIRE m.model_id IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (f:FederatedRound) REQUIRE f.round_id IS UNIQUE")
                
                # Créer les index de performance
                session.run("CREATE INDEX IF NOT EXISTS FOR (t:Transaction) ON (t.timestamp)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (t:Transaction) ON (t.agency)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (a:Alert) ON (a.timestamp)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (m:Model) ON (m.agency)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (f:FederatedRound) ON (f.created_at)")
                
                logger.info("Schéma Neo4j initialisé avec succès")
            except Exception as e:
                logger.error(f"Erreur lors de l'initialisation du schéma Neo4j: {e}")
    
    def create_agency(self, agency_id: str, name: str):
        """Créer ou mettre à jour une agence."""
        with self.driver.session() as session:
            try:
                session.run(
                    """
                    MERGE (ag:Agency {agency_id: $agency_id})
                    SET ag.name = $name
                    """,
                    agency_id=agency_id,
                    name=name
                )
                logger.debug(f"Agence {agency_id} créée/mise à jour")
            except Exception as e:
                logger.error(f"Erreur lors de la création de l'agence {agency_id}: {e}")
    
    def write_transaction(self, txn_data: dict):
        """
        Écrire une transaction dans Neo4j.
        
        Args:
            txn_data: dict avec les champs Transaction
        """
        with self.driver.session() as session:
            try:
                session.run(
                    """
                    MERGE (t:Transaction {transaction_id: $transaction_id})
                    SET 
                        t.agency = $agency,
                        t.amount = $amount,
                        t.merchant_category = $merchant_category,
                        t.location = $location,
                        t.timestamp = $timestamp,
                        t.is_foreign = $is_foreign,
                        t.is_online = $is_online,
                        t.hour_of_day = $hour_of_day,
                        t.day_of_week = $day_of_week,
                        t.is_fraud = $is_fraud,
                        t.score = $score,
                        t.prediction = $prediction,
                        t.model_version = $model_version,
                        t.created_at = $created_at
                    WITH t
                    MATCH (ag:Agency {agency_id: $agency})
                    MERGE (t)-[:BELONGS_TO]->(ag)
                    MERGE (m:Model {model_id: $model_id})
                    MERGE (t)-[:SCORED_BY]->(m)
                    """,
                    transaction_id=txn_data.get("transaction_id"),
                    agency=txn_data.get("agency"),
                    amount=txn_data.get("amount"),
                    merchant_category=txn_data.get("merchant_category"),
                    location=txn_data.get("location"),
                    timestamp=txn_data.get("timestamp"),
                    is_foreign=txn_data.get("is_foreign"),
                    is_online=txn_data.get("is_online"),
                    hour_of_day=txn_data.get("hour_of_day"),
                    day_of_week=txn_data.get("day_of_week"),
                    is_fraud=txn_data.get("is_fraud"),
                    score=txn_data.get("score"),
                    prediction=txn_data.get("prediction"),
                    model_version=txn_data.get("model_version"),
                    created_at=txn_data.get("created_at", datetime.utcnow().isoformat()),
                    model_id=f"{txn_data.get('agency')}_v{txn_data.get('model_version', 1)}"
                )
                logger.debug(f"Transaction {txn_data.get('transaction_id')} écrite dans Neo4j")
            except Exception as e:
                logger.error(f"Erreur lors de l'écriture de la transaction: {e}")
    
    def write_alert(self, alert_data: dict):
        """
        Écrire une alerte dans Neo4j.
        
        Args:
            alert_data: dict avec alert_id, transaction_id, agency, score, threshold, timestamp
        """
        with self.driver.session() as session:
            try:
                session.run(
                    """
                    MERGE (a:Alert {alert_id: $alert_id})
                    SET 
                        a.transaction_id = $transaction_id,
                        a.agency = $agency,
                        a.score = $score,
                        a.threshold = $threshold,
                        a.timestamp = $timestamp,
                        a.created_at = $created_at
                    WITH a
                    MATCH (t:Transaction {transaction_id: $transaction_id})
                    MERGE (t)-[:TRIGGERED]->(a)
                    """,
                    alert_id=alert_data.get("alert_id"),
                    transaction_id=alert_data.get("transaction_id"),
                    agency=alert_data.get("agency"),
                    score=alert_data.get("score"),
                    threshold=alert_data.get("threshold"),
                    timestamp=alert_data.get("timestamp"),
                    created_at=alert_data.get("created_at", datetime.utcnow().isoformat())
                )
                logger.debug(f"Alerte {alert_data.get('alert_id')} écrite dans Neo4j")
            except Exception as e:
                logger.error(f"Erreur lors de l'écriture de l'alerte: {e}")
    
    def write_model(self, model_data: dict):
        """
        Écrire ou mettre à jour un modèle local.
        
        Args:
            model_data: dict avec model_id, agency, version, train_samples, threshold, 
                       accuracy, precision, recall, f1, fraud_rate, artifact_path, last_trained_at
        """
        with self.driver.session() as session:
            try:
                session.run(
                    """
                    MERGE (m:Model {model_id: $model_id})
                    SET 
                        m.agency = $agency,
                        m.version = $version,
                        m.created_at = $created_at,
                        m.train_samples = $train_samples,
                        m.threshold = $threshold,
                        m.accuracy = $accuracy,
                        m.precision = $precision,
                        m.recall = $recall,
                        m.f1 = $f1,
                        m.fraud_rate = $fraud_rate,
                        m.artifact_path = $artifact_path,
                        m.last_trained_at = $last_trained_at
                    WITH m
                    MATCH (ag:Agency {agency_id: $agency})
                    MERGE (m)-[:OWNED_BY]->(ag)
                    """,
                    model_id=model_data.get("model_id"),
                    agency=model_data.get("agency"),
                    version=model_data.get("version"),
                    created_at=model_data.get("created_at", datetime.utcnow().isoformat()),
                    train_samples=model_data.get("train_samples"),
                    threshold=model_data.get("threshold"),
                    accuracy=model_data.get("accuracy"),
                    precision=model_data.get("precision"),
                    recall=model_data.get("recall"),
                    f1=model_data.get("f1"),
                    fraud_rate=model_data.get("fraud_rate"),
                    artifact_path=model_data.get("artifact_path"),
                    last_trained_at=model_data.get("last_trained_at", datetime.utcnow().isoformat())
                )
                logger.debug(f"Modèle {model_data.get('model_id')} écrit dans Neo4j")
            except Exception as e:
                logger.error(f"Erreur lors de l'écriture du modèle: {e}")
    
    def write_federated_round(self, round_data: dict):
        """
        Écrire un round de Federated Learning.
        
        Args:
            round_data: dict avec round_id, created_at, global_version, aggregated_agencies,
                       base_local_versions, accuracy, precision, recall, f1, fraud_rate, artifact_path
        """
        with self.driver.session() as session:
            try:
                aggregated_agencies = round_data.get("aggregated_agencies", [])
                
                # Convertir base_local_versions dict en JSON string pour Neo4j compatibility
                base_versions_dict = round_data.get("base_local_versions", {})
                base_versions_json = json.dumps(base_versions_dict)
                
                session.run(
                    """
                    MERGE (f:FederatedRound {round_id: $round_id})
                    SET 
                        f.created_at = $created_at,
                        f.global_version = $global_version,
                        f.aggregated_agencies = $aggregated_agencies,
                        f.base_local_versions = $base_local_versions,
                        f.accuracy = $accuracy,
                        f.precision = $precision,
                        f.recall = $recall,
                        f.f1 = $f1,
                        f.fraud_rate = $fraud_rate,
                        f.artifact_path = $artifact_path
                    """,
                    round_id=round_data.get("round_id"),
                    created_at=round_data.get("created_at", datetime.utcnow().isoformat()),
                    global_version=round_data.get("global_version"),
                    aggregated_agencies=aggregated_agencies,
                    base_local_versions=base_versions_json,
                    accuracy=round_data.get("accuracy"),
                    precision=round_data.get("precision"),
                    recall=round_data.get("recall"),
                    f1=round_data.get("f1"),
                    fraud_rate=round_data.get("fraud_rate"),
                    artifact_path=round_data.get("artifact_path")
                )
                
                # Créer les relations avec les modèles locaux qui ont servi à l'agrégation
                for agency, version in base_versions_dict.items():
                    model_id = f"{agency}_v{version}"
                    session.run(
                        """
                        MATCH (f:FederatedRound {round_id: $round_id})
                        MATCH (m:Model {model_id: $model_id})
                        MERGE (f)-[:AGGREGATES]->(m)
                        """,
                        round_id=round_data.get("round_id"),
                        model_id=model_id
                    )
                
                logger.debug(f"Round FL {round_data.get('round_id')} écrit dans Neo4j")
            except Exception as e:
                logger.error(f"Erreur lors de l'écriture du round FL: {e}")
