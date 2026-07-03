# flowguard_dashboard/pages/local_models.py
# ─── Page 3 : Modèles ML Locaux ───

import dash
from dash import html, dcc, callback, Input, Output, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from core.neo4j_loader import loader
from core.config import (
    AGENCY_COLORS, AGENCY_KEY_TO_DISPLAY, PLOTLY_TEMPLATE,
    PAPER_BG, PLOT_BG, REFRESH_INTERVAL,
)
from components.live_badge import create_live_badge
from components.empty_state import create_empty_state

dash.register_page(__name__, path="/local-models", name="Modèles Locaux", order=2)


def _safe_metric(val):
    if val is None or (isinstance(val, float) and val != val):
        return 0.0, "N/A"
    return float(val), f"{val:.4f}"


def _format_samples(val):
    """Format train_samples robustly (handles numpy types, None, NaN)."""
    if val is None:
        return "N/A"
    try:
        n = int(val)
        return f"{n:,}"
    except (ValueError, TypeError, OverflowError):
        return "N/A"


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


def _build_agency_card(row, agency_key):
    """Construit une carte détaillée pour une agence."""
    color = AGENCY_COLORS.get(agency_key, "#888")
    display_name = AGENCY_KEY_TO_DISPLAY.get(agency_key, agency_key)

    version = row.get("version", "N/A")
    acc_val, acc_str = _safe_metric(row.get("accuracy"))
    prec_val, prec_str = _safe_metric(row.get("model_precision"))
    rec_val, rec_str = _safe_metric(row.get("recall"))
    f1_val, f1_str = _safe_metric(row.get("f1"))
    fraud_rate = row.get("fraud_rate")
    train_samples = row.get("train_samples", "N/A")
    threshold = row.get("threshold")
    last_trained = row.get("last_trained_at")

    if last_trained is not None and not pd.isna(last_trained) and hasattr(last_trained, "strftime"):
        last_trained_str = last_trained.strftime("%Y-%m-%d %H:%M")
    elif last_trained is not None and not pd.isna(last_trained):
        last_trained_str = str(last_trained)[:16]
    else:
        last_trained_str = "N/A"

    fraud_badge_color = "#FF4444" if fraud_rate is not None and fraud_rate == fraud_rate and fraud_rate > 0.1 else "#8b949e"
    fraud_str = f"{fraud_rate:.4f}" if fraud_rate is not None and fraud_rate == fraud_rate else "N/A"
    threshold_str = f"{threshold:.2f}" if threshold is not None and threshold == threshold else "N/A"

    def progress_bar(label, value, display_str, bar_color):
        pct = min(max(value * 100, 0), 100)
        return html.Div(className="metric-row", children=[
            html.Div(className="metric-label-row", children=[
                html.Span(label, className="metric-label"),
                html.Span(display_str, className="metric-value-text"),
            ]),
            html.Div(
                style={"height": "6px", "backgroundColor": "rgba(255,255,255,0.06)",
                       "borderRadius": "3px", "overflow": "hidden"},
                children=[
                    html.Div(style={
                        "height": "100%",
                        "width": f"{pct}%",
                        "backgroundColor": bar_color,
                        "borderRadius": "3px",
                        "transition": "width 0.4s ease",
                    }),
                ],
            ),
        ])

    return dbc.Card([
        dbc.CardHeader(
            html.Div(className="agency-card-header", children=[
                html.Span(display_name, style={"fontWeight": "700", "fontSize": "1.1rem"}),
                dbc.Badge(f"v{version}", className="ms-2", style={
                    "backgroundColor": f"{color}22", "color": color,
                    "fontSize": "0.85rem", "padding": "4px 12px",
                }),
            ]),
            style={"borderBottom": f"2px solid {color}", "backgroundColor": "#161b22"},
        ),
        dbc.CardBody([
            progress_bar("Accuracy", acc_val, acc_str, color),
            progress_bar("Precision", prec_val, prec_str, color),
            progress_bar("Recall", rec_val, rec_str, color),
            progress_bar("F1 Score", f1_val, f1_str, color),
            html.Hr(style={"borderColor": "#30363d", "margin": "12px 0"}),
            html.Div(className="model-detail-row", children=[
                html.Span("Fraud Rate", className="metric-label"),
                dbc.Badge(fraud_str, style={"backgroundColor": f"{fraud_badge_color}22",
                                            "color": fraud_badge_color}),
            ]),
            html.Div(className="model-detail-row", children=[
                html.Span("Train Samples", className="metric-label"),
                html.Span(_format_samples(train_samples), className="metric-value-text"),
            ]),
            html.Div(className="model-detail-row", children=[
                html.Span("Threshold", className="metric-label"),
                html.Span(threshold_str, className="metric-value-text"),
            ]),
            html.Div(className="model-detail-row", children=[
                html.Span("Last Trained", className="metric-label"),
                html.Span(last_trained_str, className="metric-value-text"),
            ]),
        ]),
    ], className="chart-card agency-model-card")


