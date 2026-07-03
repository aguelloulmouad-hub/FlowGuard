# flowguard_dashboard/components/empty_state.py
# ─── Composant placeholder "En attente de données..." ───

from dash import html


def create_empty_state(message="En attente de données...", icon="bi-hourglass-split"):
    """
    Composant centré avec icône animée et message informatif.
    Affiché lorsqu'aucune donnée n'est disponible.
    """
    return html.Div(
        className="empty-state-container",
        children=[
            html.Div(
                className="empty-state-icon",
                children=[html.I(className=f"bi {icon}")],
            ),
            html.P(message, className="empty-state-text"),
            html.P(
                "Les données apparaîtront automatiquement dès que le pipeline sera actif.",
                className="empty-state-subtext",
            ),
        ],
    )
