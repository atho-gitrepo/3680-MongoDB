# esd/sofascore/types/team.py

"""
This module contains the Team related data classes and statistics.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import logging
from .country import Country, parse_country
from .color import Color, parse_color
from .manager import Manager, parse_manager

logger = logging.getLogger(__name__)

@dataclass
class TeamTournamentStats:
    """
    Represents a team's season-long statistics in a specific tournament (league).
    Used primarily for the average goals filter.
    """
    team_id: int
    tournament_id: int
    matches_played: int = 0
    goals_scored_total: float = 0.0
    goals_conceded_total: float = 0.0
    goals_scored_average: float = 0.0
    goals_conceded_average: float = 0.0
    total_average_goals: float = 0.0
    raw_data: Optional[Dict[str, Any]] = None

@dataclass
class Team:
    """
    A class to represent a team.
    """

    name: str = field(default=None)
    short_name: str = field(default=None)
    slug: str = field(default=None)
    name_code: str = field(default=None)
    entity_type: str = field(default=None)
    id: int = field(default=0)
    country: Country = field(default_factory=Country)
    color: Color = field(default_factory=Color)
    manager: Optional[Manager] = field(default_factory=Manager)
    players: Optional[list] = field(default_factory=list)


def parse_common_team_fields(data: dict) -> dict:
    """
    Parse common team fields.
    """
    return {
        "name": data.get("name"),
        "short_name": data.get("shortName"),
        "slug": data.get("slug"),
        "name_code": data.get("nameCode"),
        "id": data.get("id", 0),
        "entity_type": data.get("entityType"),
        "country": parse_country(data.get("country", {})),
        "color": parse_color(data.get("teamColors", {})),
    }


def parse_team(data: dict) -> Team:
    """
    Parse team data.
    """
    common = parse_common_team_fields(data)
    team = Team(**common)
    if "manager" in data:
        team.manager = parse_manager(data.get("manager", {}))
    return team

def parse_team_tournament_stats(
    team_id: int, 
    tournament_id: int, 
    data: Dict[str, Any]
) -> TeamTournamentStats:
    """
    Parses the raw JSON data from the team tournament stats endpoint 
    into a TeamTournamentStats object.
    """
    
    stats = TeamTournamentStats(
        team_id=team_id, 
        tournament_id=tournament_id, 
        raw_data=data
    )
    
    try:
        stat_blocks = data.get("statistics", {}).get("total", [])
        
        overall_stats = next(
            (block for block in stat_blocks if block.get("type") == "overall"),
            None
        )

        if not overall_stats:
            logger.warning(
                f"Stats for team {team_id} in tournament {tournament_id} found but 'overall' block is missing."
            )
            return stats
            
        stats.matches_played = overall_stats.get("matches", 0)

        if stats.matches_played == 0:
            return stats

        stats.goals_scored_total = float(overall_stats.get("goalsScored", 0))
        stats.goals_conceded_total = float(overall_stats.get("goalsConceded", 0))
        
        # Calculate Averages
        stats.goals_scored_average = stats.goals_scored_total / stats.matches_played
        stats.goals_conceded_average = stats.goals_conceded_total / stats.matches_played
        stats.total_average_goals = stats.goals_scored_average + stats.goals_conceded_average
        
        return stats

    except Exception as exc:
        logger.error(
            f"Error parsing TeamTournamentStats for Team {team_id} (Tournament {tournament_id}): {exc}",
            exc_info=True
        )
        return stats