# ─── Layout ───

layout = html.Div([
    dcc.Interval(id="models-interval", interval=REFRESH_INTERVAL, n_intervals=0),

    html.Div(className="page-header", children=[
        html.H2("🤖 Modèles ML Locaux", className="page-title"),
        html.Div(id="models-live-badge"),
    ]),

    # Row 1 — Agency Cards
    dbc.Row(id="models-agency-cards", className="g-3 mb-4"),

    # Row 2 — Metric selector + Line chart
    dbc.Row([
        dbc.Col([
            dbc.Card(dbc.CardBody([
                html.Div(className="metric-selector-row", children=[
                    html.Label("Métrique :", className="metric-selector-label"),
                    dcc.Dropdown(
                        id="models-metric-dropdown",
                        options=[
                            {"label": "Accuracy", "value": "accuracy"},
                            {"label": "Precision", "value": "model_precision"},
                            {"label": "Recall", "value": "recall"},
                            {"label": "F1 Score", "value": "f1"},
                        ],
                        value="accuracy",
                        clearable=False,
                        className="metric-dropdown",
                        style={"width": "200px"},
                    ),
                ]),
                dcc.Graph(id="models-evolution-chart", config={"displayModeBar": False}),
            ]), className="chart-card"),
        ], width=12),
    ], className="g-3 mb-4"),

    # Row 3 — Grouped bar + History table
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id="models-comparison-bar", config={"displayModeBar": False})),
                     className="chart-card"),
            lg=6, md=12,
        ),
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.H6("Historique Complet", className="card-section-title"),
                html.Div(id="models-history-table"),
            ]), className="chart-card"),
            lg=6, md=12,
        ),
    ], className="g-3 mb-4"),
])


# ─── Callbacks ───

