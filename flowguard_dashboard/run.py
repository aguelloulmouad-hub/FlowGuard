# flowguard_dashboard/run.py
# ─── Lance l'application FlowGuard Dashboard ───

import sys
import os

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app

if __name__ == "__main__":
    print("=" * 60)
    print("  [*] FlowGuard Dashboard")
    print("  Fraud Detection Monitoring - Real-Time")
    print("=" * 60)
    print("  URL:   http://localhost:8050")
    print("  Neo4j: bolt://localhost:7687")
    print("=" * 60)
    app.run(debug=False, host="0.0.0.0", port=8050)
