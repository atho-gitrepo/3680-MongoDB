# main.py
import datetime
import logging
from typing import List, Dict, Any, Optional, Set
import requests
import os 
import subprocess
import sys

# --- CORE PROJECT IMPORTS ---
# Ensure your project structure allows these imports to resolve correctly
from esd.sofascore.client import SofascoreClient
from esd.sofascore.types import Event, Standing, Tournament, Season, Team, Category 
from esd.utils import get_today 

logger = logging.getLogger(__name__)

# ######################################################################
# ### HELPER FUNCTIONS (Integrated Logic from Previous Steps)
# ######################################################################

def get_current_season_id(service: Any, tournament_id: int) -> Optional[int]:
    """
    Finds the ID of the current (or most recent) season for a given tournament.
    """
    try:
        seasons: List[Season] = service.get_tournament_seasons(tournament_id)
        if not seasons:
            return None
        
        # Look for the season explicitly marked as current 
        current_season = next((s.id for s in seasons if hasattr(s, 'is_current') and s.is_current), None)
        if current_season is not None:
            return current_season
            
        # Fallback: Assume the first season returned is the most relevant/current
        return seasons[0].id
        
    except Exception as e:
        logger.warning(f"Failed to find season for tournament {tournament_id}: {e}")
        return None

def get_top_bottom_daily_fixtures(client: Any, category_enum: Category, date_str: str = 'today') -> List[Dict[str, Any]]:
    """
    Retrieves the daily fixtures involving the top 3 and last 3 teams 
    from all major tournaments in a specified category using real API calls.
    """
    if not client.service:
        client.initialize() # Should already be done, but safe check
    
    service = client.service
    
    # 1. Gather all tournaments for the category
    logger.info(f"Fetching tournaments for category: {category_enum.name}")
    try:
        # Calls SofascoreService.get_tournaments_by_category
        tournaments: List[Tournament] = service.get_tournaments_by_category(category_enum)
    except Exception as e:
        logger.error(f"Error fetching tournaments: {e}")
        return []

    target_team_ids: Set[int] = set()

    # 2. Identify all target teams (Top 3 and Last 3)
    for t in tournaments:
        season_id = get_current_season_id(service, t.id)
        if season_id is None:
            continue

        try:
            # Calls SofascoreService.get_tournament_standings
            standings_groups: List[Standing] = service.get_tournament_standings(t.id, season_id)
        except Exception as e:
            logger.warning(f"Skipping {t.name} due to standings error: {e}")
            continue
            
        if not standings_groups or not hasattr(standings_groups[0], 'rows'):
             continue
             
        standing_rows: List[StandingRow] = standings_groups[0].rows
        num_teams = len(standing_rows)
        
        # Get Top 3 and Last 3 teams
        top_teams = standing_rows[:3]
        last_three_start_index = max(0, num_teams - 3) # Ensure index is not negative
        bottom_teams = standing_rows[last_three_start_index:]
        
        # Add team IDs
        for row in top_teams + bottom_teams:
            if hasattr(row, 'team') and hasattr(row.team, 'id'):
                target_team_ids.add(row.team.id)

    logger.info(f"Identified {len(target_team_ids)} unique teams of interest across all tournaments.")

    # 3. Get all events for the specified date
    date_to_fetch = get_today() if date_str == 'today' else date_str
    try:
        daily_events: List[Event] = client.get_events(date_to_fetch)
    except Exception as e:
        logger.error(f"Error fetching daily events: {e}")
        return []
    
    # 4. Filter and format the results
    filtered_fixtures = []
    
    for event in daily_events:
        home_id = getattr(event.home_team, 'id', None)
        away_id = getattr(event.away_team, 'id', None)
        
        if home_id in target_team_ids or away_id in target_team_ids:
            
            target_teams_involved = []
            if home_id in target_team_ids:
                target_teams_involved.append(event.home_team.name)
            if away_id in target_team_ids:
                target_teams_involved.append(event.away_team.name)

            tournament_name = getattr(event, 'tournament_name', 'Unknown')
            start_time = getattr(event, 'start_time', None)

            filtered_fixtures.append({
                "tournament": tournament_name,
                "match": f"{event.home_team.name} vs {event.away_team.name}",
                "time": start_time.strftime("%H:%M") if isinstance(start_time, datetime.datetime) else 'N/A',
                "teams_of_interest": ", ".join(sorted(list(set(target_teams_involved))))
            })
            
    return filtered_fixtures

# ######################################################################
# ### TELEGRAM FUNCTION
# ######################################################################

def send_telegram_message(message: str, chat_id: str, bot_token: str):
    """
    Sends a message to a specified Telegram chat using the Bot API.
    """
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

# ######################################################################
# ### MAIN EXECUTION BLOCK
# ######################################################################

if __name__ == '__main__':
    # Configuration
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 📌 GET ENVIRONMENT VARIABLES
    # NOTE: These must be set in your execution environment (.env file or system exports)
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN") 
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    # We pass the Category instance for Football (assuming its ID is 1)
    FOOTBALL_CATEGORY = Category(1) 
    
    # Initialize Client
    client = SofascoreClient()
    
    try:
        client.initialize()
        fixture_date = 'today'
        
        # EXECUTES THE DATA RETRIEVAL
        fixtures = get_top_bottom_daily_fixtures(client, FOOTBALL_CATEGORY, date_str=fixture_date)
        
        # --- Console Output ---
        
        print("\n" + "=" * 60)
        print(f"  DAILY FIXTURES FOR TOP 3 & LAST 3 TEAMS ({fixture_date.upper()})")
        print("=" * 60)
        
        header = f"⚽ Sofascore Daily Fixtures - {fixture_date.capitalize()} ⚽\n\n"
        
        if fixtures:
            body = "*Matches Involving Top 3 or Last 3 Teams:*\n"
            for f in fixtures:
                # Console Print
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

    except Exception as e:
        error_message = f"🚨 FATAL ERROR: Failed to run fixture process: {type(e).__name__} - {e}"
        logging.error(error_message)
        send_telegram_message(error_message, TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN)
        
    finally:
        if 'client' in locals():
            client.close()

