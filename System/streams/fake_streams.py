"""
Générateurs de transactions fake - 3 agences (A, B, C).
Injecte les transactions dans Kafka (transactions.raw).
"""

import logging
import json
import random
import uuid
from datetime import datetime, timedelta
from kafka import KafkaProducer
import config

logger = logging.getLogger(__name__)


class FakeStreamGenerator:
    """Générateur de transactions pour une agence."""
    
    def __init__(self, agency: str):
        self.agency = agency
        self.kafka_producer = KafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            retries=3
        )
        
        # Profils spécifiques par agence
        if agency == "A":
            # Stable, comportement classique
            self.amount_range = (20, 500)
            self.fraud_rate = 0.02
            self.merchants = ["grocery", "gas_station", "restaurant", "utilities", "healthcare"]
            self.locations = ["paris", "lyon", "marseille"]
            self.online_ratio = 0.1
            self.foreign_ratio = 0.05
            self.description = "Agency A: Stable, comportement classique"
        
        elif agency == "B":
            # Bruité, risqué
            self.amount_range = (50, 5000)
            self.fraud_rate = 0.08
            self.merchants = ["online_retail", "entertainment", "travel", "other"]
            self.locations = ["paris", "lyon", "marseille", "toulouse", "nice", "online"]
            self.online_ratio = 0.3
            self.foreign_ratio = 0.15
            self.description = "Agency B: Bruité, montants élevés, risqué"
        
        elif agency == "C":
            # Digital, fréquent, petits montants
            self.amount_range = (1, 150)
            self.fraud_rate = 0.04
            self.merchants = ["online_retail", "entertainment", "utilities"]
            self.locations = ["online", "paris"]
            self.online_ratio = 0.9
            self.foreign_ratio = 0.02
            self.description = "Agency C: Digital, fréquent, petits montants"
        
        else:
            raise ValueError(f"Agency inconnue: {agency}")
    
    def generate_transaction(self, index: int = 0) -> dict:
        """
        Générer une transaction fake.
        
        Args:
            index: index pour générer des patterns répétitifs
        
        Returns:
            dict Transaction avec is_fraud injecté par les fraud rules
        """
        now = datetime.utcnow()
        
        # Montant
        amount = random.uniform(*self.amount_range)
        
        # Timestamp (lightly shuffled pour simuler du timing réaliste)
        timestamp = (now - timedelta(seconds=random.randint(0, 60))).isoformat()
        
        # Localisation
        location = random.choice(self.locations)
        
        # Catégorie marchant
        merchant_category = random.choice(self.merchants)
        
        # Flags
        is_online = random.random() < self.online_ratio
        is_foreign = random.random() < self.foreign_ratio
        
        # Heure et jour
        hour_of_day = random.randint(0, 23)
        day_of_week = random.randint(0, 6)
        
        # Label fraude injecté par les fraud rules
        is_fraud = self._apply_fraud_rules(
            amount, hour_of_day, is_foreign, is_online, 
            location, index
        )
        
        # Construire la transaction
        transaction = {
            "transaction_id": str(uuid.uuid4()),
            "agency": self.agency,
            "amount": round(amount, 2),
            "merchant_category": merchant_category,
            "location": location,
            "timestamp": timestamp,
            "is_foreign": is_foreign,
            "is_online": is_online,
            "hour_of_day": hour_of_day,
            "day_of_week": day_of_week,
            "is_fraud": is_fraud
        }
        
        return transaction
    
    def _apply_fraud_rules(self, amount: float, hour: int, is_foreign: bool, 
                          is_online: bool, location: str, index: int) -> bool:
        """
        Appliquer les règles de fraude pour injecter des patterns réalistes.
        
        Args:
            amount: montant
            hour: heure du jour
            is_foreign: flag étranger
            is_online: flag en ligne
            location: localisation
            index: index pour patterns
        
        Returns:
            bool fraud
        """
        fraud = False
        
        # Règle 1 : Fraude basée sur le taux (aléatoire)
        if random.random() < self.fraud_rate:
            fraud = True
        
        # Règle 2 : Montants extrêmes
        if self.agency == "A" and amount > 450:
            fraud = True
        elif self.agency == "B" and amount > 4500:
            fraud = True
        elif self.agency == "C" and amount > 140:
            fraud = True
        
        # Règle 3 : Transactions nocturnes anormales
        if hour < 6 or hour > 23:
            if random.random() < 0.1:  # 10% de chance fraude la nuit
                fraud = True
        
        # Règle 4 : Étrangers
        if is_foreign and random.random() < 0.05:
            fraud = True
        
        # Règle 5 : Burst de transactions (simulé par index % 50 < 5)
        if index % 50 < 5 and index % 50 != 0:
            if random.random() < 0.08:
                fraud = True
        
        return fraud
    
    def produce_transactions(self, count: int = 100, batch_size: int = 10):
        """
        Générer et produire des transactions dans Kafka.
        
        Args:
            count: nombre de transactions à produire
            batch_size: nombre de transactions par batch (pour stats)
        """
        logger.info(f"{self.description} - Production de {count} transactions")
        
        try:
            for i in range(count):
                transaction = self.generate_transaction(i)
                
                # Produire dans Kafka
                self.kafka_producer.send(
                    config.TOPICS["raw"],
                    value=transaction
                )
                
                # Log et stats
                if (i + 1) % batch_size == 0:
                    logger.debug(f"Agency {self.agency}: {i + 1}/{count} transactions produites")
            
            # Flush pour s'assurer que tous les messages sont envoyés
            self.kafka_producer.flush()
            logger.info(f"Agency {self.agency}: {count} transactions produites avec succès")
        
        except Exception as e:
            logger.error(f"Erreur lors de la production de transactions Agency {self.agency}: {e}")
    
    def run(self, rate: int = 10, duration: int = None):
        """
        Boucle continue de production de transactions.
        
        Args:
            rate: transactions par seconde (approximatif)
            duration: durée en secondes (None = infini)
        """
        logger.info(f"Agency {self.agency}: Démarrage du stream (rate={rate} txn/s)")
        
        import time
        start_time = time.time()
        transaction_index = 0
        
        try:
            while True:
                if duration and (time.time() - start_time) > duration:
                    logger.info(f"Agency {self.agency}: Stream arrêté après {duration}s")
                    break
                
                transaction = self.generate_transaction(transaction_index)
                
                self.kafka_producer.send(
                    config.TOPICS["raw"],
                    value=transaction
                )
                
                transaction_index += 1
                
                # Throttle rate
                time.sleep(1.0 / rate)
        
        except KeyboardInterrupt:
            logger.info(f"Agency {self.agency}: Stream arrêté par l'utilisateur")
        except Exception as e:
            logger.error(f"Erreur lors de la production continue Agency {self.agency}: {e}")
        finally:
            self.kafka_producer.close()
