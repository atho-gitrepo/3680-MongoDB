import datetime
import logging
from typing import List, Dict, Any, Optional, Set
import requests
import os 
# NOTE: Replace the MOCK CLASSES below with these imports from your package
from esd.sofascore.client import SofascoreClient
# from esd.sofascore.types import Event, Standing, Tournament, Season, Team, Category 

# --- WARNING: MOCK CLASSES RETAINED FOR STANDALONE EXECUTION ONLY ---
# In your real project, REMOVE these definitions and use the actual imports
class Team:
    def __init__(self, id: int, name: str): self.id = id; self.name = name
class Event:
    def __init__(self, home_team: Team, away_team: Team, start_time: datetime.datetime, tournament_name: str):
        self.home_team = home_team; self.away_team = away_team; self.start_time = start_time; self.tournament_name = tournament_name
class Tournament:
    def __init__(self, id: int, name: str): self.id = id; self.name = name
class Season:
    def __init__(self, id: int, is_current: bool = True): self.id = id; self.is_current = is_current
class StandingRow:
    def __init__(self, team: Team, rank: int): self.team = team; self.rank = rank
class Standing:
    def __init__(self, rows: List[StandingRow]): self.rows = rows
class Category:
    FOOTBALL = 1
    def __init__(self, value: int): self.value = value
    @property
    def name(self): return "FOOTBALL" if self.value == 1 else "OTHER"
# --- END MOCK CLASSES ---

logger = logging.getLogger(__name__)

# --- Helper Functions (Re-implemented with real logic) ---

def get_current_season_id(service: Any, tournament_id: int) -> Optional[int]:
    """Finds the ID of the current (or most recent) season for a given tournament."""
    try:
        seasons: List[Season] = service.get_tournament_seasons(tournament_id)
        if not seasons: return None
        current_season = next((s.id for s in seasons if hasattr(s, 'is_current') and s.is_current), None)
        if current_season is not None: return current_season
        return seasons[0].id
    except Exception as e:
        logger.warning(f"Failed to find season for tournament {tournament_id}: {e}")
        return None

def get_top_bottom_daily_fixtures(client: Any, category_enum: Category, date_str: str = 'today') -> List[Dict[str, Any]]:
    """Retrieves the daily fixtures involving the top 3 and last 3 teams."""
    if not client.service: client.initialize()
    service = client.service
    
    logger.info(f"Fetching tournaments for category: {category_enum.name}")
    try:
        tournaments: List[Tournament] = service.get_tournaments_by_category(category_enum)
    except Exception as e:
        logger.error(f"Error fetching tournaments: {e}")
        return []

    target_team_ids: Set[int] = set()
    for t in tournaments:
        season_id = get_current_season_id(service, t.id)
        if season_id is None: continue

        try:
            standings_groups: List[Standing] = service.get_tournament_standings(t.id, season_id)
        except Exception as e:
            logger.warning(f"Skipping {t.name} due to standings error: {e}")
            continue
            
        if not standings_groups or not hasattr(standings_groups[0], 'rows'): continue
             
        standing_rows: List[StandingRow] = standings_groups[0].rows
        num_teams = len(standing_rows)
        
        top_teams = standing_rows[:3]
        last_three_start_index = max(3, num_teams - 3)
        bottom_teams = standing_rows[last_three_start_index:]
        
        for row in top_teams + bottom_teams:
            if hasattr(row, 'team') and hasattr(row.team, 'id'):
                target_team_ids.add(row.team.id)

    logger.info(f"Identified {len(target_team_ids)} unique teams of interest across all tournaments.")

    try:
        daily_events: List[Event] = client.get_events(date_str)
    except Exception as e:
        logger.error(f"Error fetching daily events: {e}")
        return []
    
    filtered_fixtures = []
    for event in daily_events:
        home_id = event.home_team.id
        away_id = event.away_team.id
        
        if home_id in target_team_ids or away_id in target_team_ids:
            target_teams_involved = []
            if home_id in target_team_ids: target_teams_involved.append(event.home_team.name)
            if away_id in target_team_ids: target_teams_involved.append(event.away_team.name)

            tournament_name = getattr(event, 'tournament_name', 'Unknown')
            start_time = getattr(event, 'start_time', None)

            filtered_fixtures.append({
                "tournament": tournament_name,
                "match": f"{event.home_team.name} vs {event.away_team.name}",
                "time": start_time.strftime("%H:%M") if isinstance(start_time, datetime.datetime) else 'N/A',
                "teams_of_interest": ", ".join(sorted(list(set(target_teams_involved))))
            })
            
    return filtered_fixtures

# --- Telegram Function ---

def send_telegram_message(message: str, chat_id: str, bot_token: str):
    """Sends a message to a specified Telegram chat using the Bot API."""
    if not bot_token or not chat_id:
        logging.error("Telegram BOT_TOKEN or CHAT_ID is missing. Cannot send message.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }
    
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        logging.info("Telegram message sent successfully.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Telegram request failed: {e}")

# --- Main Execution Block ---

if __name__ == '__main__':
    # Configuration
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 📌 GET ENVIRONMENT VARIABLES
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN") 
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    FOOTBALL_CATEGORY = Category(1) 
    
    # Initialize Client
    client = SofascoreClient()
    
    try:
        client.initialize()
        fixture_date = 'today'
        
        # 🔑 THIS CALL EXECUTES THE DATA RETRIEVAL
        fixtures = get_top_bottom_daily_fixtures(client, FOOTBALL_CATEGORY, date_str=fixture_date)
        
        # --- Console Output (To fulfill your request for the list when running) ---
        
        print("\n" + "=" * 60)
        print(f"  DAILY FIXTURES FOR TOP 3 & LAST 3 TEAMS ({fixture_date.upper()})")
        print("=" * 60)
        
        header = f"⚽ Sofascore Daily Fixtures - {fixture_date.capitalize()} ⚽\n\n"
        
        if fixtures:
            body = "*Matches Involving Top 3 or Last 3 Teams:*\n"
            for f in fixtures:
                # Print to console
                print(f"Tournament: {f['tournament']}")
                print(f"Match:      {f['match']}")
                print(f"Time:       {f['time']}")
                print(f"Involved:   {f['teams_of_interest']}")
                print("-" * 50)
                
                # Build Telegram body
                body += (
                    f"\n*🏆 {f['tournament']}*\n"
                    f"  {f['match']} @ {f['time']}\n"
                    f"  (Focus: {f['teams_of_interest']})"
                )
            
            final_message = header + body
            
        else:
            print("No relevant fixtures found for today.")
            final_message = header + "No relevant fixtures found for today."
            
        # --- Send Telegram Message ---
        
        send_telegram_message(
            message=final_message,
            chat_id=TELEGRAM_CHAT_ID,
            bot_token=TELEGRAM_BOT_TOKEN
        )

    except RuntimeError as e:
        error_message = f"🚨 FATAL ERROR: Failed to run fixture process. Check Playwright or API: {e}"
        logging.error(error_message)
        send_telegram_message(error_message, TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN)
        
    except Exception as e:
        error_message = f"⚠️ An unexpected error occurred: {e}"
        logging.error(error_message)
        send_telegram_message(error_message, TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN)
        
    finally:
        # Clean up resources
        if 'client' in locals():
            client.close()
