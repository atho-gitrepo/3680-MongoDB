# esd/sofascore/endpoints.py

"""
This module contains the endpoints of the SofaScore API, generalized to support
different sports/categories.
"""

from typing import Union

class SofascoreEndpoints:
    """
    A class to represent the endpoints of the SofaScore API.
    """

    def __init__(self, base_url: str = "https://api.sofascore.com/api/v1") -> None:
        self.base_url = base_url

    # --- Category/Sport Endpoints ---

    def categories_endpoint(self) -> str:
        """
        Returns the URL of the endpoint to get all available sports/categories.
        """
        return self.base_url + "/sport/all/categories"
        
    def events_endpoint(self, category_name: str) -> str:
        """
        Returns the URL of the endpoint to get the scheduled events for a specific category.

        Args:
            category_name (str): The name of the sport/category (e.g., 'football', 'basketball').

        Returns:
            str: The URL of the endpoint with a {date} placeholder.
        """
        return f"{self.base_url}/sport/{category_name}/scheduled-events/{{date}}"

    def live_events_endpoint(self, category_name: str) -> str:
        """
        Returns the URL of the endpoint to get the live events for a specific category.

        Args:
            category_name (str): The name of the sport/category (e.g., 'football', 'basketball').

        Returns:
            str: The URL of the endpoint to get the live events.
        """
        return f"{self.base_url}/sport/{category_name}/events/live"
    
    # --- Event Endpoints ---

    def event_endpoint(self, event_id: int) -> str:
        """
        Returns the URL of the endpoint to get the event information.

        Args:
            event_id (int): The event id.

        Returns:
            str: The URL of the endpoint to get the event information.
        """
        return f"{self.base_url}/event/{event_id}"

    def match_stats_endpoint(self, event_id: int) -> str:
        """
        Returns the URL of the endpoint to get the match statistics.

        Args:
            event_id (int): The event id.

        Returns:
            str: The URL of the endpoint to get the match statistics.
        """
        return f"{self.base_url}/event/{event_id}/statistics"

    def match_events_endpoint(self, event_id: int) -> str:
        """
        Returns the URL of the endpoint to get the match events (incidents).

        Args:
            event_id (int): The event id.

        Returns:
            str: The URL of the endpoint to get the match events.
        """
        return f"{self.base_url}/event/{event_id}/incidents"

    def match_top_players_endpoint(self, event_id: int) -> str:
        """
        Returns the URL of the endpoint to get the top players of a match.

        Args:
            event_id (int): The event id.

        Returns:
            str: The URL of the endpoint to get the top players of a match.
        """
        return f"{self.base_url}/event/{event_id}/best-players/summary"

    def match_comments_endpoint(self, event_id: int) -> str:
        """
        Returns the URL of the endpoint to get the comments of a match.

        Args:
            event_id (int): The event id.

        Returns:
            str: The URL of the endpoint to get the comments of a match.
        """
        return f"{self.base_url}/event/{event_id}/comments"

    def match_shots_endpoint(self, event_id: int) -> str:
        """
        Returns the URL of the endpoint to get the shots of a match.

        Args:
            event_id (int): The event id.

        Returns:
            str: The URL of the endpoint to get the shots of a match.
        """
        return f"{self.base_url}/event/{event_id}/shotmap"

    def match_probabilities_endpoint(self, event_id: int) -> str:
        """
        Returns the URL of the endpoint to get the match probabilities.

        Args:
            event_id (int): The event id.

        Returns:
            str: The URL of the endpoint to get the match probabilities.
        """
        return f"{self.base_url}/event/{event_id}/win-probability"

    def match_lineups_endpoint(self, event_id: int) -> str:
        """
        Returns the URL of the endpoint to get the match lineups.

        Args:
            event_id (int): The event id.

        Returns:
            str: The URL of the endpoint to get the match lineups.
        """
        return f"{self.base_url}/event/{event_id}/lineups"

    # --- Tournament Endpoints ---

    def tournaments_endpoint(self, category_id: int) -> str:
        """
        Returns the URL of the endpoint to get the unique tournaments of a category.

        Args:
            category_id (int): The category id.

        Returns:
            str: The URL of the endpoint to get the unique tournaments of a category.
        """
        return f"{self.base_url}/category/{category_id}/unique-tournaments"

    def tournament_seasons_endpoint(self, tournament_id: int) -> str:
        """
        Returns the URL of the endpoint to get the seasons of a unique tournament.

        Args:
            tournament_id (int): The unique tournament id.

        Returns:
            str: The URL of the endpoint to get the seasons of a tournament.
        """
        return f"{self.base_url}/unique-tournament/{tournament_id}/seasons"

    def tournament_events_endpoint(
        self, tournament_id: int, season_id: int, upcoming: bool, page: int
    ) -> str:
        """
        Returns the URL of the endpoint to get the events of a tournament season.

        Args:
            tournament_id (int): The unique tournament id.
            season_id (int): The season id.
            upcoming (bool): Whether to get the upcoming events.
            page (int, optional): The page number. Defaults to 0.

        Returns:
            str: The URL of the endpoint to get the events of a tournament.
        """
        _from = "last" if not upcoming else "next"
        base = self.base_url + "/unique-tournament"
        return f"{base}/{tournament_id}/season/{season_id}/events/{_from}/{page}"

    def tournament_bracket_endpoint(self, tournament_id: int, season_id: int) -> str:
        """
        Returns the URL of the endpoint to get the cup trees/bracket of a tournament.

        Args:
            tournament_id (int): The unique tournament id.
            season_id (int): The season id.

        Returns:
            str: The URL of the endpoint to get the bracket of a tournament.
        """
        return f"{self.base_url}/unique-tournament/{tournament_id}/season/{season_id}/cuptrees"

    def tournament_standings_endpoint(self, tournament_id: int, season_id: int) -> str:
        """
        Returns the URL of the endpoint to get the standings of a tournament.

        Args:
            tournament_id (int): The unique tournament id.
            season_id (int): The season id.

        Returns:
            str: The URL of the endpoint to get the standings of a tournament.
        """
        base = self.base_url + "/unique-tournament"
        return f"{base}/{tournament_id}/season/{season_id}/standings/total"

    def tournament_topteams_endpoint(self, tournament_id: int, season_id: int) -> str:
        """
        Returns the URL of the endpoint to get the top teams of a tournament.

        Args:
            tournament_id (int): The unique tournament id.
            season_id (int): The season id.

        Returns:
            str: The URL of the endpoint to get the top teams of a tournament.
        """
        base = self.base_url + "/unique-tournament"
        return f"{base}/{tournament_id}/season/{season_id}/top-teams/overall"

    def tournament_topplayers_endpoint(self, tournament_id: int, season_id: int) -> str:
        """
        Returns the URL of the endpoint to get the top players of a tournament.

        Args:
            tournament_id (int): The unique tournament id.
            season_id (int): The season id.

        Returns:
            str: The URL of the endpoint to get the top players of a tournament.
        """
        base = self.base_url + "/unique-tournament"
        return f"{base}/{tournament_id}/season/{season_id}/top-players/overall"

    # --- Team Endpoints ---

    def team_endpoint(self, team_id: int) -> str:
        """
        Returns the URL of the endpoint to get the team information.

        Args:
            team_id (int): The team id.

        Returns:
            str: The URL of the endpoint to get the team information.
        """
        return f"{self.base_url}/team/{team_id}"

    def team_players_endpoint(self, team_id: int) -> str:
        """
        Returns the URL of the endpoint to get the team players.

        Args:
            team_id (int): The team id.

        Returns:
            str: The URL of the endpoint to get the team players.
        """
        return self.team_endpoint(team_id) + "/players"

    def team_events_endpoint(self, team_id: int, upcoming: bool, page: int) -> str:
        """
        Returns the URL of the endpoint to get the team events.

        Args:
            team_id (int): The team id.
            upcoming (bool): Whether to get the upcoming events.
            page (int): The page number.

        Returns:
            str: The URL of the endpoint to get the team events.
        """
        _from = "last" if not upcoming else "next"
        return f"{self.base_url}/team/{team_id}/events/{_from}/{page}"

    # --- Player Endpoints ---

    def player_endpoint(self, player_id: int) -> str:
        """
        Returns the URL of the endpoint to get the player information.

        Args:
            player_id (int): The player id.

        Returns:
            str: The URL of the endpoint to get the player information.
        """
        return f"{self.base_url}/player/{player_id}"

    def player_transfer_history_endpoint(self, player_id: int) -> str:
        """
        Returns the URL of the endpoint to get the player transfer history.

        Args:
            player_id (int): The player id.

        Returns:
            str: The URL of the endpoint to get the player transfer history.
        """
        return f"{self.base_url}/player/{player_id}/transfer-history"

    def player_charac_endpoint(self, player_id: int) -> str:
        """
        Returns the URL of the endpoint to get the player characteristics.

        Args:
            player_id (int): The player id.

        Returns:
            str: The URL of the endpoint to get the player characteristics.
        """
        return f"{self.base_url}/player/{player_id}/characteristics"

    def player_attributes_endpoint(self, player_id: int) -> str:
        """
        Returns the URL of the endpoint to get the player attributes.

        Args:
            player_id (int): The player id.

        Returns:
            str: The URL of the endpoint to get the player attributes.
        """
        return f"{self.base_url}/player/{player_id}/attribute-overviews"

    def player_stats_endpoint(self, player_id: int) -> str:
        """
        Returns the URL of the endpoint to get the player statistics.

        Args:
            player_id (int): The player id.

        Returns:
            str: The URL of the endpoint to get the player statistics.
        """
        return f"{self.base_url}/player/{player_id}/statistics"

    # --- Search Endpoints ---

    def search_endpoint(self, query: str, entity_type: str) -> str:
        """
        Returns the URL of the endpoint to search for entities.

        Args:
            query (str): The search query.
            entity_type (str): The entity type (e.g., 'teams', 'players').

        Returns:
            str: The URL of the endpoint to search for entities.
        """
        return f"{self.base_url}/search/{entity_type}?q={query}&page=0"
