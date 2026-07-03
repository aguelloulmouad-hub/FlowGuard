"""
Configuration centralisée pour le projet FlowGuard.
Aucun hardcode en dehors de ce fichier.
"""

# Kafka
KAFKA_BOOTSTRAP = "127.0.0.1:9092"

# Consumer timeouts (ms) - spécifique à chaque composant
KAFKA_CLEANER_TIMEOUT = 5000      # Cleaner: arrive rapidement (transactions raw)
KAFKA_ML_PIPELINE_TIMEOUT = 5000  # ML Pipeline: arrive rapidement (transactions cleaned)
KAFKA_AGGREGATOR_TIMEOUT = 60000  # Aggregator: timeout plus long (mises à jour modèle rares)

# Neo4j
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"

# Kafka Topics
TOPICS = {
    "raw": "transactions.raw",
    "cleaned": "transactions.cleaned",
    "alerts": "alerts",
    "model_updates": "model.updates",
    "federated_updates": "federated.updates"
}

# Agences
AGENCIES = ["A", "B", "C"]

# ML Configuration
RETRAIN_EVERY = 1000          # Réentraîner après 1000 transactions
BUFFER_SIZE = 5000            # Buffer glissant max
BOOTSTRAP_MIN = 1000          # Minimum de transactions avant premier entraînement
PREDICTION_THRESHOLD = 0.5    # Seuil pour générer une alerte

# Federated Learning
FL_TRIGGER = 3                # Déclencher FL quand 3 agences ont une nouvelle version

# Paths
MODEL_DIR = "artifacts/models"
SCHEMA_OUTPUT = "schema/neo4j_schema.json"

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"

# Timeouts
KAFKA_CONSUMER_TIMEOUT = 5000
NEO4J_CONNECTION_TIMEOUT = 30