@callback(
    Output("models-agency-cards", "children"),
    Output("models-comparison-bar", "figure"),
    Output("models-history-table", "children"),
    Output("models-live-badge", "children"),
    Input("models-interval", "n_intervals"),
)
def update_models_main(_n):
    now = datetime.now()
    df_latest = loader.get_latest_model_per_agency()

    empty_fig = go.Figure()
    _chart_layout(empty_fig, "Aucune donnée")

    if df_latest.empty:
        cards = [dbc.Col(create_empty_state("Aucun modèle entraîné"), width=12)]
        empty_table = create_empty_state("Aucun historique", "bi-clock-history")
        return cards, empty_fig, empty_table, create_live_badge(now)

    # ── Agency Cards ──
    cards = []
    for agency_key in ["Agency_A", "Agency_B", "Agency_C"]:
        adf = df_latest[df_latest["agency"] == agency_key]
        if adf.empty:
            continue
        row = adf.iloc[0]
        cards.append(dbc.Col(_build_agency_card(row, agency_key), lg=4, md=6, xs=12))

    # ── Comparison bar ──
    metrics = ["accuracy", "model_precision", "recall", "f1"]
    metric_labels = {"accuracy": "Accuracy", "model_precision": "Precision",
                     "recall": "Recall", "f1": "F1"}
    fig_bar = go.Figure()
    for agency_key, color in AGENCY_COLORS.items():
        adf = df_latest[df_latest["agency"] == agency_key]
        if adf.empty:
            continue
        row = adf.iloc[0]
        display = AGENCY_KEY_TO_DISPLAY.get(agency_key, agency_key)
        values = [row.get(m, 0) if row.get(m) is not None and row.get(m) == row.get(m) else 0 for m in metrics]
        fig_bar.add_trace(go.Bar(
            x=[metric_labels[m] for m in metrics],
            y=values,
            name=display,
            marker_color=color,
        ))
    _chart_layout(fig_bar, "Comparaison des Métriques entre Agences")
    fig_bar.update_layout(barmode="group", bargap=0.15, bargroupgap=0.1)
    fig_bar.update_yaxes(title_text="Valeur", range=[0, 1.05])

    # ── History table ──
    df_hist = loader.get_models_history()
    if df_hist.empty:
        table = create_empty_state("Aucun historique", "bi-clock-history")
    else:
        tdf = df_hist.copy()
        if "agency" in tdf.columns:
            tdf["agency"] = tdf["agency"].map(AGENCY_KEY_TO_DISPLAY).fillna(tdf["agency"])
        for col in ["accuracy", "model_precision", "recall", "f1", "fraud_rate"]:
            if col in tdf.columns:
                tdf[col] = tdf[col].apply(lambda x: f"{x:.4f}" if x is not None and x == x else "N/A")
        if "last_trained_at" in tdf.columns:
            tdf["last_trained_at"] = tdf["last_trained_at"].apply(
                lambda x: x.strftime("%Y-%m-%d %H:%M") if (not pd.isna(x) and hasattr(x, "strftime")) else "N/A"
            )
        display_cols = ["agency", "version", "accuracy", "model_precision", "recall",
                        "f1", "fraud_rate", "train_samples", "last_trained_at"]
        available = [c for c in display_cols if c in tdf.columns]
        col_names = {
            "agency": "Agence", "version": "Version", "accuracy": "Accuracy",
            "model_precision": "Precision", "recall": "Recall", "f1": "F1",
            "fraud_rate": "Fraud Rate", "train_samples": "Samples", "last_trained_at": "Last Trained",
        }
        table = dash_table.DataTable(
            columns=[{"name": col_names.get(c, c), "id": c} for c in available],
            data=tdf[available].sort_values("version", ascending=False).to_dict("records") if "version" in tdf.columns else tdf[available].to_dict("records"),
            page_size=8,
            sort_action="native",
            style_table={"overflowX": "auto"},
            style_header={
                "backgroundColor": "#161b22", "color": "#e6edf3",
                "fontWeight": "600", "border": "1px solid #30363d", "fontSize": "12px",
            },
            style_cell={
                "backgroundColor": "#0d1117", "color": "#c9d1d9",
                "border": "1px solid #21262d", "fontSize": "12px",
                "padding": "8px 12px", "fontFamily": "Inter, sans-serif", "textAlign": "left",
            },
        )

    return cards, fig_bar, table, create_live_badge(now)


@callback(
    Output("models-evolution-chart", "figure"),
    Input("models-interval", "n_intervals"),
    Input("models-metric-dropdown", "value"),
)
def update_models_evolution(_n, selected_metric):
    df_hist = loader.get_models_history()

    empty_fig = go.Figure()
    _chart_layout(empty_fig, "Aucune donnée")

    if df_hist.empty or selected_metric not in df_hist.columns:
        return empty_fig

    metric_labels = {"accuracy": "Accuracy", "model_precision": "Precision",
                     "recall": "Recall", "f1": "F1 Score"}
    label = metric_labels.get(selected_metric, selected_metric)

    fig = go.Figure()
    for agency_key, color in AGENCY_COLORS.items():
        adf = df_hist[df_hist["agency"] == agency_key].sort_values("version")
        if adf.empty:
            continue
        display = AGENCY_KEY_TO_DISPLAY.get(agency_key, agency_key)
        fig.add_trace(go.Scatter(
            x=adf["version"], y=adf[selected_metric],
            mode="lines+markers",
            name=display,
            line=dict(color=color, width=2),
            marker=dict(size=7),
        ))
        # Annotation on last point
        if not adf.empty:
            last = adf.iloc[-1]
            val = last[selected_metric]
            if val is not None and val == val:
                fig.add_annotation(
                    x=last["version"], y=val,
                    text=f"{val:.4f}",
                    showarrow=True, arrowhead=2,
                    font=dict(color=color, size=10),
                    arrowcolor=color,
                    ax=30, ay=-20,
                )

    _chart_layout(fig, f"Évolution {label} par Version de Modèle")
    fig.update_xaxes(title_text="Version du Modèle", dtick=1)
    fig.update_yaxes(title_text=label, range=[0, 1.05])

    return fig
