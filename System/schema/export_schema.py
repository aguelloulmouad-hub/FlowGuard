"""
Export Schema - Génère neo4j_schema.json basé sur le vrai schéma utilisé dans neo4j_writer.py
"""

import logging
import json
from pathlib import Path
import config

logger = logging.getLogger(__name__)


def export_schema():
    """
    Générer et exporter le schéma Neo4j au format JSON.
    
    Le schéma est basé sur les noeuds et relations utilisés dans neo4j_writer.py
    """
    
    schema = {
        "nodes": {
            "Transaction": {
                "description": "Représente une transaction financière",
                "properties": [
                    {"name": "transaction_id", "type": "string", "required": True, "unique": True},
                    {"name": "agency", "type": "string", "required": True},
                    {"name": "amount", "type": "float", "required": True},
                    {"name": "merchant_category", "type": "string", "required": True},
                    {"name": "location", "type": "string", "required": True},
                    {"name": "timestamp", "type": "string", "required": True},
                    {"name": "is_foreign", "type": "boolean", "required": True},
                    {"name": "is_online", "type": "boolean", "required": True},
                    {"name": "hour_of_day", "type": "integer", "required": True},
                    {"name": "day_of_week", "type": "integer", "required": True},
                    {"name": "is_fraud", "type": "boolean", "required": True},
                    {"name": "score", "type": "float", "required": False},
                    {"name": "prediction", "type": "integer", "required": False},
                    {"name": "model_version", "type": "integer", "required": False},
                    {"name": "created_at", "type": "string", "required": True}
                ]
            },
            "Alert": {
                "description": "Alerte de fraude générée pour une transaction",
                "properties": [
                    {"name": "alert_id", "type": "string", "required": True, "unique": True},
                    {"name": "transaction_id", "type": "string", "required": True},
                    {"name": "agency", "type": "string", "required": True},
                    {"name": "score", "type": "float", "required": True},
                    {"name": "threshold", "type": "float", "required": True},
                    {"name": "timestamp", "type": "string", "required": True},
                    {"name": "created_at", "type": "string", "required": True}
                ]
            },
            "Agency": {
                "description": "Agence financière",
                "properties": [
                    {"name": "agency_id", "type": "string", "required": True, "unique": True},
                    {"name": "name", "type": "string", "required": True}
                ]
            },
            "Model": {
                "description": "Modèle ML local par agence",
                "properties": [
                    {"name": "model_id", "type": "string", "required": True, "unique": True},
                    {"name": "agency", "type": "string", "required": True},
                    {"name": "version", "type": "integer", "required": True},
                    {"name": "created_at", "type": "string", "required": True},
                    {"name": "train_samples", "type": "integer", "required": True},
                    {"name": "threshold", "type": "float", "required": True},
                    {"name": "accuracy", "type": "float", "required": False},
                    {"name": "precision", "type": "float", "required": False},
                    {"name": "recall", "type": "float", "required": False},
                    {"name": "f1", "type": "float", "required": False},
                    {"name": "fraud_rate", "type": "float", "required": False},
                    {"name": "artifact_path", "type": "string", "required": True},
                    {"name": "last_trained_at", "type": "string", "required": False}
                ]
            },
            "FederatedRound": {
                "description": "Round d'agrégation de Federated Learning",
                "properties": [
                    {"name": "round_id", "type": "string", "required": True, "unique": True},
                    {"name": "created_at", "type": "string", "required": True},
                    {"name": "global_version", "type": "integer", "required": True},
                    {"name": "aggregated_agencies", "type": "array", "required": True},
                    {"name": "base_local_versions", "type": "object", "required": True},
                    {"name": "accuracy", "type": "float", "required": False},
                    {"name": "precision", "type": "float", "required": False},
                    {"name": "recall", "type": "float", "required": False},
                    {"name": "f1", "type": "float", "required": False},
                    {"name": "fraud_rate", "type": "float", "required": False},
                    {"name": "artifact_path", "type": "string", "required": True}
                ]
            },
        },
        "relationships": [
            {
                "from": "Transaction",
                "to": "Agency",
                "type": "BELONGS_TO",
                "description": "Une transaction appartient à une agence",
                "properties": []
            },
            {
                "from": "Transaction",
                "to": "Alert",
                "type": "TRIGGERED",
                "description": "Une transaction a déclenché une alerte",
                "properties": []
            },
            {
                "from": "Transaction",
                "to": "Model",
                "type": "SCORED_BY",
                "description": "Une transaction a été évaluée par un modèle",
                "properties": []
            },
            {
                "from": "Model",
                "to": "Agency",
                "type": "OWNED_BY",
                "description": "Un modèle appartient à une agence",
                "properties": []
            },
            {
                "from": "FederatedRound",
                "to": "Model",
                "type": "AGGREGATES",
                "description": "Un round FL agrège les poids de plusieurs modèles locaux",
                "properties": []
            }
        ],
        "dash_queries": {
            "recent_transactions": "MATCH (t:Transaction) RETURN t ORDER BY t.created_at DESC LIMIT 100",
            "active_alerts": "MATCH (a:Alert) RETURN a ORDER BY a.timestamp DESC LIMIT 50",
            "model_versions": "MATCH (m:Model) RETURN m ORDER BY m.created_at DESC",
            "federated_rounds": "MATCH (f:FederatedRound) RETURN f ORDER BY f.created_at DESC",
            "fraud_rate_by_agency": "MATCH (m:Model)-[:OWNED_BY]->(ag:Agency) RETURN ag.name, m.fraud_rate, m.version, m.created_at ORDER BY m.created_at DESC",
            "high_score_alerts": "MATCH (a:Alert) WHERE a.score > 0.8 RETURN a ORDER BY a.score DESC LIMIT 20",
            "agency_stats": "MATCH (t:Transaction)-[:BELONGS_TO]->(ag:Agency) RETURN ag.name, COUNT(t) AS transaction_count, SUM(CASE WHEN t.is_fraud=true THEN 1 ELSE 0 END) AS fraud_count",
            "model_performance": "MATCH (m:Model) RETURN m.agency, m.version, m.accuracy, m.precision, m.recall, m.f1 ORDER BY m.created_at DESC LIMIT 50"
        }
    }
    
    # Créer le répertoire schema s'il n'existe pas
    schema_dir = Path(config.SCHEMA_OUTPUT).parent
    schema_dir.mkdir(parents=True, exist_ok=True)
    
    # Écrire le fichier JSON
    output_path = Path(config.SCHEMA_OUTPUT)
    with open(output_path, 'w') as f:
        json.dump(schema, f, indent=2)
    
    logger.info(f"Schéma Neo4j exporté vers {output_path}")
    return schema


if __name__ == "__main__":
    # Configuration du logging
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format=config.LOG_FORMAT
    )
    
    export_schema()
    print(f"Schéma exporté vers {config.SCHEMA_OUTPUT}")
