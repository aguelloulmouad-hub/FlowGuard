# flowguard_dashboard/components/kpi_card.py
# ─── Composant réutilisable KPI Card avec effet glassmorphism ───

from dash import html
import dash_bootstrap_components as dbc


def create_kpi_card(title, value, icon, color, subtitle=None):
    """
    Crée une carte KPI avec effet glassmorphism.

    Args:
        title: Titre du KPI
        value: Valeur affichée (string ou nombre)
        icon: Classe Bootstrap Icons (ex: "bi-graph-up")
        color: Couleur d'accent (hex)
        subtitle: Sous-titre optionnel
    """
    display_value = value if value is not None else "N/A"
    if isinstance(display_value, float):
        if display_value != display_value:  # NaN check
            display_value = "N/A"
        else:
            display_value = f"{display_value:.2f}"

    card_children = [
        html.Div(
            className="kpi-card-header",
            children=[
                html.Div(
                    className="kpi-icon-wrapper",
                    style={"background": f"linear-gradient(135deg, {color}33, {color}11)"},
                    children=[
                        html.I(className=f"bi {icon}", style={"color": color, "fontSize": "1.5rem"}),
                    ],
                ),
                html.Div(
                    className="kpi-info",
                    children=[
                        html.P(title, className="kpi-title"),
                        html.H3(str(display_value), className="kpi-value", style={"color": color}),
                    ],
                ),
            ],
        ),
    ]

    if subtitle:
        card_children.append(
            html.Div(
                className="kpi-subtitle",
                children=[html.Small(subtitle)],
            )
        )

    return dbc.Card(
        dbc.CardBody(card_children, className="kpi-card-body"),
        className="kpi-card",
    )
