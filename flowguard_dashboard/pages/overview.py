# flowguard_dashboard/pages/overview.py
# ─── Page 1 : Vue Générale ───

import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

from core.neo4j_loader import loader
from core.config import (
    AGENCY_COLORS, AGENCY_KEY_TO_DISPLAY, PLOTLY_TEMPLATE,
    PAPER_BG, PLOT_BG, REFRESH_INTERVAL, FL_COLOR,
)
from components.kpi_card import create_kpi_card
from components.live_badge import create_live_badge
from components.empty_state import create_empty_state

dash.register_page(__name__, path="/", name="Overview", order=0)

# ─── Helpers ───

def _safe(val, fmt=None):
    if val is None or (isinstance(val, float) and val != val):
        return "N/A"
    if fmt == "pct":
        return f"{val * 100:.2f}%"
    if fmt == "int":
        return f"{int(val):,}"
    if fmt == "f2":
        return f"{val:.4f}"
    return str(val)


def _chart_layout(fig, title=""):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        title=dict(text=title, font=dict(size=14, color="#e6edf3")),
        font=dict(family="Inter, sans-serif", color="#8b949e"),
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color="#8b949e"),
        ),
    )
    return fig

# ─── Layout ───

layout = html.Div([
    dcc.Interval(id="overview-interval", interval=REFRESH_INTERVAL, n_intervals=0),

    # Header
    html.Div(className="page-header", children=[
        html.H2("📊 Vue Générale", className="page-title"),
        html.Div(id="overview-live-badge"),
    ]),

    # Row 1 — KPI Cards
    dbc.Row(id="overview-kpi-row", className="g-3 mb-4"),

    # Row 2 — Line chart + Gauge
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id="overview-timeseries", config={"displayModeBar": False})),
                     className="chart-card"),
            lg=8, md=12,
        ),
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id="overview-gauge", config={"displayModeBar": False})),
                     className="chart-card"),
            lg=4, md=12,
        ),
    ], className="g-3 mb-4"),

    # Row 3 — Bar chart + Scatter
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id="overview-alerts-bar", config={"displayModeBar": False})),
                     className="chart-card"),
            lg=6, md=12,
        ),
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id="overview-scatter", config={"displayModeBar": False})),
                     className="chart-card"),
            lg=6, md=12,
        ),
    ], className="g-3 mb-4"),
])


# ─── Callback ───

