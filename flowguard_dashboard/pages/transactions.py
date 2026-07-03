# flowguard_dashboard/pages/transactions.py
# ─── Page 5 : Analyse Transactions ───

import dash
from dash import html, dcc, callback, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from core.neo4j_loader import loader
from core.config import (
    AGENCY_COLORS, AGENCY_KEY_TO_DISPLAY, PLOTLY_TEMPLATE,
    PAPER_BG, PLOT_BG, REFRESH_INTERVAL, DAY_LABELS,
)
from components.live_badge import create_live_badge
from components.empty_state import create_empty_state

dash.register_page(__name__, path="/transactions", name="Transactions", order=4)


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


# ─── Layout ───

layout = html.Div([
    dcc.Interval(id="txn-interval", interval=REFRESH_INTERVAL, n_intervals=0),

    html.Div(className="page-header", children=[
        html.H2("🔍 Analyse Transactions", className="page-title"),
        html.Div(id="txn-live-badge"),
    ]),

    # Row 1 — Filters
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.H6("Filtres", className="card-section-title"),
                dbc.Row([
                    dbc.Col([
                        html.Label("Agence", className="filter-label"),
                        dcc.Dropdown(
                            id="txn-filter-agency",
                            options=[
                                {"label": "Toutes", "value": "All"},
                                {"label": "Agency A", "value": "Agency_A"},
                                {"label": "Agency B", "value": "Agency_B"},
                                {"label": "Agency C", "value": "Agency_C"},
                            ],
                            value="All",
                            clearable=False,
                            className="filter-dropdown",
                        ),
                    ], lg=2, md=4, xs=6),
                    dbc.Col([
                        html.Label("Fraude", className="filter-label"),
                        dcc.Dropdown(
                            id="txn-filter-fraud",
                            options=[
                                {"label": "Toutes", "value": "All"},
                                {"label": "Fraude", "value": "Fraude"},
                                {"label": "Normal", "value": "Normal"},
                            ],
                            value="All",
                            clearable=False,
                            className="filter-dropdown",
                        ),
                    ], lg=2, md=4, xs=6),
                    dbc.Col([
                        html.Label("En ligne", className="filter-label"),
                        dcc.Dropdown(
                            id="txn-filter-online",
                            options=[
                                {"label": "Toutes", "value": "All"},
                                {"label": "Oui", "value": "Oui"},
                                {"label": "Non", "value": "Non"},
                            ],
                            value="All",
                            clearable=False,
                            className="filter-dropdown",
                        ),
                    ], lg=2, md=4, xs=6),
                    dbc.Col([
                        html.Label("Étranger", className="filter-label"),
                        dcc.Dropdown(
                            id="txn-filter-foreign",
                            options=[
                                {"label": "Toutes", "value": "All"},
                                {"label": "Oui", "value": "Oui"},
                                {"label": "Non", "value": "Non"},
                            ],
                            value="All",
                            clearable=False,
                            className="filter-dropdown",
                        ),
                    ], lg=2, md=4, xs=6),
                    dbc.Col([
                        html.Label("Montant", className="filter-label"),
                        dcc.RangeSlider(
                            id="txn-filter-amount",
                            min=0, max=50000, step=100,
                            value=[0, 50000],
                            marks={0: "0", 10000: "10K", 25000: "25K", 50000: "50K"},
                            tooltip={"placement": "bottom", "always_visible": False},
                        ),
                    ], lg=3, md=6, xs=12),
                    dbc.Col([
                        html.Label("\u00a0", className="filter-label"),
                        html.Div([
                            dbc.Button(
                                [html.I(className="bi bi-funnel-fill me-1"), "Appliquer"],
                                id="txn-apply-filters",
                                className="filter-button",
                            ),
                        ]),
                    ], lg=1, md=2, xs=6),
                ], className="g-2 align-items-end"),
            ]), className="chart-card"),
            width=12,
        ),
    ], className="g-3 mb-4"),

    # Row 2 — Transactions Table
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.H6("Transactions", className="card-section-title"),
                html.Div(id="txn-table-container"),
            ]), className="chart-card"),
            width=12,
        ),
    ], className="g-3 mb-4"),

    # Row 3 — Heatmap + Boxplot
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id="txn-heatmap", config={"displayModeBar": False})),
                     className="chart-card"),
            lg=6, md=12,
        ),
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id="txn-boxplot", config={"displayModeBar": False})),
                     className="chart-card"),
            lg=6, md=12,
        ),
    ], className="g-3 mb-4"),

    # Row 4 — Top categories + Sunburst
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id="txn-top-categories", config={"displayModeBar": False})),
                     className="chart-card"),
            lg=7, md=12,
        ),
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id="txn-sunburst", config={"displayModeBar": False})),
                     className="chart-card"),
            lg=5, md=12,
        ),
    ], className="g-3 mb-4"),
])


