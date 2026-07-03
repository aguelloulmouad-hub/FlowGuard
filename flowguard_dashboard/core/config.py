# flowguard_dashboard/core/config.py
# ─── Configuration globale du dashboard FlowGuard ───

# ─── Neo4j ───
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"

# ─── Refresh ───
REFRESH_INTERVAL = 10_000  # millisecondes

# ─── Couleurs agences ───
AGENCY_COLORS = {
    "Agency_A": "#00D4FF",   # cyan
    "Agency_B": "#FF6B35",   # orange
    "Agency_C": "#7B2FBE",   # violet
}

# ─── Couleurs spéciales ───
FL_COLOR   = "#00FF88"       # vert néon pour le modèle global
ALERT_HIGH = "#FF4444"       # score > 0.8
ALERT_MED  = "#FF8C00"       # score 0.6–0.8
ALERT_LOW  = "#FFD700"       # score 0.5–0.6

# ─── Plotly template ───
PLOTLY_TEMPLATE = "plotly_dark"
PAPER_BG = "rgba(0,0,0,0)"
PLOT_BG  = "rgba(0,0,0,0)"

# ─── Mapping agences ───
AGENCY_ID_TO_KEY = {
    "A": "Agency_A",
    "B": "Agency_B",
    "C": "Agency_C",
}

AGENCY_KEY_TO_DISPLAY = {
    "Agency_A": "Agency A",
    "Agency_B": "Agency B",
    "Agency_C": "Agency C",
}

AGENCY_KEY_TO_ID = {v: k for k, v in AGENCY_ID_TO_KEY.items()}

# ─── Jours de la semaine ───
DAY_LABELS = {
    0: "Lun",
    1: "Mar",
    2: "Mer",
    3: "Jeu",
    4: "Ven",
    5: "Sam",
    6: "Dim",
}

# ─── App ───
APP_VERSION = "2.0.0"
APP_TITLE = "FlowGuard | Fraud Detection"
