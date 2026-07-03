# flowguard_dashboard/pages/alerts.py
# ─── Page 2 : Alertes Temps Réel ───

import dash
from dash import html, dcc, callback, Input, Output, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from datetime import datetime

from core.neo4j_loader import loader
from core.config import (
    AGENCY_COLORS, AGENCY_KEY_TO_DISPLAY, PLOTLY_TEMPLATE,
    PAPER_BG, PLOT_BG, REFRESH_INTERVAL,
    ALERT_HIGH, ALERT_MED, ALERT_LOW,
)
from components.kpi_card import create_kpi_card
from components.live_badge import create_live_badge
from components.empty_state import create_empty_state

dash.register_page(__name__, path="/alerts", name="Alertes", order=1)


def _safe(val, fmt=None):
    if val is None or (isinstance(val, float) and val != val):
        return "N/A"
    if fmt == "int":
        return f"{int(val):,}"
    if fmt == "f4":
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
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#8b949e")),
    )
    return fig


def _score_color(score):
    if score is None or (isinstance(score, float) and score != score):
        return ALERT_LOW
    if score > 0.8:
        return ALERT_HIGH
    if score > 0.6:
        return ALERT_MED
    return ALERT_LOW


# ─── Layout ───

layout = html.Div([
    dcc.Interval(id="alerts-interval", interval=REFRESH_INTERVAL, n_intervals=0),

    html.Div(className="page-header", children=[
        html.H2("🚨 Alertes Temps Réel", className="page-title"),
        html.Div(id="alerts-live-badge"),
    ]),

    # Row 1 — KPI Cards
    dbc.Row(id="alerts-kpi-row", className="g-3 mb-4"),

    # Row 2 — Live Table
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.H6("Dernières Alertes", className="card-section-title"),
                html.Div(id="alerts-table-container"),
            ]), className="chart-card"),
            width=12,
        ),
    ], className="g-3 mb-4"),

    # Row 3 — Area chart + Histogram
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id="alerts-area-chart", config={"displayModeBar": False})),
                     className="chart-card"),
            lg=7, md=12,
        ),
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id="alerts-histogram", config={"displayModeBar": False})),
                     className="chart-card"),
            lg=5, md=12,
        ),
    ], className="g-3 mb-4"),

    # Row 4 — Donut chart
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id="alerts-donut", config={"displayModeBar": False})),
                     className="chart-card"),
            lg=6, md=12, className="mx-auto",
        ),
    ], className="g-3 mb-4"),
])


# ─── Callback ───

