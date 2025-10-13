"""
Sofascore client module
"""

import logging
# REMOVE: from typing import callable 
# 'callable' is a built-in function, not a member of the typing module.

from .service import SofascoreService
from .types import (
    Event,
    Player,
    Tournament,
    Team,
    Category,
    EntityType,
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
        self.service: SofascoreService | None = None
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
            
        # ✅ FIX: Use the built-in callable() without importing it.
        if callable(date):
            self.logger.warning("Received a callable object as 'date'. Calling it to get string date.")
            try:
                date = date() # Call the function (e.g., get_today())
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

    def get_event(self, event_id: int) -> Event:
        """
        Get the event information.
        """
        if not self.service:
            self.logger.error("Service not initialized. Cannot get event.")
            return None
            
        return self.service.get_event(event_id)
    
    def get_player(self, player_id: int) -> Player:
        """
        Get the player information.
        """
        if not self.service:
            self.logger.error("Service not initialized. Cannot get player.")
            return None
            
        return self.service.get_player(player_id)
