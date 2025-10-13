import datetime
import logging
from typing import List, Dict, Any, Optional, Set
import requests
import os

# --- CORE PROJECT IMPORTS ---
from esd.sofascore.client import SofascoreClient
from esd.sofascore.types import Event, Tournament, Season, Category 
from esd.utils import get_today

logger = logging.getLogger(__name__)

# ######################################################################
# ### HELPER FUNCTIONS
# ######################################################################

def get_current_season_id(service: Any, tournament_id: int) -> Optional[int]:
    """
    Finds the ID of the current (or most recent) season for a given tournament.
    """
    try:
        seasons: List[Season] = service.get_tournament_seasons(tournament_id)
        if not seasons:
            return None
        
        current_season = next((s.id for s in seasons if hasattr(s, 'is_current') and s.is_current), None)
        if current_season is not None:
            return current_season
        return seasons[0].id
        
    except Exception as e:
        logger.warning(f"Failed to find season for tournament {tournament_id}: {e}")
        return None


def parse_event_time(start_time) -> str:
    """
    Safely parse the event start_time into HH:MM format.
    """
    if not start_time:
        return 'N/A'

    # If start_time is a callable property, call it
    if callable(start_time):
        try:
            start_time = start_time()
        except Exception:
            return 'N/A'

    if isinstance(start_time, datetime.datetime):
        return start_time.strftime("%H:%M")

    # Attempt ISO parsing without external libraries
    try:
        dt = datetime.datetime.fromisoformat(str(start_time))
        return dt.strftime("%H:%M")
    except Exception:
        return 'N/A'


# ######################################################################
# ### CORE FUNCTION: Get ALL Daily Fixtures for a Region
# ######################################################################

def get_all_daily_fixtures(client: Any, category_enum: Category, date_str: str = 'today') -> List[Dict[str, Any]]:
    """
    Retrieves ALL daily fixtures that belong to ANY tournament in the specified region.
    """
    if not client.service:
        client.initialize()
    
    service = client.service

    # 1. Gather all tournament IDs for the category
    logger.info(f"Fetching all tournament IDs for category: {category_enum.name}")
    try:
        tournaments: List[Tournament] = service.get_tournaments_by_category(category_enum)
        if not tournaments:
            logger.info(f"No tournaments found for category: {category_enum.name}")
            return []
            
        target_tournament_ids: Set[int] = {t.id for t in tournaments if hasattr(t, 'id')}
        logger.info(f"Identified {len(target_tournament_ids)} tournaments in category {category_enum.name}.")

    except Exception as e:
        logger.error(f"Error fetching tournaments for all fixtures: {e}")
        return []

    # 2. Get all events for the specified date
    # 🌟 CRITICAL FIX: ENSURE get_today() IS CALLED.
    date_to_fetch = get_today() if date_str == 'today' else date_str
    
    try:
        # client.get_events is likely the method throwing the 'function' format error
        daily_events: List[Event] = client.get_events(date_to_fetch)
        if not daily_events:
            logger.info(f"No events found for date {date_to_fetch}")
            return []
    except Exception as e:
        # Log the error again for clarity
        logger.error(f"Failed to get all events for date {date_to_fetch}: {e}")
        return []

    # 3. Filter and format results
    filtered_fixtures = []
    for event in daily_events:
        tournament_id = getattr(event, 'tournament_id', None) 

        if tournament_id in target_tournament_ids:
            tournament_name = getattr(event, 'tournament_name', 'Unknown')
            start_time = parse_event_time(getattr(event, 'start_time', None))

            filtered_fixtures.append({
                "tournament": tournament_name,
                "match": f"{event.home_team.name} vs {event.away_team.name}",
                "time": start_time,
            })
            
    filtered_fixtures.sort(key=lambda f: f['tournament'])

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
        # Also log Telegram Bad Request errors (400) like the one you saw in the logs
        logging.error(f"Telegram request failed: {e}")


# ######################################################################
# ### MAIN EXECUTION
# ######################################################################

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    client = SofascoreClient()
    try:
        client.initialize()

        # Loop through all categories dynamically
        for region in Category:
            logger.info(f"Processing region: {region.name} (ID: {region.value})")

            all_fixtures = get_all_daily_fixtures(client, region, date_str='today')
            
            # --- CONSTRUCT MESSAGE FOR ALL FIXTURES ---
            
            print("\n" + "=" * 60)
            print(f"  ALL DAILY FIXTURES - REGION: {region.name.upper()}")
            print("=" * 60)

            header = f"⚽ Sofascore Daily Fixtures - {region.name.capitalize()} ⚽\n\n"
            
            full_list_body = f"*📅 All Fixtures for {region.name.capitalize()}:*\n"

            if all_fixtures:
                # Group by Tournament for better readability
                fixtures_by_tournament = {}
                for f in all_fixtures:
                    fixtures_by_tournament.setdefault(f['tournament'], []).append(f)

                # Iterate through sorted tournaments for the Telegram message
                for tournament_name, fixtures in fixtures_by_tournament.items():
                    print(f"\nTournament: {tournament_name}")
                    full_list_body += f"\n*🏆 {tournament_name}*\n"
                    
                    for f in fixtures:
                        print(f"Match: {f['match']} @ {f['time']}")
                        full_list_body += (
                            f"  {f['match']} @ {f['time']}\n"
                        )
                    print("-" * 50)

                final_message = header + full_list_body
            else:
                print("No relevant fixtures found for this region today.")
                final_message = header + "No fixtures found for this region today."

            # Send Telegram message
            if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                send_telegram_message(
                    message=final_message,
                    chat_id=TELEGRAM_CHAT_ID,
                    bot_token=TELEGRAM_BOT_TOKEN
                )

    except Exception as e:
        error_message = f"🚨 FATAL ERROR: {type(e).__name__} - {e}"
        logging.error(error_message)
        send_telegram_message(error_message, TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN)

    finally:
        if 'client' in locals():
            client.close()
