# esd/sofascore/types/team_stats.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging

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
    
    # Raw data for inspection
    raw_data: Optional[Dict[str, Any]] = None


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
    
    # Navigate the nested JSON structure to find the "overall" stats
    try:
        # Assuming the 'total' statistics block holds the season aggregate
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

