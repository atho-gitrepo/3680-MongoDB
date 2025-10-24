# esd/sofascore/types/__init__.py

"""
Contains the types for the Sofascore service.
"""

from .event import Event, parse_events, parse_event
# ... (all other imports) ...
from .entity import EntityType
from .categories import Category
# 🟢 INTEGRATION: Import the team tournament stats data structure
from .team_stats import TeamTournamentStats, parse_team_tournament_stats 


__all__ = [
    # ... (all other symbols) ...
    "EntityType",
    "Category",
    "StatusType",
    "Status",
    # 🟢 INTEGRATION: Add the team tournament stats to the exported symbols
    "TeamTournamentStats",
    "parse_team_tournament_stats",
]
