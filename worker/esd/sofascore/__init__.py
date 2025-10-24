# esd/sofascore/__init__.py

"""
Sofascore module (The package front door)
"""

# Import the main client class
from .client import SofascoreClient 

# Import and expose all the necessary data structures from the .types submodule
from .types import (
    Event,
    Team,
    Player,
    TransferHistory,
    PlayerAttributes,
    MatchStats,
    Lineups,
    Incident,
    TopPlayersMatch,
    Comment,
    Shot,
    Tournament,
    Season,
    Bracket,
    Standing,
    TopTournamentTeams,
    TopTournamentPlayers,
    EntityType,
    Category,
    TeamTournamentStats, 
    parse_team_tournament_stats,
)

# Import the entire types submodule (for users who want to access other types)
from . import types

# Update __all__ to include the symbols you want to expose at the package level
__all__ = [
    "SofascoreClient", 
    "EntityType",
    "TeamTournamentStats",
    "parse_team_tournament_stats",
    "types"
]
