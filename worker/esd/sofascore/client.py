# esd/sofascore/client.py

"""
Sofascore client module
"""

import logging
from typing import Optional, Dict, Any # Keep 'Optional', 'Dict', 'Any' for type hints

from .service import SofascoreService
from .types import (
    Event,
    Player,
    Tournament,
    Team,
    Category,
    EntityType,
    # 🟢 INTEGRATION: Import TeamTournamentStats and parser
    TeamTournamentStats,
    parse_team_tournament_stats, 
)


class SofascoreClient:
    """
    A client to interact with the SofaScore service.
    """

    def __init__(self, browser_path: str = None):
        """
        Initializes the Sofascore client.
        """
        self.logger = logging.getLogger(__name__)
        self.service: Optional[SofascoreService] = None # Use Optional for clarity
        self.browser_path = browser_path
        self.__initialized = False
        self.logger.info("SofascoreClient initialized (service pending).")

    def initialize(self):
        """
        Explicitly initializes the underlying service and resources.
        """
        if self.service is None:
            self.service = SofascoreService(self.browser_path)
            self.__initialized = True
            self.logger.info("SofascoreService successfully initialized.")
        else:
            self.logger.warning("SofascoreService already initialized.")


    def close(self):
        """
        Closes the underlying service and releases resources (Playwright).
        """
        if self.service:
            self.service.close()
            self.service = None
            self.__initialized = False
            self.logger.info("SofascoreClient resources closed.")

    # --- Data Retrieval Methods ---

    def get_events(self, date: str = 'today', live: bool = False) -> list[Event]:
        """
        Get events for a specific date or all live events.
        """
        if not self.service:
            self.logger.error("Service not initialized. Cannot fetch events.")
            return []
            
        if live:
            return self.service.get_live_events()
            
        # ✅ FIX: Use the built-in callable() function
        if callable(date):
            self.logger.warning("Received a callable object as 'date'. Calling it to get string date.")
            try:
                # Call the function (e.g., get_today())
                date = date() 
            except Exception as e:
                self.logger.error(f"Error calling function passed as date: {e}")
                return []
        
        return self.service.get_events(date)

    def search(self, query: str, entity: EntityType = EntityType.ALL) -> list[Event | Team | Player | Tournament]:
        """
        Search query for matches, teams, players, and tournaments.
        """
        if not self.service:
            self.logger.error("Service not initialized. Cannot search.")
            return []
            
        return self.service.search(query, entity)

    def get_event(self, event_id: int) -> Optional[Event]:
        """
        Get the event information.
        """
        if not self.service:
            self.logger.error("Service not initialized. Cannot get event.")
            return None
            
        return self.service.get_event(event_id)
    
    def get_player(self, player_id: int) -> Optional[Player]:
        """
        Get the player information.
        """
        if not self.service:
            self.logger.error("Service not initialized. Cannot get player.")
            return None
            
        return self.service.get_player(player_id)

    # 🟢 INTEGRATION: New method for fetching team statistics
    def get_team_tournament_stats(self, team_id: int, tournament_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the raw season statistics (including average goals) for a team 
        in a specific tournament by delegating the call to the service.

        Note: The parsing from raw JSON to TeamTournamentStats is handled
        in bot.py using the separate parse_team_tournament_stats function.
        """
        if not self.service:
            self.logger.error("Service not initialized. Cannot get team stats.")
            return None
            
        # The service returns the raw dictionary data
        return self.service.get_team_tournament_stats(team_id, tournament_id)