# ─── Callbacks ───

@callback(
    Output("txn-table-container", "children"),
    Output("txn-live-badge", "children"),
    Input("txn-apply-filters", "n_clicks"),
    Input("txn-interval", "n_intervals"),
    State("txn-filter-agency", "value"),
    State("txn-filter-fraud", "value"),
    State("txn-filter-online", "value"),
    State("txn-filter-foreign", "value"),
    State("txn-filter-amount", "value"),
)
def update_txn_table(_clicks, _n, agency, fraud, online, foreign, amount_range):
    now = datetime.now()
    amount_min = amount_range[0] if amount_range and amount_range[0] > 0 else None
    amount_max = amount_range[1] if amount_range and amount_range[1] < 50000 else None

    df = loader.get_transactions_filtered(
        agency=agency, is_fraud=fraud, is_online=online,
        is_foreign=foreign, amount_min=amount_min, amount_max=amount_max,
        limit=200,
    )

    if df.empty:
        return create_empty_state("Aucune transaction trouvée", "bi-search"), create_live_badge(now)

    tdf = df.copy()
    if "agency" in tdf.columns:
        tdf["agency"] = tdf["agency"].map(AGENCY_KEY_TO_DISPLAY).fillna(tdf["agency"])
    if "amount" in tdf.columns:
        tdf["amount"] = tdf["amount"].apply(lambda x: f"{x:,.2f}" if x is not None and x == x else "N/A")
    if "score" in tdf.columns:
        tdf["score"] = tdf["score"].apply(lambda x: f"{x:.4f}" if x is not None and x == x else "—")
    if "prediction" in tdf.columns:
        tdf["prediction"] = tdf["prediction"].apply(
            lambda x: "Fraud" if x == 1 else ("Normal" if x == 0 else "—")
        )
    if "is_fraud" in tdf.columns:
        tdf["is_fraud_display"] = tdf["is_fraud"].apply(
            lambda x: "✅ Oui" if x in [True, 1] else ("❌ Non" if x in [False, 0] else "—")
        )
    if "is_online" in tdf.columns:
        tdf["is_online"] = tdf["is_online"].apply(lambda x: "Oui" if x in [True, 1] else "Non")
    if "is_foreign" in tdf.columns:
        tdf["is_foreign"] = tdf["is_foreign"].apply(lambda x: "Oui" if x in [True, 1] else "Non")
    if "timestamp" in tdf.columns:
        tdf["timestamp"] = tdf["timestamp"].apply(
            lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if hasattr(x, "strftime") else str(x)[:19] if x else "N/A"
        )

    display_cols = ["transaction_id", "agency", "amount", "merchant_category", "location",
                    "hour_of_day", "is_online", "is_foreign", "score", "prediction",
                    "is_fraud_display", "timestamp"]
    available = [c for c in display_cols if c in tdf.columns]
    col_names = {
        "transaction_id": "Txn ID", "agency": "Agence", "amount": "Montant",
        "merchant_category": "Catégorie", "location": "Lieu", "hour_of_day": "Heure",
        "is_online": "En Ligne", "is_foreign": "Étranger", "score": "Score",
        "prediction": "Prédiction", "is_fraud_display": "Fraude", "timestamp": "Timestamp",
    }

    # Build conditional styles for fraud rows
    style_conditions = []
    if "is_fraud" in df.columns:
        fraud_ids = df[df["is_fraud"].isin([True, 1])].index.tolist()
        if fraud_ids:
            style_conditions.append({
                "if": {"filter_query": '{is_fraud_display} contains "Oui"'},
                "backgroundColor": "rgba(255,68,68,0.12)",
            })

    table = dash_table.DataTable(
        columns=[{"name": col_names.get(c, c), "id": c} for c in available],
        data=tdf[available].to_dict("records"),
        page_size=15,
        sort_action="native",
        export_format="csv",
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#161b22", "color": "#e6edf3",
            "fontWeight": "600", "border": "1px solid #30363d", "fontSize": "11px",
        },
        style_cell={
            "backgroundColor": "#0d1117", "color": "#c9d1d9",
            "border": "1px solid #21262d", "fontSize": "11px",
            "padding": "6px 10px", "fontFamily": "Inter, sans-serif",
            "textAlign": "left", "maxWidth": "150px", "overflow": "hidden",
            "textOverflow": "ellipsis",
        },
        style_data_conditional=style_conditions,
    )

    return table, create_live_badge(now)