@callback(
    Output("overview-kpi-row", "children"),
    Output("overview-timeseries", "figure"),
    Output("overview-gauge", "figure"),
    Output("overview-alerts-bar", "figure"),
    Output("overview-scatter", "figure"),
    Output("overview-live-badge", "children"),
    Input("overview-interval", "n_intervals"),
)
def update_overview(_n):
    now = datetime.now()

    # ── KPIs ──
    df_kpi = loader.get_kpis()
    if df_kpi.empty:
        kpis = [dbc.Col(create_empty_state(), width=12)]
        empty_fig = go.Figure()
        _chart_layout(empty_fig, "Aucune donnée")
        return kpis, empty_fig, empty_fig, empty_fig, empty_fig, create_live_badge(now)

    row = df_kpi.iloc[0]
    kpis = [
        dbc.Col(create_kpi_card("Total Transactions", _safe(row.get("total_txn"), "int"),
                                "bi-receipt", "#00D4FF"), lg=3, md=6, xs=12),
        dbc.Col(create_kpi_card("Total Alertes", _safe(row.get("total_alerts"), "int"),
                                "bi-exclamation-triangle", "#FF4444"), lg=3, md=6, xs=12),
        dbc.Col(create_kpi_card("Taux de Fraude", _safe(row.get("global_fraud_rate"), "pct"),
                                "bi-shield-exclamation", "#FF8C00"), lg=3, md=6, xs=12),
        dbc.Col(create_kpi_card("Rounds FL", _safe(row.get("total_fl_rounds"), "int"),
                                "bi-arrow-repeat", FL_COLOR), lg=3, md=6, xs=12),
    ]

    # ── Timeseries ──
    df_ts = loader.get_transaction_timeseries()
    if df_ts.empty:
        fig_ts = go.Figure()
        _chart_layout(fig_ts, "Flux de Transactions (24h)")
    else:
        fig_ts = go.Figure()
        for agency, color in AGENCY_COLORS.items():
            adf = df_ts[df_ts["agency"] == agency].sort_values("hour_of_day")
            if adf.empty:
                continue
            display = AGENCY_KEY_TO_DISPLAY.get(agency, agency)
            fig_ts.add_trace(go.Scatter(
                x=adf["hour_of_day"], y=adf["cnt"],
                mode="lines+markers",
                name=display,
                line=dict(color=color, width=2, shape="spline"),
                marker=dict(size=6),
            ))
        _chart_layout(fig_ts, "Flux de Transactions par Heure & Agence")
        fig_ts.update_xaxes(title_text="Heure", dtick=2)
        fig_ts.update_yaxes(title_text="Nombre de Transactions")

    # ── Gauge ──
    avg_score = row.get("avg_score")
    avg_score_val = avg_score if avg_score is not None and avg_score == avg_score else 0
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=avg_score_val,
        number={"font": {"size": 36, "color": "#e6edf3"}, "valueformat": ".4f"},
        title={"text": "Score Moyen", "font": {"size": 14, "color": "#8b949e"}},
        gauge={
            "axis": {"range": [0, 1], "tickcolor": "#8b949e"},
            "bar": {"color": "#00D4FF"},
            "bgcolor": "rgba(255,255,255,0.05)",
            "steps": [
                {"range": [0, 0.3], "color": "rgba(0,255,136,0.2)"},
                {"range": [0.3, 0.6], "color": "rgba(255,140,0,0.2)"},
                {"range": [0.6, 1], "color": "rgba(255,68,68,0.2)"},
            ],
            "threshold": {
                "line": {"color": "#FF4444", "width": 3},
                "thickness": 0.8,
                "value": 0.5,
            },
        },
    ))
    _chart_layout(fig_gauge, "")
    fig_gauge.update_layout(height=300)

    # ── Alerts Bar ──
    df_alerts = loader.get_recent_alerts(limit=500)
    if df_alerts.empty:
        fig_bar = go.Figure()
        _chart_layout(fig_bar, "Alertes par Agence")
    else:
        alert_counts = df_alerts.groupby("agency").size().reset_index(name="count")
        fig_bar = go.Figure()
        for _, r in alert_counts.iterrows():
            ag = r["agency"]
            color = AGENCY_COLORS.get(ag, "#888")
            display = AGENCY_KEY_TO_DISPLAY.get(ag, ag)
            fig_bar.add_trace(go.Bar(
                x=[display], y=[r["count"]],
                name=display,
                marker_color=color,
                marker_line=dict(width=0),
            ))
        _chart_layout(fig_bar, "Alertes par Agence")
        fig_bar.update_layout(showlegend=False, bargap=0.3)
        fig_bar.update_yaxes(title_text="Nombre d'Alertes")

    # ── Scatter ──
    df_sc = loader.get_scatter_score_amount()
    if df_sc.empty:
        fig_sc = go.Figure()
        _chart_layout(fig_sc, "Score vs Montant")
    else:
        fig_sc = go.Figure()
        for agency, color in AGENCY_COLORS.items():
            adf = df_sc[df_sc["agency"] == agency]
            if adf.empty:
                continue
            display = AGENCY_KEY_TO_DISPLAY.get(agency, agency)
            fig_sc.add_trace(go.Scatter(
                x=adf["amount"], y=adf["score"],
                mode="markers",
                name=display,
                marker=dict(color=color, size=6, opacity=0.7),
                text=adf.get("transaction_id"),
                hovertemplate="<b>%{text}</b><br>Montant: %{x}<br>Score: %{y:.4f}<extra></extra>",
            ))
        _chart_layout(fig_sc, "Score vs Montant par Agence")
        fig_sc.update_xaxes(title_text="Montant")
        fig_sc.update_yaxes(title_text="Score de Fraude")

    return kpis, fig_ts, fig_gauge, fig_bar, fig_sc, create_live_badge(now)
