# flowguard_dashboard/app.py
# ─── Point d'entrée unique : init Dash + server ───

import sys
import os

# Ajouter le répertoire courant au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dash import Dash, html, dcc, page_container, callback, Input, Output
import dash_bootstrap_components as dbc

from components.navbar import create_sidebar
from core.neo4j_loader import loader
from core.config import REFRESH_INTERVAL

# ─── App Dash ───
app = Dash(
    __name__,
    use_pages=True,
    pages_folder="pages",
    external_stylesheets=[
        dbc.themes.DARKLY,
        dbc.icons.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
    ],
    suppress_callback_exceptions=True,
    title="FlowGuard | Fraud Detection",
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"name": "description", "content": "FlowGuard - Real-time Fraud Detection Monitoring Dashboard"},
    ],
)
server = app.server

# ─── Layout Principal ───
app.layout = dbc.Container([
    dcc.Location(id="url", refresh=False),
    dcc.Interval(id="global-interval", interval=REFRESH_INTERVAL, n_intervals=0),

    # Flexbox : Sidebar + Content
    html.Div(className="app-wrapper", children=[
        # Sidebar
        create_sidebar(),
        # Content Area
        html.Div(className="main-content", children=[
            page_container,
        ]),
    ]),
], fluid=True, className="app-container")


# ─── Callback Neo4j Status ───
@app.callback(
    Output("neo4j-status-dot", "className"),
    Output("neo4j-status-text", "children"),
    Input("global-interval", "n_intervals"),
)
def update_neo4j_status(_n):
    connected = loader.check_connection()
    if connected:
        return "status-dot status-green", "Neo4j Connected"
    return "status-dot status-red", "Neo4j Disconnected"
