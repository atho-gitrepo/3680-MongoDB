"""
SofaScore Standing dataclass.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from .tournament import Tournament, parse_tournament
from .team import Team, parse_team

logger = logging.getLogger(__name__)

@dataclass
class StandingItem:
    """
    StandingItem dataclass
    """
    # Use Optional[int] and default=None for fields that might be missing
    id: Optional[int] = field(default=None)
    team: Optional[Team] = field(default=None)
    descriptions: List[str] = field(default_factory=list)
    promotion: Dict[str, Any] = field(default_factory=dict)
    
    # Statistical fields are now Optional[int]
    position: Optional[int] = field(default=None)
    matches: Optional[int] = field(default=None)
    wins: Optional[int] = field(default=None)
    scores_for: Optional[int] = field(default=None)
    scores_against: Optional[int] = field(default=None)
    losses: Optional[int] = field(default=None)
    draws: Optional[int] = field(default=None)
    points: Optional[int] = field(default=None)
    
    score_diff_formatted: Optional[str] = field(default=None)


def parse_standing_item(data: dict) -> StandingItem:
    """
    Parse standing item data.

    Args:
        data (dict): Standing item data.

    Returns:
        StandingItem: Standing item dataclass
    """
    # Use .get() without a default of 0 to return None if the key is missing
    return StandingItem(
        id=data.get("id"),
        team=parse_team(data.get("team", {})),
        descriptions=data.get("descriptions", []),
        promotion=data.get("promotion", {}),
        position=data.get("position"),
        matches=data.get("matches"),
        wins=data.get("wins"),
        scores_for=data.get("scoresFor"),
        scores_against=data.get("scoresAgainst"),
        losses=data.get("losses"),
        draws=data.get("draws"),
        points=data.get("points"),
        score_diff_formatted=data.get("scoreDiffFormatted"),
    )


def parse_standing_items(data: list) -> List[StandingItem]:
    """
    Parse standing item data.

    Args:
        data (list): List of Standing item data.

    Returns:
        List[StandingItem]: List of Standing item dataclass
    """
    # Defensive check to ensure we are iterating over a list
    if not isinstance(data, list):
        logger.warning(f"Expected a list for standing items data, got {type(data)}")
        return []
        
    return [parse_standing_item(standing_item) for standing_item in data]


@dataclass
class Standing:
    """Standing dataclass"""

    id: Optional[int] = field(default=None)
    name: Optional[str] = field(default=None)
    tournament: Optional[Tournament] = field(default=None)
    last_updated: Optional[int] = field(default=None)
    items: List[StandingItem] = field(default_factory=list)
    # description: str = field(default=None)


def parse_standing(data: dict) -> Standing:
    """
    Parse standing data.

    Args:
        data (dict): Standing data.

    Returns:
        Standing: Standing dataclass
    """
    # Get 'rows' and ensure it's a list for parsing
    standing_items_data = data.get("rows", [])
    if not isinstance(standing_items_data, list):
        standing_items_data = []
        logger.warning(f"Unexpected data type for standing rows: {type(data.get('rows'))}")
        
    return Standing(
        id=data.get("id"),
        name=data.get("name"),
        tournament=parse_tournament(data.get("tournament", {})),
        last_updated=data.get("updatedAtTimestamp"),
        items=parse_standing_items(standing_items_data),
        # description=data.get("description"),
    )


def parse_standings(data: list) -> List[Standing]:
    """
    Parse standing data.

    Args:
        data (list): List of Standing data.

    Returns:
        List[Standing]: List of Standing dataclass
    """
    # Defensive check to ensure the top level is a list of standings
    if not isinstance(data, list):
        logger.error(f"Expected a list for standings data, got {type(data)}")
        return []
        
    return [parse_standing(standing) for standing in data]
