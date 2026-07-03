# flowguard_dashboard/components/navbar.py
# ─── Sidebar fixe + header navigation ───

from dash import html, dcc
import dash_bootstrap_components as dbc

from core.config import APP_VERSION


def create_sidebar():
    """
    Sidebar fixe à gauche avec navigation, badge LIVE,
    et indicateur de statut Neo4j.
    """
    nav_items = [
        {"label": "Overview",            "icon": "bi-house-door-fill", "href": "/"},
        {"label": "Alertes",             "icon": "bi-exclamation-triangle-fill", "href": "/alerts"},
        {"label": "Modèles Locaux",      "icon": "bi-cpu-fill", "href": "/local-models"},
        {"label": "Federated Learning",  "icon": "bi-globe2", "href": "/federated"},
        {"label": "Transactions",        "icon": "bi-search", "href": "/transactions"},
    ]

    nav_links = []
    for item in nav_items:
        nav_links.append(
            dbc.NavLink(
                children=[
                    html.I(className=f"bi {item['icon']} nav-link-icon"),
                    html.Span(item["label"]),
                ],
                href=item["href"],
                className="sidebar-link",
                active="exact",
            )
        )

    sidebar = html.Div(
        id="sidebar",
        className="sidebar",
        children=[
            # ─── Logo + titre ───
            html.Div(
                className="sidebar-brand",
                children=[
                    html.Div(
                        className="sidebar-logo",
                        children=[
                            html.Span("🛡️", style={"fontSize": "1.8rem"}),
                            html.Div([
                                html.H4("FlowGuard", className="brand-title"),
                                html.Span("Fraud Detection", className="brand-subtitle"),
                            ]),
                        ],
                    ),
                    # ─── Badge LIVE ───
                    html.Div(
                        className="sidebar-live",
                        children=[
                            html.Span(className="live-dot-sidebar"),
                            html.Span("LIVE", className="live-text-sidebar"),
                        ],
                    ),
                ],
            ),
            html.Hr(className="sidebar-divider"),
            # ─── Navigation ───
            dbc.Nav(
                nav_links,
                vertical=True,
                pills=True,
                className="sidebar-nav",
            ),
            # ─── Footer ───
            html.Div(
                className="sidebar-footer",
                children=[
                    html.Hr(className="sidebar-divider"),
                    html.Div(
                        className="sidebar-status",
                        children=[
                            html.Span(id="neo4j-status-dot", className="status-dot status-green"),
                            html.Span("Neo4j Connected", id="neo4j-status-text", className="status-text"),
                        ],
                    ),
                    html.Small(f"v{APP_VERSION}", className="sidebar-version"),
                ],
            ),
        ],
    )
    return sidebar