@callback(
    Output("txn-heatmap", "figure"),
    Output("txn-boxplot", "figure"),
    Output("txn-top-categories", "figure"),
    Output("txn-sunburst", "figure"),
    Input("txn-interval", "n_intervals"),
)
def update_txn_charts(_n):
    empty_fig = go.Figure()
    _chart_layout(empty_fig, "Aucune donnée")

    # ── Heatmap ──
    df_heat = loader.get_heatmap_data()
    if df_heat.empty:
        fig_heat = go.Figure()
        _chart_layout(fig_heat, "Heatmap Transactions")
    else:
        pivot = df_heat.pivot_table(index="hour_of_day", columns="day_of_week", values="cnt", fill_value=0)
        # Ensure all days and hours are present
        all_hours = list(range(24))
        all_days = list(range(7))
        pivot = pivot.reindex(index=all_hours, columns=all_days, fill_value=0)

        day_labels = [DAY_LABELS.get(d, str(d)) for d in all_days]

        fig_heat = go.Figure(go.Heatmap(
            z=pivot.values,
            x=day_labels,
            y=[f"{h:02d}h" for h in all_hours],
            colorscale=[[0, "#0d1117"], [0.5, "#1f6feb"], [1, "#da3633"]],
            hovertemplate="Jour: %{x}<br>Heure: %{y}<br>Transactions: %{z}<extra></extra>",
        ))
        _chart_layout(fig_heat, "Fréquence Transactions (Heure × Jour)")
        fig_heat.update_yaxes(autorange="reversed")

    # ── Boxplot ──
    df_box = loader.get_amount_boxplot()
    if df_box.empty:
        fig_box = go.Figure()
        _chart_layout(fig_box, "Distribution Montants")
    else:
        fig_box = go.Figure()
        for agency_key, color in AGENCY_COLORS.items():
            display = AGENCY_KEY_TO_DISPLAY.get(agency_key, agency_key)
            for is_fraud_val, fraud_label in [(False, "Normal"), (True, "Fraud")]:
                mask = (df_box["agency"] == agency_key) & (df_box["is_fraud"].isin([is_fraud_val, int(is_fraud_val)]))
                subset = df_box[mask]
                if subset.empty:
                    continue
                fig_box.add_trace(go.Box(
                    y=subset["amount"],
                    name=f"{display} ({fraud_label})",
                    marker_color=color,
                    opacity=0.8 if fraud_label == "Normal" else 1.0,
                    line=dict(width=1.5 if fraud_label == "Fraud" else 1),
                    boxpoints="outliers",
                ))
        _chart_layout(fig_box, "Distribution Montants par Agence × Statut")
        fig_box.update_yaxes(title_text="Montant")

    # ── Top merchant categories ──
    df_cats = loader.get_top_merchant_categories()
    if df_cats.empty:
        fig_cats = go.Figure()
        _chart_layout(fig_cats, "Top Catégories")
    else:
        df_cats_sorted = df_cats.sort_values("txn_count", ascending=True)
        fig_cats = go.Figure()
        # Bars for transaction count
        fig_cats.add_trace(go.Bar(
            y=df_cats_sorted["category"],
            x=df_cats_sorted["txn_count"],
            orientation="h",
            name="Transactions",
            marker_color="#00D4FF",
            opacity=0.8,
        ))
        # Line for fraud rate on secondary axis
        fig_cats.add_trace(go.Scatter(
            y=df_cats_sorted["category"],
            x=df_cats_sorted["fraud_rate"].apply(lambda x: x * 100 if x is not None and x == x else 0),
            mode="lines+markers",
            name="Fraud Rate (%)",
            line=dict(color="#FF4444", width=2),
            marker=dict(size=7),
            xaxis="x2",
        ))
        _chart_layout(fig_cats, "Top 10 Catégories Marchands")
        fig_cats.update_layout(
            xaxis=dict(title="Nombre de Transactions", side="bottom"),
            xaxis2=dict(title="Fraud Rate (%)", side="top", overlaying="x",
                        range=[0, 100], showgrid=False),
            barmode="overlay",
        )

    # ── Sunburst ──
    df_sun = loader.get_transactions_filtered(limit=500)
    if df_sun.empty or "agency" not in df_sun.columns:
        fig_sun = go.Figure()
        _chart_layout(fig_sun, "Répartition")
    else:
        sun_df = df_sun.copy()
        sun_df["agency_display"] = sun_df["agency"].map(AGENCY_KEY_TO_DISPLAY).fillna(sun_df["agency"])
        sun_df["fraud_label"] = sun_df["is_fraud"].apply(
            lambda x: "Fraud" if x in [True, 1] else "Normal"
        )
        if "merchant_category" not in sun_df.columns:
            sun_df["merchant_category"] = "Unknown"

        # Build sunburst data
        labels, parents, values, colors = [], [], [], []

        # Level 1: Agencies
        for ag_display in sun_df["agency_display"].unique():
            ag_count = len(sun_df[sun_df["agency_display"] == ag_display])
            labels.append(ag_display)
            parents.append("")
            values.append(ag_count)
            ag_key = [k for k, v in AGENCY_KEY_TO_DISPLAY.items() if v == ag_display]
            colors.append(AGENCY_COLORS.get(ag_key[0], "#888") if ag_key else "#888")

            # Level 2: Fraud status
            for fraud_label in ["Normal", "Fraud"]:
                subset = sun_df[(sun_df["agency_display"] == ag_display) & (sun_df["fraud_label"] == fraud_label)]
                fl_count = len(subset)
                if fl_count == 0:
                    continue
                node_name = f"{ag_display} - {fraud_label}"
                labels.append(node_name)
                parents.append(ag_display)
                values.append(fl_count)
                colors.append("#FF4444" if fraud_label == "Fraud" else "#00FF88")

                # Level 3: Merchant category
                for cat in subset["merchant_category"].value_counts().head(5).index:
                    cat_count = len(subset[subset["merchant_category"] == cat])
                    cat_name = f"{node_name} - {cat}"
                    labels.append(cat_name)
                    parents.append(node_name)
                    values.append(cat_count)
                    colors.append("#30363d")

        fig_sun = go.Figure(go.Sunburst(
            labels=labels,
            parents=parents,
            values=values,
            marker=dict(colors=colors),
            branchvalues="total",
            textfont=dict(size=10),
            hovertemplate="<b>%{label}</b><br>Count: %{value}<extra></extra>",
        ))
        _chart_layout(fig_sun, "Agency → Fraude → Catégorie")
        fig_sun.update_layout(margin=dict(t=50, l=10, r=10, b=10))

    return fig_heat, fig_box, fig_cats, fig_sun
