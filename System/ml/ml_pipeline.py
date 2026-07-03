"""
Pipeline ML - Orchestre les 3 modèles locaux (Agency A, B, C).
Consomme transactions.cleaned, produit dans alerts et model.updates.
"""

import logging
import json
import uuid
from datetime import datetime
from kafka import KafkaConsumer, KafkaProducer
import config
from ml.local_model import LocalModel
from storage.neo4j_writer import Neo4jWriter

logger = logging.getLogger(__name__)


class MLPipeline:
    """
    Pipeline ML qui gère les 3 modèles locaux.
    - Consomme transactions.cleaned
    - Fait des prédictions
    - Génère des alertes
    - Réentraîne les modèles
    - Écrit dans Neo4j
    """
    
    def __init__(self):
        self.consumer = KafkaConsumer(
            config.TOPICS["cleaned"],
            bootstrap_servers=config.KAFKA_BOOTSTRAP,
            group_id="ml_pipeline_group",
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            #consumer_timeout_ms=config.KAFKA_ML_PIPELINE_TIMEOUT
        )
        
        self.alerts_producer = KafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            retries=3
        )
        
        self.updates_producer = KafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            retries=3
        )
        
        # Modèles locaux pour chaque agence
        self.models = {agency: LocalModel(agency) for agency in config.AGENCIES}
        
        # Neo4j writer
        self.neo4j_writer = Neo4jWriter()
        
        # Initialiser les agences dans Neo4j
        for agency in config.AGENCIES:
            self.neo4j_writer.create_agency(agency, f"Agency {agency}")
        
        # Compteurs de transactions par agence
        self.transaction_counts = {agency: 0 for agency in config.AGENCIES}
        
        # Compteurs globaux
        self.total_processed = 0
        self.total_alerts = 0
    
    def process_transaction(self, transaction: dict):
        """
        Traiter une transaction : prédiction, alerte, Neo4j.
        
        Args:
            transaction: dict cleaned
        """
        agency = transaction.get("agency")
        
        if agency not in self.models:
            logger.warning(f"Agence inconnue: {agency}")
            return
        
        try:
            # Ajouter au buffer du modèle
            self.models[agency].add_transaction(transaction)
            self.transaction_counts[agency] += 1
            self.total_processed += 1
            
            # Faire une prédiction
            score = self.models[agency].predict(transaction)
            prediction = None
            
            if score is not None:
                prediction = 1 if score > self.models[agency].threshold else 0
            
            # Créer l'enregistrement pour Neo4j
            txn_record = transaction.copy()
            txn_record["score"] = score
            txn_record["prediction"] = prediction
            txn_record["model_version"] = self.models[agency].version if self.models[agency].is_trained else 0
            txn_record["created_at"] = datetime.utcnow().isoformat()
            
            # Écrire dans Neo4j
            self.neo4j_writer.write_transaction(txn_record)
            
            # Générer une alerte si nécessaire
            if score is not None and score > self.models[agency].threshold:
                alert_id = str(uuid.uuid4())
                alert = {
                    "alert_id": alert_id,
                    "transaction_id": transaction.get("transaction_id"),
                    "agency": agency,
                    "score": score,
                    "threshold": self.models[agency].threshold,
                    "timestamp": datetime.utcnow().isoformat(),
                    "created_at": datetime.utcnow().isoformat()
                }
                
                # Produire l'alerte dans Kafka
                self.alerts_producer.send(config.TOPICS["alerts"], value=alert)
                
                # Écrire l'alerte dans Neo4j
                self.neo4j_writer.write_alert(alert)
                
                self.total_alerts += 1
                logger.info(f"ALERTE: Transaction {transaction.get('transaction_id')} - Score {score:.3f}")
            
            # Vérifier s'il faut réentraîner
            if self.transaction_counts[agency] % config.RETRAIN_EVERY == 0 and \
               self.transaction_counts[agency] >= config.BOOTSTRAP_MIN:
                logger.info(f"Agency {agency}: Réentraînement déclenchement ({self.transaction_counts[agency]} transactions)")
                
                if self.models[agency].train():
                    # Publier la mise à jour du modèle
                    #update = {
                    #    "agency": agency,
                    #    "version": self.models[agency].version,
                    #    "timestamp": datetime.utcnow().isoformat()
                    #}
                    update = {
                        "agency": agency,
                        "version": self.models[agency].version,
                        "train_samples": self.models[agency].train_samples,
                        "artifact_path": str(
                            self.models[agency].artifact_dir /
                            f"model_v{self.models[agency].version}.pkl"
                        ),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    self.updates_producer.send(config.TOPICS["model_updates"], value=update)
                    
                    # Écrire le modèle dans Neo4j
                    model_data = {
                        "model_id": f"{agency}_v{self.models[agency].version}",
                        "agency": agency,
                        "version": self.models[agency].version,
                        "created_at": datetime.utcnow().isoformat(),
                        "train_samples": self.models[agency].train_samples,
                        "threshold": self.models[agency].threshold,
                        "accuracy": self.models[agency].accuracy,
                        "precision": self.models[agency].precision,
                        "recall": self.models[agency].recall,
                        "f1": self.models[agency].f1,
                        "fraud_rate": self.models[agency].fraud_rate,
                        "artifact_path": str(self.models[agency].artifact_dir / f"model_v{self.models[agency].version}.pkl"),
                        "last_trained_at": self.models[agency].last_trained_at
                    }
                    
                    self.neo4j_writer.write_model(model_data)
            
            if self.total_processed % 100 == 0:
                logger.debug(
                    f"Pipeline ML: {self.total_processed} transactions traitées, "
                    f"{self.total_alerts} alertes générées"
                )
        
        except Exception as e:
            logger.error(f"Erreur lors du traitement de la transaction: {e}")
    
    def run(self):
        """Boucle principale du pipeline ML."""
        logger.info("Pipeline ML démarré, écoute transactions.cleaned")
        
        try:
            for message in self.consumer:
                transaction = message.value
                self.process_transaction(transaction)
            
            logger.info("Pipeline ML arrêté")
        
        except KeyboardInterrupt:
            logger.info("Pipeline ML arrêté par l'utilisateur")
        except Exception as e:
            logger.error(f"Erreur fatale dans le pipeline ML: {e}")
        finally:
            self.alerts_producer.flush()
            self.updates_producer.flush()
            self.consumer.close()
            self.alerts_producer.close()
            self.updates_producer.close()
            self.neo4j_writer.close()
