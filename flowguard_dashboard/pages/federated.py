# flowguard_dashboard/pages/federated.py
# ─── Page 4 : Federated Learning ───

import dash
from dash import html, dcc, callback, Input, Output, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from datetime import datetime

from core.neo4j_loader import loader
from core.config import (
    AGENCY_COLORS, AGENCY_KEY_TO_DISPLAY, PLOTLY_TEMPLATE,
    PAPER_BG, PLOT_BG, REFRESH_INTERVAL, FL_COLOR,
)
from components.live_badge import create_live_badge
from components.empty_state import create_empty_state

dash.register_page(__name__, path="/federated", name="Federated Learning", order=3)


def _hex_to_rgba(hex_color, alpha=0.2):
    """Convert hex color to rgba string for Plotly compatibility."""
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _safe(val, fmt=None):
    if val is None or (isinstance(val, float) and val != val):
        return "N/A"
    if fmt == "f4":
        return f"{val:.4f}"
    if fmt == "int":
        return f"{int(val):,}"
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


def _format_agencies(val):
    """Convertit ['A','B','C'] en 'A, B, C'."""
    if val is None:
        return "N/A"
    if isinstance(val, list):
        return ", ".join(str(x) for x in val)
    return str(val)


# ─── Layout ───

layout = html.Div([
    dcc.Interval(id="fl-interval", interval=REFRESH_INTERVAL, n_intervals=0),

    html.Div(className="page-header", children=[
        html.H2("🌐 Federated Learning", className="page-title"),
        html.Div(id="fl-live-badge"),
    ]),

    # Row 1 — Latest Round Card
    dbc.Row([
        dbc.Col(html.Div(id="fl-latest-round"), width=12),
    ], className="g-3 mb-4"),

    # Row 2 — Progression + Radar
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id="fl-progression", config={"displayModeBar": False})),
                     className="chart-card"),
            lg=7, md=12,
        ),
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id="fl-radar", config={"displayModeBar": False})),
                     className="chart-card"),
            lg=5, md=12,
        ),
    ], className="g-3 mb-4"),

    # Row 3 — History Table
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.H6("Historique des Rounds FL", className="card-section-title"),
                html.Div(id="fl-history-table"),
            ]), className="chart-card"),
            width=12,
        ),
    ], className="g-3 mb-4"),
])


# ─── Callback ───

