"""
Cleaner - Consomme transactions.raw, nettoie et produit transactions.cleaned.
Nettoyage basique : validation des champs, normalisation.
"""

import logging
import json
from kafka import KafkaConsumer, KafkaProducer
import config

logger = logging.getLogger(__name__)


class TransactionCleaner:
    """Nettoyeur de transactions Kafka."""
    
    def __init__(self):
        self.consumer = KafkaConsumer(
            config.TOPICS["raw"],
            bootstrap_servers=config.KAFKA_BOOTSTRAP,
            group_id="cleaner_group",
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            consumer_timeout_ms=config.KAFKA_CLEANER_TIMEOUT
        )
        
        self.producer = KafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            retries=3
        )
        
        self.processed_count = 0
        self.errors_count = 0
    
    def clean_transaction(self, raw_transaction: dict) -> dict:
        """
        Nettoyer une transaction brute.
        
        Args:
            raw_transaction: dict brut du topic raw
        
        Returns:
            dict nettoyé, ou None si invalide
        """
        try:
            # Valider les champs obligatoires
            required_fields = [
                "transaction_id", "agency", "amount", "merchant_category",
                "location", "timestamp", "is_foreign", "is_online",
                "hour_of_day", "day_of_week", "is_fraud"
            ]
            
            for field in required_fields:
                if field not in raw_transaction:
                    logger.warning(f"Champ manquant: {field} dans {raw_transaction.get('transaction_id')}")
                    return None
            
            # Validation des types
            cleaned = {
                "transaction_id": str(raw_transaction["transaction_id"]),
                "agency": str(raw_transaction["agency"]).upper(),
                "amount": float(raw_transaction["amount"]),
                "merchant_category": str(raw_transaction["merchant_category"]).lower(),
                "location": str(raw_transaction["location"]).lower(),
                "timestamp": str(raw_transaction["timestamp"]),
                "is_foreign": bool(raw_transaction["is_foreign"]),
                "is_online": bool(raw_transaction["is_online"]),
                "hour_of_day": int(raw_transaction["hour_of_day"]),
                "day_of_week": int(raw_transaction["day_of_week"]),
                "is_fraud": bool(raw_transaction["is_fraud"])
            }
            
            # Validations métier
            if cleaned["amount"] <= 0:
                logger.warning(f"Montant invalide: {cleaned['amount']}")
                return None
            
            if cleaned["hour_of_day"] < 0 or cleaned["hour_of_day"] > 23:
                logger.warning(f"Heure invalide: {cleaned['hour_of_day']}")
                return None
            
            if cleaned["day_of_week"] < 0 or cleaned["day_of_week"] > 6:
                logger.warning(f"Jour invalide: {cleaned['day_of_week']}")
                return None
            
            if cleaned["agency"] not in config.AGENCIES:
                logger.warning(f"Agence invalide: {cleaned['agency']}")
                return None
            
            return cleaned
        
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage: {e}")
            return None
    
    def run(self):
        """Boucle principale du cleaner."""
        logger.info("Cleaner démarré, écoute transactions.raw")
        
        try:
            for message in self.consumer:
                raw_transaction = message.value
                
                cleaned = self.clean_transaction(raw_transaction)
                
                if cleaned:
                    # Produire dans le topic cleaned
                    self.producer.send(config.TOPICS["cleaned"], value=cleaned)
                    self.processed_count += 1
                    
                    if self.processed_count % 100 == 0:
                        logger.debug(f"Cleaner: {self.processed_count} transactions traitées")
                else:
                    self.errors_count += 1
                    if self.errors_count % 100 == 0:
                        logger.warning(f"Cleaner: {self.errors_count} erreurs")
            
            logger.info("Cleaner arrêté")
        
        except KeyboardInterrupt:
            logger.info("Cleaner arrêté par l'utilisateur")
        except Exception as e:
            logger.error(f"Erreur fatale dans le cleaner: {e}")
        finally:
            self.producer.flush()
            self.consumer.close()
            self.producer.close()