@callback(
    Output("alerts-kpi-row", "children"),
    Output("alerts-table-container", "children"),
    Output("alerts-area-chart", "figure"),
    Output("alerts-histogram", "figure"),
    Output("alerts-donut", "figure"),
    Output("alerts-live-badge", "children"),
    Input("alerts-interval", "n_intervals"),
)
def update_alerts(_n):
    now = datetime.now()
    df_alerts = loader.get_recent_alerts(limit=100)

    empty_fig = go.Figure()
    _chart_layout(empty_fig, "Aucune donnée")

    if df_alerts.empty:
        kpis = [dbc.Col(create_empty_state("Aucune alerte détectée"), width=12)]
        empty_table = create_empty_state("Aucune alerte à afficher", "bi-bell-slash")
        return kpis, empty_table, empty_fig, empty_fig, empty_fig, create_live_badge(now)

    # ── KPIs ──
    total_alerts = len(df_alerts)
    avg_score = df_alerts["score"].mean() if "score" in df_alerts.columns else None
    max_score = df_alerts["score"].max() if "score" in df_alerts.columns else None

    kpis = [
        dbc.Col(create_kpi_card("Alertes Récentes", _safe(total_alerts, "int"),
                                "bi-exclamation-triangle-fill", ALERT_HIGH), lg=4, md=6, xs=12),
        dbc.Col(create_kpi_card("Score Moyen", _safe(avg_score, "f4"),
                                "bi-speedometer2", ALERT_MED), lg=4, md=6, xs=12),
        dbc.Col(create_kpi_card("Score Max", _safe(max_score, "f4"),
                                "bi-arrow-up-circle-fill", ALERT_HIGH), lg=4, md=6, xs=12),
    ]

    # ── Table ──
    table_df = df_alerts.head(50).copy()
    display_cols = ["alert_id", "agency", "transaction_id", "score", "threshold",
                    "merchant_category", "timestamp"]
    available_cols = [c for c in display_cols if c in table_df.columns]

    # Format columns
    if "agency" in table_df.columns:
        table_df["agency"] = table_df["agency"].map(AGENCY_KEY_TO_DISPLAY).fillna(table_df["agency"])
    if "score" in table_df.columns:
        table_df["score"] = table_df["score"].apply(lambda x: f"{x:.4f}" if x == x and x is not None else "N/A")
    if "threshold" in table_df.columns:
        table_df["threshold"] = table_df["threshold"].apply(lambda x: f"{x:.2f}" if x == x and x is not None else "N/A")
    if "timestamp" in table_df.columns:
        table_df["timestamp"] = table_df["timestamp"].apply(
            lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if hasattr(x, "strftime") else str(x)
        )

    col_names = {
        "alert_id": "Alert ID", "agency": "Agence", "transaction_id": "Transaction ID",
        "score": "Score", "threshold": "Seuil", "merchant_category": "Catégorie",
        "timestamp": "Timestamp",
    }

    table = dash_table.DataTable(
        id="alerts-data-table",
        columns=[{"name": col_names.get(c, c), "id": c} for c in available_cols],
        data=table_df[available_cols].to_dict("records"),
        page_size=10,
        sort_action="native",
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#161b22",
            "color": "#e6edf3",
            "fontWeight": "600",
            "border": "1px solid #30363d",
            "fontSize": "12px",
        },
        style_cell={
            "backgroundColor": "#0d1117",
            "color": "#c9d1d9",
            "border": "1px solid #21262d",
            "fontSize": "12px",
            "padding": "8px 12px",
            "fontFamily": "Inter, sans-serif",
            "textAlign": "left",
        },
        style_data_conditional=[
            {
                "if": {"filter_query": '{score} > "0.8000"'},
                "backgroundColor": "rgba(255,68,68,0.15)",
            },
            {
                "if": {"filter_query": '{score} > "0.6000" && {score} <= "0.8000"'},
                "backgroundColor": "rgba(255,140,0,0.15)",
            },
            {
                "if": {"filter_query": '{score} <= "0.6000"'},
                "backgroundColor": "rgba(255,215,0,0.10)",
            },
        ],
    )

    # ── Area chart: alertes par minute ──
    df_apm = loader.get_alerts_per_minute(minutes=60)
    if df_apm.empty:
        fig_area = go.Figure()
        _chart_layout(fig_area, "Alertes par Minute (dernière heure)")
    else:
        fig_area = go.Figure()
        for agency, color in AGENCY_COLORS.items():
            adf = df_apm[df_apm["agency"] == agency].sort_values("minute_bucket")
            if adf.empty:
                continue
            display = AGENCY_KEY_TO_DISPLAY.get(agency, agency)
            fig_area.add_trace(go.Scatter(
                x=adf["minute_bucket"], y=adf["cnt"],
                mode="lines",
                name=display,
                line=dict(color=color, width=1),
                fill="tonexty" if agency != list(AGENCY_COLORS.keys())[0] else "tozeroy",
                stackgroup="one",
            ))
        _chart_layout(fig_area, "Alertes par Minute (dernière heure)")
        fig_area.update_xaxes(title_text="Temps")
        fig_area.update_yaxes(title_text="Nombre d'Alertes")

    # ── Histogram: distribution scores ──
    df_scores = loader.get_score_distribution()
    if df_scores.empty:
        fig_hist = go.Figure()
        _chart_layout(fig_hist, "Distribution des Scores")
    else:
        fig_hist = go.Figure()
        for agency, color in AGENCY_COLORS.items():
            adf = df_scores[df_scores["agency"] == agency]
            if adf.empty:
                continue
            display = AGENCY_KEY_TO_DISPLAY.get(agency, agency)
            fig_hist.add_trace(go.Histogram(
                x=adf["score"],
                nbinsx=20,
                name=display,
                marker_color=color,
                opacity=0.7,
            ))
        _chart_layout(fig_hist, "Distribution des Scores d'Alerte")
        fig_hist.update_layout(barmode="overlay")
        fig_hist.update_xaxes(title_text="Score")
        fig_hist.update_yaxes(title_text="Fréquence")

    # ── Donut: top merchant categories ──
    if "merchant_category" in df_alerts.columns:
        cat_counts = df_alerts["merchant_category"].value_counts().head(8)
        fig_donut = go.Figure(go.Pie(
            labels=cat_counts.index.tolist(),
            values=cat_counts.values.tolist(),
            hole=0.5,
            marker=dict(colors=[
                "#00D4FF", "#FF6B35", "#7B2FBE", "#00FF88",
                "#FF4444", "#FFD700", "#FF69B4", "#4ECDC4",
            ]),
            textinfo="percent+label",
            textfont=dict(size=11),
        ))
        _chart_layout(fig_donut, "Top Catégories Marchands (Alertes)")
        fig_donut.update_layout(
            showlegend=True,
            legend=dict(orientation="v", x=1.02, y=0.5),
        )
    else:
        fig_donut = go.Figure()
        _chart_layout(fig_donut, "Catégories Marchands")

    return kpis, table, fig_area, fig_hist, fig_donut, create_live_badge(now)