@callback(
    Output("fl-latest-round", "children"),
    Output("fl-progression", "figure"),
    Output("fl-radar", "figure"),
    Output("fl-history-table", "children"),
    Output("fl-live-badge", "children"),
    Input("fl-interval", "n_intervals"),
)
def update_federated(_n):
    now = datetime.now()
    df_fl = loader.get_federated_rounds()

    empty_fig = go.Figure()
    _chart_layout(empty_fig, "Aucune donnée")

    if df_fl.empty:
        no_data = create_empty_state("Aucun round de Federated Learning détecté", "bi-globe2")
        return no_data, empty_fig, empty_fig, no_data, create_live_badge(now)

    # ── Latest Round Card ──
    last = df_fl.iloc[-1]
    created = last.get("created_at")
    created_str = created.strftime("%Y-%m-%d %H:%M:%S") if hasattr(created, "strftime") else str(created)[:19] if created else "N/A"
    agencies_str = _format_agencies(last.get("aggregated_agencies"))

    latest_card = dbc.Card([
        dbc.CardBody([
            html.Div(className="fl-latest-header", children=[
                html.Div([
                    html.H5("Dernier Round de Federated Learning", className="fl-latest-title"),
                    html.Div(className="fl-latest-info-row", children=[
                        html.Div([
                            html.Span("Round ID", className="fl-info-label"),
                            html.Span(_safe(last.get("round_id")), className="fl-info-value"),
                        ], className="fl-info-item"),
                        html.Div([
                            html.Span("Global Version", className="fl-info-label"),
                            dbc.Badge(f"v{_safe(last.get('global_version'))}", style={
                                "backgroundColor": f"{FL_COLOR}22", "color": FL_COLOR,
                                "fontSize": "0.9rem", "padding": "4px 12px",
                            }),
                        ], className="fl-info-item"),
                        html.Div([
                            html.Span("Timestamp", className="fl-info-label"),
                            html.Span(created_str, className="fl-info-value"),
                        ], className="fl-info-item"),
                        html.Div([
                            html.Span("Agences Agrégées", className="fl-info-label"),
                            html.Span(agencies_str, className="fl-info-value"),
                        ], className="fl-info-item"),
                    ]),
                ]),
                html.Div(className="fl-metrics-badges", children=[
                    dbc.Badge(f"Acc: {_safe(last.get('accuracy'), 'f4')}", className="fl-metric-badge",
                              style={"backgroundColor": f"{FL_COLOR}22", "color": FL_COLOR}),
                    dbc.Badge(f"F1: {_safe(last.get('f1'), 'f4')}", className="fl-metric-badge",
                              style={"backgroundColor": "#00D4FF22", "color": "#00D4FF"}),
                    dbc.Badge(f"Recall: {_safe(last.get('recall'), 'f4')}", className="fl-metric-badge",
                              style={"backgroundColor": "#FF6B3522", "color": "#FF6B35"}),
                    dbc.Badge(f"Prec: {_safe(last.get('fl_precision'), 'f4')}", className="fl-metric-badge",
                              style={"backgroundColor": "#7B2FBE22", "color": "#7B2FBE"}),
                ]),
            ]),
        ]),
    ], className="chart-card fl-latest-card", style={"borderLeft": f"3px solid {FL_COLOR}"})

    # ── Progression chart ──
    fig_prog = go.Figure()
    fl_colors = {"accuracy": FL_COLOR, "f1": "#00D4FF", "recall": "#FF6B35", "fl_precision": "#7B2FBE"}
    fl_labels = {"accuracy": "Accuracy", "f1": "F1 Score", "recall": "Recall", "fl_precision": "Precision"}

    for metric, color in fl_colors.items():
        if metric not in df_fl.columns:
            continue
        vals = df_fl[metric].dropna()
        if vals.empty:
            continue
        valid_df = df_fl.dropna(subset=[metric])
        fig_prog.add_trace(go.Scatter(
            x=valid_df["global_version"], y=valid_df[metric],
            mode="lines+markers",
            name=fl_labels.get(metric, metric),
            line=dict(color=color, width=2),
            marker=dict(size=7),
        ))
        # Annotation on last point
        if not valid_df.empty:
            last_pt = valid_df.iloc[-1]
            fig_prog.add_annotation(
                x=last_pt["global_version"], y=last_pt[metric],
                text=f"{last_pt[metric]:.4f}",
                showarrow=True, arrowhead=2,
                font=dict(color=color, size=10),
                arrowcolor=color,
                ax=35, ay=-15,
            )

    _chart_layout(fig_prog, "Progression FL au fil des Rounds")
    fig_prog.update_xaxes(title_text="Global Version", dtick=1)
    fig_prog.update_yaxes(title_text="Valeur", range=[0, 1.05])

    # ── Radar / Spider chart ──
    categories = ["Accuracy", "Precision", "Recall", "F1", "1 - Fraud Rate"]

    # Global FL values
    gl_acc = last.get("accuracy", 0) or 0
    gl_prec = last.get("fl_precision", 0) or 0
    gl_rec = last.get("recall", 0) or 0
    gl_f1 = last.get("f1", 0) or 0
    gl_fr = last.get("fraud_rate", 0) or 0
    gl_vals = [gl_acc, gl_prec, gl_rec, gl_f1, 1 - gl_fr]

    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=gl_vals + [gl_vals[0]],
        theta=categories + [categories[0]],
        name="Global FL",
        line=dict(color=FL_COLOR, width=2),
        fill="toself",
        fillcolor=_hex_to_rgba(FL_COLOR, 0.2),
        opacity=0.8,
    ))

    # Local models
    df_latest = loader.get_latest_model_per_agency()
    if not df_latest.empty:
        for agency_key, color in AGENCY_COLORS.items():
            adf = df_latest[df_latest["agency"] == agency_key]
            if adf.empty:
                continue
            row = adf.iloc[0]
            a_acc = row.get("accuracy", 0) or 0
            a_prec = row.get("model_precision", 0) or 0
            a_rec = row.get("recall", 0) or 0
            a_f1 = row.get("f1", 0) or 0
            a_fr = row.get("fraud_rate", 0) or 0
            vals = [a_acc, a_prec, a_rec, a_f1, 1 - a_fr]
            display = AGENCY_KEY_TO_DISPLAY.get(agency_key, agency_key)
            fig_radar.add_trace(go.Scatterpolar(
                r=vals + [vals[0]],
                theta=categories + [categories[0]],
                name=display,
                line=dict(color=color, width=1.5),
                fill="toself",
                fillcolor=_hex_to_rgba(color, 0.1),
                opacity=0.6,
            ))

    _chart_layout(fig_radar, "Global FL vs Modèles Locaux")
    fig_radar.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True, range=[0, 1],
                gridcolor="#30363d", linecolor="#30363d",
            ),
            angularaxis=dict(
                gridcolor="#30363d", linecolor="#30363d",
                tickfont=dict(color="#8b949e"),
            ),
        ),
    )

    # ── History table ──
    tdf = df_fl.copy()
    if "aggregated_agencies" in tdf.columns:
        tdf["aggregated_agencies"] = tdf["aggregated_agencies"].apply(_format_agencies)
    if "created_at" in tdf.columns:
        tdf["created_at"] = tdf["created_at"].apply(
            lambda x: x.strftime("%Y-%m-%d %H:%M") if hasattr(x, "strftime") else str(x)[:16] if x else "N/A"
        )
    for col in ["accuracy", "fl_precision", "recall", "f1", "fraud_rate"]:
        if col in tdf.columns:
            tdf[col] = tdf[col].apply(lambda x: f"{x:.4f}" if x is not None and x == x else "N/A")
    if "artifact_path" in tdf.columns:
        tdf["artifact_path"] = tdf["artifact_path"].apply(
            lambda x: str(x)[-30:] + "..." if x and len(str(x)) > 30 else str(x) if x else "N/A"
        )

    display_cols = ["round_id", "global_version", "created_at", "aggregated_agencies",
                    "accuracy", "f1", "recall", "fl_precision", "fraud_rate", "artifact_path"]
    available = [c for c in display_cols if c in tdf.columns]
    col_names = {
        "round_id": "Round ID", "global_version": "Global Version", "created_at": "Date",
        "aggregated_agencies": "Agences", "accuracy": "Accuracy", "f1": "F1",
        "recall": "Recall", "fl_precision": "Precision", "fraud_rate": "Fraud Rate",
        "artifact_path": "Artifact",
    }

    table = dash_table.DataTable(
        columns=[{"name": col_names.get(c, c), "id": c} for c in available],
        data=tdf[available].sort_values("global_version", ascending=False).to_dict("records") if "global_version" in tdf.columns else tdf[available].to_dict("records"),
        page_size=5,
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

    return latest_card, fig_prog, fig_radar, table, create_live_badge(now)
