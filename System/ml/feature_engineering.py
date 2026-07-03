"""
Feature Engineering - Transformation de transactions en vecteurs de features.
Compatible avec sklearn et les modèles ML locaux.
"""

import logging
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

# Features constants
AMOUNT_MIN = 1.0
AMOUNT_MAX = 10000.0
MERCHANTS = ["grocery", "gas_station", "restaurant", "online_retail", "entertainment", 
             "healthcare", "travel", "utilities", "other"]
LOCATIONS_COMMON = ["paris", "lyon", "marseille", "toulouse", "nice", "online"]


class FeatureEngineer:
    """Extraction et normalisation des features d'une transaction."""
    
    def __init__(self):
        self.feature_names = [
            "amount_normalized",      # 0: Montant normalisé
            "hour_normalized",        # 1: Heure du jour (0-23)
            "day_normalized",         # 2: Jour de la semaine (0-6)
            "is_foreign",             # 3: Booléen
            "is_online",              # 4: Booléen
            "merchant_grocery",       # 5-13: One-hot encoding merchants (9 features)
            "merchant_gas_station",
            "merchant_restaurant",
            "merchant_online_retail",
            "merchant_entertainment",
            "merchant_healthcare",
            "merchant_travel",
            "merchant_utilities",
            "merchant_other",
            "location_paris",         # 14-19: One-hot encoding locations (6 features)
            "location_lyon",
            "location_marseille",
            "location_toulouse",
            "location_nice",
            "location_online"
        ]
        self.n_features = len(self.feature_names)
    
    def transform(self, transaction: dict) -> np.ndarray:
        """
        Transformer une transaction en vecteur de features numpy.
        
        Args:
            transaction: dict avec les champs Transaction (amount, hour_of_day, 
                        day_of_week, is_foreign, is_online, merchant_category, location)
        
        Returns:
            numpy array de dimension (n_features,) sans NaN ni Inf
        """
        features = []
        
        try:
            # 1. Normalisation du montant (log scale)
            amount = float(transaction.get("amount", 50.0))
            amount_normalized = np.log1p(amount) / np.log1p(AMOUNT_MAX)
            amount_normalized = np.clip(amount_normalized, 0.0, 1.0)
            features.append(amount_normalized)
            
            # 2. Heure du jour (0-23) normalisée
            hour = int(transaction.get("hour_of_day", 12))
            hour_normalized = hour / 24.0
            features.append(hour_normalized)
            
            # 3. Jour de la semaine (0-6) normalisé
            day = int(transaction.get("day_of_week", 0))
            day_normalized = day / 7.0
            features.append(day_normalized)
            
            # 4. Flag étranger (booléen)
            is_foreign = float(transaction.get("is_foreign", False))
            features.append(is_foreign)
            
            # 5. Flag en ligne (booléen)
            is_online = float(transaction.get("is_online", False))
            features.append(is_online)
            
            # 6-14. One-hot encoding des catégories marchands
            merchant = transaction.get("merchant_category", "other").lower()
            for m in MERCHANTS:
                features.append(1.0 if merchant == m else 0.0)
            
            # 15-20. One-hot encoding des localisations
            location = transaction.get("location", "online").lower()
            common_locations = ["paris", "lyon", "marseille", "toulouse", "nice", "online"]
            for loc in common_locations:
                features.append(1.0 if location == loc else 0.0)
            
            # Convertir en numpy array
            feature_array = np.array(features, dtype=np.float32)
            
            # Vérification : aucun NaN ni Inf
            if np.isnan(feature_array).any() or np.isinf(feature_array).any():
                logger.warning(f"Features contiennent des NaN ou Inf: {transaction}")
                feature_array = np.nan_to_num(feature_array, nan=0.0, posinf=1.0, neginf=0.0)
            
            # Vérification de la dimension
            assert feature_array.shape == (self.n_features,), \
                f"Mauvaise dimension: {feature_array.shape} != {(self.n_features,)}"
            
            return feature_array
        
        except Exception as e:
            logger.error(f"Erreur dans feature_engineering: {e}")
            # Retourner un vecteur de zéros en cas d'erreur
            return np.zeros(self.n_features, dtype=np.float32)
    
    def batch_transform(self, transactions: list) -> np.ndarray:
        """
        Transformer un batch de transactions en matrice de features.
        
        Args:
            transactions: liste de dict
        
        Returns:
            matrice numpy de dimension (n_transactions, n_features)
        """
        features_list = [self.transform(txn) for txn in transactions]
        return np.array(features_list, dtype=np.float32)
