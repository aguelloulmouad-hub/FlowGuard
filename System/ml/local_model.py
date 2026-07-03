"""
Modèle Local ML - SGDClassifier avec buffer glissant et versionnage.
Compatible avec Federated Learning (FedAvg).
"""

import logging
import numpy as np
import pickle
import json
from collections import deque
from datetime import datetime
from sklearn.linear_model import SGDClassifier
from pathlib import Path
import config
from ml.feature_engineering import FeatureEngineer

logger = logging.getLogger(__name__)


class LocalModel:
    """
    Modèle ML local par agence.
    - SGDClassifier (loss='log_loss')
    - Buffer glissant de 5000 transactions
    - Versionnage automatique
    - Prédictions en temps réel
    """
    
    def __init__(self, agency: str):
        self.agency = agency
        self.feature_engineer = FeatureEngineer()
        
        # Modèle sklearn
        self.model = None
        self.version = 0
        self.is_trained = False
        
        # Buffer glissant
        self.buffer = deque(maxlen=config.BUFFER_SIZE)
        self.transaction_count = 0
        
        # Métadonnées
        self.creation_time = datetime.utcnow().isoformat()
        self.last_trained_at = None
        self.train_samples = 0
        self.threshold = config.PREDICTION_THRESHOLD
        
        # Métriques de performance
        self.accuracy = None
        self.precision = None
        self.recall = None
        self.f1 = None
        self.fraud_rate = None
        
        # Chemin d'artefacts
        self.artifact_dir = Path(config.MODEL_DIR) / f"agency_{agency.lower()}"
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        
        # Charger le dernier modèle s'il existe
        self._load_latest_model()
    
    def _load_latest_model(self):
        """Charger le dernier modèle et ses métadonnées si présent."""
        try:
            # Chercher le numéro de version le plus élevé
            model_files = list(self.artifact_dir.glob("model_v*.pkl"))
            if model_files:
                versions = [int(f.stem.split('_v')[-1]) for f in model_files]
                latest_version = max(versions)
                
                model_path = self.artifact_dir / f"model_v{latest_version}.pkl"
                meta_path = self.artifact_dir / f"meta_v{latest_version}.json"
                
                with open(model_path, 'rb') as f:
                    self.model = pickle.load(f)
                
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
                    self.version = meta['version']
                    self.is_trained = True
                    self.train_samples = meta.get('train_samples', 0)
                    self.last_trained_at = meta.get('last_trained_at')
                    self.accuracy = meta.get('accuracy')
                    self.precision = meta.get('precision')
                    self.recall = meta.get('recall')
                    self.f1 = meta.get('f1')
                    self.fraud_rate = meta.get('fraud_rate')
                    self.threshold = meta.get('threshold', config.PREDICTION_THRESHOLD)
                
                logger.info(f"Agency {self.agency}: Modèle v{self.version} chargé (samples={self.train_samples})")
        except Exception as e:
            logger.debug(f"Aucun modèle antérieur pour agency {self.agency}: {e}")
            self.model = None
            self.is_trained = False
    
    def add_transaction(self, transaction: dict):
        """
        Ajouter une transaction au buffer.
        
        Args:
            transaction: dict avec les champs Transaction incluant is_fraud
        """
        self.buffer.append(transaction)
        self.transaction_count += 1
    
    def predict(self, transaction: dict) -> float:
        """
        Faire une prédiction sur une transaction.
        
        Args:
            transaction: dict Transaction
        
        Returns:
            float entre 0 et 1 (probabilité de fraude), ou None si pas assez de données
        """
        # Bootstrap: pas de prédiction avant 1000 transactions
        if self.transaction_count < config.BOOTSTRAP_MIN:
            return None
        
        if not self.is_trained or self.model is None:
            return None
        
        try:
            features = self.feature_engineer.transform(transaction).reshape(1, -1)
            # SGDClassifier avec loss='log_loss' retourne probabilités
            probas = self.model.predict_proba(features)[0]
            # Probabilité de classe 1 (fraude)
            return float(probas[1])
        except Exception as e:
            logger.error(f"Erreur lors de la prédiction: {e}")
            return None
    
    def train(self):
        """
        Réentraîner le modèle avec les données du buffer.
        Créer un nouveau vecteur de version.
        """
        if len(self.buffer) < config.BOOTSTRAP_MIN:
            logger.warning(f"Agency {self.agency}: Pas assez de données pour entraîner ({len(self.buffer)} < {config.BOOTSTRAP_MIN})")
            return False
        
        try:
            # Extraire features et labels du buffer
            transactions = list(self.buffer)
            X = self.feature_engineer.batch_transform(transactions)
            y = np.array([int(t.get("is_fraud", 0)) for t in transactions], dtype=np.int32)
            
            # Créer ou réutiliser le modèle
            if self.model is None:
                self.model = SGDClassifier(
                    loss='log_loss',
                    max_iter=100,
                    random_state=42,
                    n_jobs=1,
                    warm_start=False,
                    early_stopping=False,
                    verbose=0
                )
            
            # Entraîner
            self.model.fit(X, y)
            
            # Mettre à jour les métadonnées
            self.version += 1
            self.is_trained = True
            self.train_samples = len(self.buffer)
            self.last_trained_at = datetime.utcnow().isoformat()
            
            # Calculer les métriques basiques
            train_score = self.model.score(X, y)
            self.accuracy = train_score
            
            # Taux de fraude dans le buffer
            fraud_count = np.sum(y)
            self.fraud_rate = float(fraud_count) / len(y)
            
            # Estimer precision/recall/f1 (simplicité)
            y_pred = self.model.predict(X)
            tp = np.sum((y_pred == 1) & (y == 1))
            fp = np.sum((y_pred == 1) & (y == 0))
            fn = np.sum((y_pred == 0) & (y == 1))
            
            if (tp + fp) > 0:
                self.precision = float(tp) / (tp + fp)
            else:
                self.precision = 0.0
            
            if (tp + fn) > 0:
                self.recall = float(tp) / (tp + fn)
            else:
                self.recall = 0.0
            
            if (self.precision + self.recall) > 0:
                self.f1 = 2 * (self.precision * self.recall) / (self.precision + self.recall)
            else:
                self.f1 = 0.0
            
            # Sauvegarder le modèle
            self._save_model()
            
            logger.info(
                f"Agency {self.agency}: Modèle v{self.version} entraîné "
                f"(samples={self.train_samples}, accuracy={self.accuracy:.3f}, "
                f"fraud_rate={self.fraud_rate:.3f})"
            )
            
            return True
        
        except Exception as e:
            logger.error(f"Erreur lors de l'entraînement du modèle Agency {self.agency}: {e}")
            return False
    
    def _save_model(self):
        """Sauvegarder le modèle et ses métadonnées."""
        try:
            model_path = self.artifact_dir / f"model_v{self.version}.pkl"
            meta_path = self.artifact_dir / f"meta_v{self.version}.json"
            
            # Sauvegarder le pickle du modèle
            with open(model_path, 'wb') as f:
                pickle.dump(self.model, f)
            
            # Sauvegarder les métadonnées JSON
            meta = {
                'version': self.version,
                'agency': self.agency,
                'created_at': datetime.utcnow().isoformat(),
                'last_trained_at': self.last_trained_at,
                'train_samples': self.train_samples,
                'threshold': self.threshold,
                'accuracy': self.accuracy,
                'precision': self.precision,
                'recall': self.recall,
                'f1': self.f1,
                'fraud_rate': self.fraud_rate,
                'artifact_path': str(model_path)
            }
            
            with open(meta_path, 'w') as f:
                json.dump(meta, f, indent=2)
            
            logger.debug(f"Modèle v{self.version} sauvegardé pour agency {self.agency}")
        
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du modèle: {e}")
    
    def get_weights(self):
        """
        Récupérer les poids du modèle pour FL.
        
        Returns:
            dict avec 'coef_', 'intercept_', 'n_samples'
        """
        if not self.is_trained or self.model is None:
            return None
        
        return {
            'coef_': self.model.coef_.copy(),
            'intercept_': self.model.intercept_.copy(),
            'n_samples': self.train_samples,
            'version': self.version
        }
    
    def set_weights(self, coef: np.ndarray, intercept: np.ndarray):
        """
        Définir les poids du modèle (après agrégation FL).
        
        Args:
            coef_: matrice des coefficients
            intercept_: vecteur d'intercepts
        """
        if self.model is None:
            self.model = SGDClassifier(
                loss='log_loss',
                max_iter=1,
                random_state=42,
                warm_start=False
            )
        
        #self.model.coef_ = coef
        #self.model.intercept_ = intercept

        self.model.coef_ = coef
        self.model.intercept_ = intercept
        self.model.classes_ = np.array([0, 1], dtype=np.int64)
        self.model.n_features_in_ = coef.shape[1]

        logger.debug(f"Poids du modèle mis à jour pour agency {self.agency}")
