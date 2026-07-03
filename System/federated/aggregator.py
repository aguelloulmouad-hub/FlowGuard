"""
Agregador FL - Écoute model.updates, agrège quand A+B+C ont une nouvelle version.
Algorithme: FedAvg simple (moyenne pondérée des coefs et intercepts).
"""

import logging
import json
import uuid
import numpy as np
import pickle
from datetime import datetime
from pathlib import Path
from kafka import KafkaConsumer, KafkaProducer
import config
from ml.local_model import LocalModel
from storage.neo4j_writer import Neo4jWriter

logger = logging.getLogger(__name__)


class FederatedAggregator:
    """
    Agrégateur FL qui écoute model.updates et déclenche des rounds FL.
    Algorithme: FedAvg avec moyenne pondérée par nombre de samples.
    """
    
    def __init__(self):
        self.consumer = KafkaConsumer(
            config.TOPICS["model_updates"],
            bootstrap_servers=config.KAFKA_BOOTSTRAP,
            group_id="aggregator_group",
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            #consumer_timeout_ms=config.KAFKA_AGGREGATOR_TIMEOUT
        )
        
        self.federated_producer = KafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            retries=3
        )
        
        # Neo4j writer
        self.neo4j_writer = Neo4jWriter()
        
        # Dictionnaire des versions locales actuelles par agence
        # { "A": version_locale, "B": version_locale, "C": version_locale }
        self.local_versions = {agency: 0 for agency in config.AGENCIES}
        
        # Dictionnaire des versions agrégées
        # { "A": version_last_aggregated, ... }
        self.aggregated_versions = {agency: 0 for agency in config.AGENCIES}
        
        # Compteur global de rounds
        self.global_round = 0
        
        # Instances de modèles locaux
        self.local_models = {agency: LocalModel(agency) for agency in config.AGENCIES}
    
    def check_fl_trigger(self) -> bool:
        """
        Vérifier si un round FL doit être déclenché.
        Condition: A ET B ET C ont chacun une nouvelle version non encore agrégée
        ET les modèles ont des poids exploitables.
        
        Returns:
            bool True si trigger, False sinon
        """
        for agency in config.AGENCIES:
            # S'il n'y a pas de nouvelle version, pas de trigger
            if self.local_versions[agency] <= self.aggregated_versions[agency]:
                return False
            
            # Vérifier que le modèle est entraîné et a des poids
            if self.local_models[agency].model is None or not self.local_models[agency].is_trained:
                logger.debug(f"Agence {agency}: Modèle pas encore entraîné, FL pas déclenché")
                return False
        
        return True
        

    def _refresh_local_model(self, agency: str, update: dict) -> bool:
        artifact_path = update.get("artifact_path")
        version = update.get("version")

        if not artifact_path:
            artifact_path = (
                Path(config.MODEL_DIR) /
                f"agency_{agency.lower()}" /
                f"model_v{version}.pkl"
            )

        artifact_path = Path(artifact_path)
        if not artifact_path.exists():
            logger.warning(f"Agence {agency}: artefact introuvable: {artifact_path}")
            return False

        try:
            with open(artifact_path, "rb") as f:
                model = pickle.load(f)

            lm = self.local_models[agency]
            lm.model = model
            lm.version = int(version)
            lm.is_trained = True
            lm.train_samples = int(update.get("train_samples", lm.train_samples or 0))

            # Charger aussi les métriques locales depuis le meta JSON
            meta_path = artifact_path.with_name(f"meta_v{version}.json")
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)

                lm.accuracy = meta.get("accuracy")
                lm.precision = meta.get("precision")
                lm.recall = meta.get("recall")
                lm.f1 = meta.get("f1")
                lm.fraud_rate = meta.get("fraud_rate")
                lm.last_trained_at = meta.get("last_trained_at", lm.last_trained_at)
                lm.threshold = meta.get("threshold", lm.threshold)
            else:
                logger.warning(f"Agence {agency}: meta introuvable: {meta_path}")

            logger.info(f"Agence {agency}: modèle v{lm.version} chargé pour FL")
            return True

        except Exception as e:
            logger.error(f"Agence {agency}: impossible de charger le modèle: {e}")
            return False

    def fedavg_aggregate(self):
        """
        Effectuer l'agrégation FedAvg.
        Moyenne pondérée des coefs et intercepts.
        """
        logger.info("Déclenchement du round FL")
        
        try:
            # Charger les poids de tous les modèles locaux
            weights_list = []
            base_versions = {}
            
            for agency in config.AGENCIES:
                weights = self.local_models[agency].get_weights()
                
                if weights is None:
                    logger.error(f"Impossible de récupérer les poids pour {agency}")
                    return False
                
                weights_list.append(weights)
                base_versions[agency] = weights['version']
            
            # Vérifier la compatibilité des dimensions
            coef_shape = weights_list[0]['coef_'].shape
            for weights in weights_list[1:]:
                if weights['coef_'].shape != coef_shape:
                    logger.error(
                        f"Dimensions incompatibles: {weights['coef_'].shape} vs {coef_shape}"
                    )
                    return False
            
            # Calculer les poids d'agrégation (par nombre de samples)
            total_samples = sum(w['n_samples'] for w in weights_list)
            if total_samples <= 0:
                logger.error("Impossible d'agréger: total_samples <= 0")
                return False

            weights_agg = [w['n_samples'] / total_samples for w in weights_list]
            logger.info(f"Poids d'agrégation: {dict(zip(config.AGENCIES, weights_agg))}")
                        
            # Calcul des métriques globales FL comme moyenne pondérée des métriques locales
            local_metrics = []

            for i, agency in enumerate(config.AGENCIES):
                lm = self.local_models[agency]
                local_metrics.append({
                    "weight": weights_agg[i],
                    "accuracy": lm.accuracy,
                    "precision": lm.precision,
                    "recall": lm.recall,
                    "f1": lm.f1,
                    "fraud_rate": lm.fraud_rate
                })

            def weighted_average(metric_name):
                numerator = 0.0
                denominator = 0.0

                for metric in local_metrics:
                    value = metric.get(metric_name)
                    if value is not None:
                        numerator += metric["weight"] * value
                        denominator += metric["weight"]

                if denominator == 0:
                    return None

                return numerator / denominator

            global_accuracy = weighted_average("accuracy")
            global_precision = weighted_average("precision")
            global_recall = weighted_average("recall")
            global_f1 = weighted_average("f1")
            global_fraud_rate = weighted_average("fraud_rate")

            # Agrégation FedAvg des coefs
            global_coef = np.zeros_like(weights_list[0]['coef_'])
            global_intercept = np.zeros_like(weights_list[0]['intercept_'])
            
            for i, agency in enumerate(config.AGENCIES):
                global_coef += weights_agg[i] * weights_list[i]['coef_']
                global_intercept += weights_agg[i] * weights_list[i]['intercept_']
            
            # Incrémenter la version globale
            self.global_round += 1
            global_version = self.global_round
            
            # Sauvegarder le modèle global
            template_model = self.local_models[config.AGENCIES[0]].model
            
            global_model = self.local_models[config.AGENCIES[0]].model.__class__(
                loss='log_loss',
                max_iter=1,
                random_state=42,
                warm_start=False
            )
            global_model.coef_ = global_coef
            global_model.intercept_ = global_intercept
            global_model.classes_ = template_model.classes_.copy()
            global_model.n_features_in_ = template_model.n_features_in_
            
            model_dir = Path(config.MODEL_DIR) / "global"
            model_dir.mkdir(parents=True, exist_ok=True)
            
            model_path = model_dir / f"global_model_v{global_version}.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump(global_model, f)
                        
            # Sauvegarder les métadonnées du modèle global
            meta_path = model_dir / f"meta_v{global_version}.json"
            global_meta = {
                "version": global_version,
                "created_at": datetime.utcnow().isoformat(),
                "global_version": global_version,
                "artifact_path": str(model_path),
                "aggregated_agencies": config.AGENCIES,
                "base_local_versions": base_versions,
                "accuracy": global_accuracy,
                "precision": global_precision,
                "recall": global_recall,
                "f1": global_f1,
                "fraud_rate": global_fraud_rate
            }

            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(global_meta, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Modèle global v{global_version} sauvegardé")
            
            # Publier dans federated.updates
            update = {
                "round": global_version,
                "aggregated_agencies": config.AGENCIES,
                "base_local_versions": base_versions,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            self.federated_producer.send(config.TOPICS["federated_updates"], value=update)
            
            # Écrire le round dans Neo4j
            round_data = {
                "round_id": f"fl_round_{global_version}",
                "created_at": datetime.utcnow().isoformat(),
                "global_version": global_version,
                "aggregated_agencies": config.AGENCIES,
                "base_local_versions": base_versions,
                "accuracy": global_accuracy,
                "precision": global_precision,
                "recall": global_recall,
                "f1": global_f1,
                "fraud_rate": global_fraud_rate,
                "artifact_path": str(model_path)
            }
            
            self.neo4j_writer.write_federated_round(round_data)
            
            # Mettre à jour les versions agrégées
            for agency in config.AGENCIES:
                self.aggregated_versions[agency] = base_versions[agency]
            
            logger.info(f"Round FL {global_version} agrégé avec succès")
            return True
        
        except Exception as e:
            logger.error(f"Erreur lors de l'agrégation FL: {e}")
            return False

    def process_model_update(self, update: dict):
        """
        Traiter une mise à jour de modèle local.
        
        Args:
            update: dict avec agency et version
        """
        agency = update.get("agency")
        version = update.get("version")
        
        if agency not in config.AGENCIES:
            logger.warning(f"Agence inconnue: {agency}")
            return
        
        # Mettre à jour la version locale
        #self.local_versions[agency] = version
        #logger.info(f"Mise à jour Agency {agency}: version {version}")
        
        # Vérifier le trigger FL
        #if self.check_fl_trigger():
        #    logger.info("Conditions FL remplies, agrégation en cours...")
        #    self.fedavg_aggregate()

        self.local_versions[agency] = version
        logger.info(f"Mise à jour Agency {agency}: version {version}")

        self._refresh_local_model(agency, update)

        if self.check_fl_trigger():
            logger.info("Conditions FL remplies, agrégation en cours...")
            self.fedavg_aggregate()
            
    def run(self):
        logger.info("Agrégateur FL démarré, écoute model.updates")

        try:
            while True:
                msg_pack = self.consumer.poll(timeout_ms=1000, max_records=50)
                if not msg_pack:
                    continue

                for _tp, messages in msg_pack.items():
                    for message in messages:
                        self.process_model_update(message.value)

        except KeyboardInterrupt:
            logger.info("Agrégateur FL arrêté par l'utilisateur")
        except Exception as e:
            logger.error(f"Erreur fatale dans l'agrégateur FL: {e}")
        finally:
            self.federated_producer.flush()
            self.consumer.close()
            self.federated_producer.close()
            self.neo4j_writer.close()
            logger.info("Ressources de l'agrégateur FL fermées")