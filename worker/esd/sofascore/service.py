# esd/sofascore/service.py

"""
Sofascore service module
"""

from __future__ import annotations
import playwright
import os
import logging
import subprocess
import sys
from typing import Optional, Dict, Any 

# Add browser installation check
def install_playwright_browsers():
    """Install Playwright browsers if missing"""
    logger = logging.getLogger(__name__)
    try:
        logger.info("Checking Playwright browser installation...")
        # Try to install browsers
        result = subprocess.run([
            sys.executable, "-m", "playwright", "install", "chromium", "--force"
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.info("Playwright browsers installed successfully")
            return True
        else:
            logger.error(f"Browser installation failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Browser installation error: {e}")
        return False

# Install browsers before anything else (Keep this outside the class for startup efficiency)
# NOTE: This may be commented out in a stable, pre-built container environment.
# install_playwright_browsers() 

# Corrected relative imports for the local package structure
from ..utils import get_json, get_today
from .endpoints import SofascoreEndpoints
from .types import (
    Event,
    parse_event,
    parse_events,
    parse_player,
    parse_player_attributes,
    parse_transfer_history,
    parse_team,
    parse_tournament,
    parse_tournaments,
    parse_seasons,
    parse_brackets,
    parse_standings,
    parse_incidents,
    parse_top_players_match,
    parse_comments,
    parse_shots,
    parse_top_tournament_teams,
    parse_top_tournament_players,
    TopTournamentPlayers,
    TopTournamentTeams,
    Shot,
    Comment,
    TopPlayersMatch,
    Incident,
    Bracket,
    Season,
    Tournament,
    Standing,
    Team,
    Player,
    PlayerAttributes,
    TransferHistory,
    MatchStats,
    parse_match_stats,
    Lineups,
    parse_lineups,
    EntityType,
    Category,
    # CRITICAL: Import the new stats
    TeamTournamentStats, 
    parse_team_tournament_stats,
)


class SofascoreService:
    """
    A class to represent the SofaScore service.
    """

    def __init__(self, browser_path: str = None):
        """
        Initializes the SofaScore service.
        """
        self.logger = logging.getLogger(__name__)
        self.browser_path = browser_path
        self.endpoints = SofascoreEndpoints()
        self.playwright = self.browser = self.page = None
        self.__init_playwright()

    def __init_playwright(self):
        # ... (Playwright initialization logic is here) ...
        """
        Initialize the Playwright and browser instances.
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Initializing Playwright (attempt {attempt + 1})")
                self.playwright = playwright.sync_api.sync_playwright().start()
                
                # Browser launch options for Railway/cloud environments
                launch_options = {
                    'headless': True,
                    'args': [
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding',
                        '--single-process'
                    ],
                    'timeout': 30000
                }
                
                # Only use executable_path if provided and exists
                if self.browser_path and os.path.exists(self.browser_path):
                    launch_options['executable_path'] = self.browser_path
                    self.logger.info(f"Using browser at: {self.browser_path}")
                    self.browser = self.playwright.chromium.launch(**launch_options)
                else:
                    # Use Playwright's bundled Chromium (works on Railway)
                    self.logger.info("Using Playwright's bundled Chromium")
                    self.browser = self.playwright.chromium.launch(**launch_options)
                
                # Create page with better timeout settings
                self.page = self.browser.new_page()
                self.page.set_default_timeout(30000)
                self.page.set_default_navigation_timeout(30000)
                
                self.logger.info("Playwright initialized successfully")
                return
                
            except Exception as exc:
                self.logger.error(f"Playwright initialization failed (attempt {attempt + 1}): {str(exc)}")
                
                # Try to install browsers if they're missing
                if "Executable doesn't exist" in str(exc) and attempt == 0:
                    self.logger.info("Attempting to install missing browsers...")
                    install_playwright_browsers()
                    continue
                    
                # Clean up on failure
                if self.playwright:
                    self.playwright.stop()
                if attempt == max_retries - 1:
                    message = f"Failed to initialize browser after {max_retries} attempts: {str(exc)}"
                    raise RuntimeError(message) from exc

    def close(self):
        """
        Close the browser and playwright instances.
        """
        try:
            if self.page:
                self.page.close()
                self.page = None
            if self.browser:
                self.browser.close()
                self.browser = None
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
            self.logger.info("Playwright resources closed successfully")
        except Exception as exc:
            self.logger.error(f"Failed to close browser: {str(exc)}")
            
    def __del__(self):
        """
        Destructor to ensure resources are released.
        """
        self.close()
        
    # NEW METHOD: Get team tournament statistics
    def get_team_tournament_stats(self, team_id: int, tournament_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the season statistics for a team in a specific tournament.
        
        Args:
            team_id (int): The ID of the team.
            tournament_id (int): The ID of the tournament (league).

        Returns:
            Optional[Dict[str, Any]]: The raw JSON response data containing the statistics.
        """
        try:
            url = self.endpoints.team_tournament_stats_endpoint(team_id, tournament_id)
            
            raw_data = get_json(self.page, url)
            
            return raw_data 
            
        except Exception as exc:
            self.logger.error(f"Failed to get team tournament stats for team {team_id} in tournament {tournament_id}: {str(exc)}")
            return None

    def get_event(self, event_id: int) -> Event:
        # ... (Existing get_event logic) ...
        """
        Get the event information.
        """
        try:
            url = self.endpoints.event_endpoint.format(event_id=event_id)
            data = get_json(self.page, url)["event"]
            return parse_event(data)
        except Exception as exc:
            self.logger.error(f"Failed to get event {event_id}: {str(exc)}")
            raise exc

    def get_events(self, date: str = 'today') -> list[Event]:
        # ... (Existing get_events logic) ...
        """
        Get the scheduled events.
        """
        if date == 'today':
            date = get_today()
        try:
            url = self.endpoints.events_endpoint.format(date=date)
            return parse_events(get_json(self.page, url)["events"])
        except Exception as exc:
            self.logger.error(f"Failed to get events for date {date}: {str(exc)}")
            raise exc

    def get_live_events(self) -> list[Event]:
        # CRITICAL FIX: Robust live events fetching
        """
        Get the live events.

        Returns:
            list[Event]: The live events.
        """
        try:
            url = self.endpoints.live_events_endpoint
            
            # FIX: Use .get() to safely handle cases where the 'events' key is missing.
            data = get_json(self.page, url).get("events", []) 
            
            if not data:
                self.logger.info("No live events found in API response.")
                return []
                
            return parse_events(data)
            
        except Exception as exc:
            self.logger.error(f"Failed to get live events: {str(exc)}")
            raise exc

    # ... (Rest of the service methods: get_player, get_match_lineups, get_team, etc.) ...
    
    def get_player(self, player_id: int) -> Player:
        """
        Get the player information.
        """
        try:
            url = self.endpoints.player_endpoint.format(player_id=player_id)
            data = get_json(self.page, url)
            if "player" in data:
                player = parse_player(data["player"])
                player.attributes = self.get_player_attributes(player_id)
                player.transfer_history = self.get_player_transfer_history(player_id)
                return player
            return Player()
        except Exception as exc:
            self.logger.error(f"Failed to get player {player_id}: {str(exc)}")
            raise exc

    def get_player_attributes(self, player_id: int) -> PlayerAttributes:
        """
        Get the player attributes.
        """
        try:
            url = self.endpoints.player_attributes_endpoint.format(player_id=player_id)
            data = get_json(self.page, url)
            if "playerAttributes" in data:
                return parse_player_attributes(data["playerAttributes"])
            return PlayerAttributes()
        except Exception as exc:
            self.logger.error(f"Failed to get player attributes {player_id}: {str(exc)}")
            raise exc

    def get_player_transfer_history(self, player_id: int) -> TransferHistory:
        """
        Get the player transfer history.
        """
        try:
            url = self.endpoints.player_transfer_history_endpoint.format(player_id=player_id)
            data = get_json(self.page, url)
            if data is not None:
                return parse_transfer_history(data)
            return TransferHistory()
        except Exception as exc:
            self.logger.error(f"Failed to get transfer history for player {player_id}: {str(exc)}")
            raise exc

    def get_player_stats(self, player_id: int) -> dict:
        """
        TODO: Get the player statistics.
        """
        try:
            url = self.endpoints.player_stats_endpoint.format(player_id=player_id)
            return get_json(self.page, url)
        except Exception as exc:
            self.logger.error(f"Failed to get player stats {player_id}: {str(exc)}")
            raise exc

    def get_match_lineups(self, event_id: int) -> Lineups:
        """
        Get the match lineups.
        """
        try:
            url = self.endpoints.match_lineups_endpoint.format(event_id=event_id)
            return parse_lineups(get_json(self.page, url))
        except Exception as exc:
            self.logger.error(f"Failed to get lineups for event {event_id}: {str(exc)}")
            raise exc

    def get_match_incidents(self, event_id: int) -> list[Incident]:
        """
        Get the match incidents.
        """
        try:
            url = self.endpoints.match_events_endpoint.format(event_id=event_id)
            data = get_json(self.page, url)["incidents"]
            return parse_incidents(data)
        except Exception as exc:
            self.logger.error(f"Failed to get incidents for event {event_id}: {str(exc)}")
            raise exc

    def get_match_top_players(self, event_id: int) -> TopPlayersMatch:
        """
        Get the top players of a match.
        """
        try:
            url = self.endpoints.match_top_players_endpoint.format(event_id=event_id)
            return parse_top_players_match(get_json(self.page, url))
        except Exception as exc:
            self.logger.error(f"Failed to get top players for event {event_id}: {str(exc)}")
            raise exc

    def get_match_comments(self, event_id: int) -> list[Comment]:
        """
        Get the match comments.
        """
        try:
            url = self.endpoints.match_comments_endpoint.format(event_id=event_id)
            data = get_json(self.page, url)["comments"]
            return parse_comments(data)
        except Exception as exc:
            self.logger.error(f"Failed to get comments for event {event_id}: {str(exc)}")
            raise exc

    def get_match_stats(self, event_id: int) -> MatchStats:
        """
        Get the match statistics.
        """
        try:
            url = self.endpoints.match_stats_endpoint.format(event_id=event_id)
            data = get_json(self.page, url).get("statistics", {})
            url = self.endpoints.match_probabilities_endpoint.format(event_id=event_id)
            win_probabilities = get_json(self.page, url).get("winProbability", {})
            return parse_match_stats(data, win_probabilities)
        except Exception as exc:
            self.logger.error(f"Failed to get stats for event {event_id}: {str(exc)}")
            raise exc

    def get_match_shots(self, event_id: int) -> dict:
        """
        Get the match shots.
        """
        try:
            url = self.endpoints.match_shots_endpoint.format(event_id=event_id)
            data = get_json(self.page, url)
            if "shotmap" in data:
                return parse_shots(data["shotmap"])
            return Shot()
        except Exception as exc:
            self.logger.error(f"Failed to get shots for event {event_id}: {str(exc)}")
            raise exc

    def get_team(self, team_id: int) -> Team:
        """
        Get the team information.
        """
        try:
            url = self.endpoints.team_endpoint.format(team_id=team_id)
            data = get_json(self.page, url)["team"]
            return parse_team(data)
        except Exception as exc:
            self.logger.error(f"Failed to get team {team_id}: {str(exc)}")
            raise exc

    def get_team_players(self, team_id: int) -> list[Player]:
        """
        Get the team players.
        """
        try:
            url = self.endpoints.team_players_endpoint.format(team_id=team_id)
            return [
                parse_player(player["player"])
                for player in get_json(self.page, url)["players"]
            ]
        except Exception as exc:
            self.logger.error(f"Failed to get team players for team {team_id}: {str(exc)}")
            raise exc

    def get_team_events(self, team_id: int, upcoming: bool, page: int) -> list[Event]:
        """
        Get the team events.
        """
        try:
            url = self.endpoints.team_events_endpoint.format(team_id=team_id, upcoming=int(upcoming), page=page)
            data = get_json(self.page, url)
            if "events" in data:
                return parse_events(data["events"])
            return []
        except Exception as exc:
            self.logger.error(f"Failed to get team events for team {team_id}: {str(exc)}")
            raise exc

    def get_tournaments_by_category(self, category_id: Category) -> list[Tournament]:
        """
        Get the tournaments by category id.
        """
        if not isinstance(category_id, Category):
            raise ValueError("category_id must be an instance of Category Enum")
        try:
            url = self.endpoints.tournaments_endpoint.format(category_id=category_id.value)
            data = get_json(self.page, url)["groups"][0].get("uniqueTournaments", [])
            return parse_tournaments(data)
        except Exception as exc:
            self.logger.error(f"Failed to get tournaments for category {category_id}: {str(exc)}")
            raise exc

    def get_tournament_seasons(self, tournament_id: int) -> list[Season]:
        """
        Get the seasons of a tournament.
        """
        try:
            url = self.endpoints.tournament_seasons_endpoint.format(tournament_id=tournament_id)
            data = get_json(self.page, url)["seasons"]
            return parse_seasons(data)
        except Exception as exc:
            self.logger.error(f"Failed to get seasons for tournament {tournament_id}: {str(exc)}")
            raise exc

    def get_tournament_bracket(
        self, tournament_id: int | Tournament, season_id: int | Season
    ) -> list[Bracket]:
        """
        Get the tournament bracket.
        """
        try:
            if isinstance(tournament_id, Tournament):
                tournament_id = tournament_id.id
            if isinstance(season_id, Season):
                season_id = season_id.id
            url = self.endpoints.tournament_bracket_endpoint.format(tournament_id=tournament_id, season_id=season_id)
            data = get_json(self.page, url)["cupTrees"]
            return parse_brackets(data)
        except Exception as exc:
            self.logger.error(f"Failed to get bracket for tournament {tournament_id}: {str(exc)}")
            raise exc

    def get_tournament_standings(
        self, tournament_id: int | Tournament, season_id: int | Season
    ) -> list[Standing]:
        """
        Get the tournament standings.
        """
        try:
            if isinstance(tournament_id, Tournament):
                tournament_id = tournament_id.id
            if isinstance(season_id, Season):
                season_id = season_id.id
            url = self.endpoints.tournament_standings_endpoint.format(tournament_id=tournament_id, season_id=season_id)
            data = get_json(self.page, url)["standings"]
            return parse_standings(data)
        except Exception as exc:
            self.logger.error(f"Failed to get standings for tournament {tournament_id}: {str(exc)}")
            raise exc

    def get_tournament_top_teams(
        self, tournament_id: int | Tournament, season_id: int | Season
    ) -> TopTournamentTeams:
        """
        Get different top teams of a tournament.
        """
        try:
            if isinstance(tournament_id, Tournament):
                tournament_id = tournament_id.id
            if isinstance(season_id, Season):
                season_id = season_id.id
            url = self.endpoints.tournament_topteams_endpoint.format(tournament_id=tournament_id, season_id=season_id)
            response = get_json(self.page, url)
            if "topTeams" in response:
                return parse_top_tournament_teams(response["topTeams"])
            return TopTournamentTeams()
        except Exception as exc:
            self.logger.error(f"Failed to get top teams for tournament {tournament_id}: {str(exc)}")
            raise exc

    def get_tournament_top_players(
        self, tournament_id: int | Tournament, season_id: int | Season
    ) -> TopTournamentPlayers:
        """
        Get the top players of the tournament.
        """
        try:
            if isinstance(tournament_id, Tournament):
                tournament_id = tournament_id.id
            if isinstance(season_id, Season):
                season_id = season_id.id
            url = self.endpoints.tournament_topplayers_endpoint.format(
                tournament_id=tournament_id, season_id=season_id
            )
            data = get_json(self.page, url)
            if "topPlayers" in data:
                return parse_top_tournament_players(data["topPlayers"])
            return TopTournamentPlayers()
        except Exception as exc:
            self.logger.error(f"Failed to get top players for tournament {tournament_id}: {str(exc)}")
            raise exc

    def get_tournament_events(
        self, tournament_id: int, season_id: int, upcoming: bool, page: int
    ) -> list[Event]:
        """
        Get the events of a tournament.
        """
        try:
            url = self.endpoints.tournament_events_endpoint.format(
                tournament_id=tournament_id, season_id=season_id, upcoming=int(upcoming), page=page
            )
            data = get_json(self.page, url)
            if "events" in data:
                return parse_events(data["events"])
            return []
        except Exception as exc:
            self.logger.error(f"Failed to get events for tournament {tournament_id}: {str(exc)}")
            raise exc

    def search(
        self, query: str, entity: EntityType = EntityType.ALL
    ) -> list[Event | Team | Player | Tournament]:
        """
        Search query for matches, teams, players, and tournaments.
        """
        try:
            entity_type = entity.value
            url = self.endpoints.search_endpoint(query=query, entity_type=entity_type)
            results = get_json(self.page, url)["results"]

            specific_parsers = {
                EntityType.TEAM: parse_team,
                EntityType.PLAYER: parse_player,
                EntityType.EVENT: parse_event,
                EntityType.TOURNAMENT: parse_tournament,
            }

            if entity == EntityType.ALL:
                type_parsers = {
                    "team": parse_team,
                    "player": parse_player,
                    "event": parse_events,
                    "uniqueTournament": parse_tournament,
                }
                entities = []
                for result in results:
                    result_type = result.get("type")
                    entity_data = result.get("entity")
                    parser = type_parsers.get(result_type, lambda x: x)
                    if isinstance(entity_data, list): # handle 'event' which returns list of events
                        entities.extend(parser(entity_data))
                    else:
                        entities.append(parser(entity_data))
                return entities
            
            parser = specific_parsers.get(entity, lambda x: x)
            return [parser(result.get("entity")) for result in results]
        except Exception as exc:
            self.logger.error(f"Failed to search for '{query}': {str(exc)}")
            raise exc
