# flowguard_dashboard/components/live_badge.py
# ─── Badge LIVE clignotant + timestamp de dernière mise à jour ───

from dash import html
from datetime import datetime


def create_live_badge(last_updated=None):
    """
    Composant affichant un badge LIVE clignotant et le timestamp
    de la dernière mise à jour.
    """
    if last_updated is None:
        last_updated = datetime.now()

    if isinstance(last_updated, str):
        try:
            last_updated = datetime.fromisoformat(last_updated)
        except (ValueError, TypeError):
            last_updated = datetime.now()

    time_str = last_updated.strftime("%H:%M:%S")

    return html.Div(
        className="live-badge-container",
        children=[
            html.Span(
                className="live-badge",
                children=[
                    html.Span(className="live-dot"),
                    html.Span("LIVE", className="live-text"),
                ],
            ),
            html.Span(
                f"Dernière mise à jour : {time_str}",
                className="live-timestamp",
            ),
        ],
    )
