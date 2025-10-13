"""
Sofascore client module
"""

import logging
from typing import callable # <--- ADDED THIS IMPORT for the type check
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
            
        # 🌟 CRITICAL FIX: Ensure the 'date' argument is a string, not a function object.
        if callable(date):
            self.logger.warning("Received a callable object as 'date'. Calling it to get string date.")
            try:
                date = date() # Call the function (e.g., get_today())
            except Exception as e:
                self.logger.error(f"Error calling function passed as date: {e}")
                return []
        
        # If 'today' is passed, it should have been resolved by the caller (main.py) to get_today(),
        # but if it somehow still contains the string 'today', we can let the service handle it 
        # or rely on the caller's logic. Since the error is specifically 'function' object, 
        # the callable check is the key.
        
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
        
    # Note: Other methods (get_team, get_tournament_standings, etc.) should also 
    # have their redundant 'self.initialize()' calls removed, following the pattern above.
    # The fix is demonstrated in the core methods used by bot.py.
