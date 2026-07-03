"""
run.py - Point d'entrée unique de FlowGuard.

Lance dans des threads séparés :
1. fake_streams.py → Agency A, B, C (3 threads producteurs)
2. cleaner.py (1 thread consommateur/producteur)
3. ml_pipeline.py (1 thread consommateur ML)
4. aggregator.py (1 thread FL)
5. export_schema.py → appelé une fois au démarrage

Usage:
    python run.py           ← Lance le pipeline normal
    python run.py --test    ← Lance les tests avant le pipeline
"""

import sys
import logging
import threading
import time
from pathlib import Path
import config
from schema.export_schema import export_schema

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT
)

logger = logging.getLogger(__name__)


def run_pipeline():
    """Lancer le pipeline FlowGuard complet."""
    
    logger.info("=" * 80)
    logger.info("FLOWGUARD - Pipeline de détection de fraude en temps réel")
    logger.info("=" * 80)
    
    # Étape 1 : Exporter le schéma Neo4j
    logger.info("\n[1/5] Exportation du schéma Neo4j...")
    try:
        export_schema()
        logger.info("✓ Schéma Neo4j exporté")
    except Exception as e:
        logger.error(f"✗ Erreur lors de l'export du schéma: {e}")
        return False
    
    # Étape 2 : Lancer les générateurs de transactions (3 agences)
    logger.info("\n[2/5] Lancement des générateurs de transactions...")
    from streams.fake_streams import FakeStreamGenerator
    
    streams_threads = []
    for agency in config.AGENCIES:
        def stream_task(ag):
            try:
                generator = FakeStreamGenerator(ag)
                generator.run(rate=10, duration=None)
            except Exception as e:
                logger.error(f"Erreur dans le stream Agency {ag}: {e}")
        
        t = threading.Thread(target=stream_task, args=(agency,), daemon=True, name=f"Stream-{agency}")
        t.start()
        streams_threads.append(t)
        time.sleep(0.5)
    
    logger.info(f"✓ {len(streams_threads)} producteurs de transactions lancés")
    
    # Étape 3 : Lancer le cleaner
    logger.info("\n[3/5] Lancement du cleaner...")
    from ingestion.cleaner import TransactionCleaner
    
    def cleaner_task():
        try:
            cleaner = TransactionCleaner()
            cleaner.run()
        except Exception as e:
            logger.error(f"Erreur dans le cleaner: {e}")
    
    cleaner_thread = threading.Thread(target=cleaner_task, daemon=True, name="Cleaner")
    cleaner_thread.start()
    time.sleep(1)
    logger.info("✓ Cleaner lancé")
    
    # Étape 4 : Lancer le pipeline ML
    logger.info("\n[4/5] Lancement du pipeline ML...")
    from ml.ml_pipeline import MLPipeline
    
    def ml_task():
        try:
            pipeline = MLPipeline()
            pipeline.run()
        except Exception as e:
            logger.error(f"Erreur dans le pipeline ML: {e}")
    
    ml_thread = threading.Thread(target=ml_task, daemon=True, name="ML-Pipeline")
    ml_thread.start()
    time.sleep(1)
    logger.info("✓ Pipeline ML lancé")
    
    # Étape 5 : Lancer l'agrégateur FL
    logger.info("\n[5/5] Lancement de l'agrégateur FL...")
    from federated.aggregator import FederatedAggregator
    
    def aggregator_task():
        try:
            aggregator = FederatedAggregator()
            aggregator.run()
        except Exception as e:
            logger.error(f"Erreur dans l'agrégateur FL: {e}")
    
    aggregator_thread = threading.Thread(target=aggregator_task, daemon=True, name="FL-Aggregator")
    aggregator_thread.start()
    time.sleep(1)
    logger.info("✓ Agrégateur FL lancé")
    
    logger.info("\n" + "=" * 80)
    logger.info("FLOWGUARD est opérationnel. Appuyez sur Ctrl+C pour arrêter.")
    logger.info("=" * 80)
    
    # Garder le processus principal actif
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nArrêt de FlowGuard...")
        logger.info("Les threads se fermeront progressivement.")
        time.sleep(2)


def main():
    """Fonction principale."""
    run_pipeline()
    


if __name__ == "__main__":
    main()
