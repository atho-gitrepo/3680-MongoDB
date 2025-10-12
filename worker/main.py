import datetime
import logging
from typing import List, Dict, Any, Optional, Set
import requests
import os # Needed for environment variables

# --- Mock/Assumed Imports from your esd/sofascore package ---
# These imports are necessary for the main logic to function.
from esd.sofascore.client import SofascoreClient
# from esd.sofascore.types import Event, Standing, Tournament, Season, Team, Category
# We redefine the minimal necessary mocks here to make the function runnable for testing
# In your real environment, you must import the actual classes.

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

# --- Assumed Functions from previous steps ---

# You must ensure these functions from your previous steps are in main.py 
# or imported correctly for the final script to run.

def get_current_season_id(service: Any, tournament_id: int) -> Optional[int]:
    """Mock implementation or actual function imported from a utility."""
    # Placeholder implementation
    return 9999 

def get_top_bottom_daily_fixtures(client: Any, category_enum: Category, date_str: str) -> List[Dict[str, Any]]:
    """
    Mock implementation of the core function that generates fixtures.
    In your real code, this is the function developed in the previous step.
    """
    # Simulate a successful fetch with mock data
    today = datetime.datetime.now()
    
    # Mock data involving top/bottom teams
    fixtures = [
        {
            "tournament": "Premier League",
            "match": "PL Team 1 vs PL Team 18",
            "time": today.strftime("%H:%M"),
            "teams_of_interest": "PL Team 1, PL Team 18"
        },
        {
            "tournament": "La Liga",
            "match": "LL Team 3 vs LL Team 20",
            "time": today.strftime("%H:%M"),
            "teams_of_interest": "LL Team 3, LL Team 20"
        }
    ]
    
    # Simulate a scenario with no fixtures for robustness
    if date_str == 'tomorrow':
        return []
        
    return fixtures

# --- New Telegram Function ---

def send_telegram_message(message: str, chat_id: str, bot_token: str):
    """
    Sends a message to a specified Telegram chat using the Bot API.
    
    Args:
        message (str): The text message to send.
        chat_id (str): The target chat ID (e.g., '@mychannel' or user ID).
        bot_token (str): The Telegram Bot token.
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
    except requests.exceptions.HTTPError as e:
        logging.error(f"Telegram API HTTP Error: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Telegram request failed: {e}")

# --- Main Execution Block (The new content for your main.py) ---

if __name__ == '__main__':
    # Configuration
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 📌 IMPORTANT: Define these environment variables or replace with actual strings
    # Get your Bot Token from BotFather and your Chat ID (e.g., from @userinfobot)
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN") 
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") # Use a group/channel ID
    
    FOOTBALL_CATEGORY = Category(1) 
    
    # Initialize Client and Service
    client = SofascoreClient()
    client.initialize() 

    try:
        fixture_date = 'today'
        fixtures = get_top_bottom_daily_fixtures(client, FOOTBALL_CATEGORY, date_str=fixture_date)
        
        # --- Message Generation ---
        
        header = f"⚽ Sofascore Daily Fixtures - {fixture_date.capitalize()} ⚽\n\n"
        
        if fixtures:
            body = "*Matches Involving Top 3 or Last 3 Teams:*\n"
            for f in fixtures:
                # Format each fixture clearly using Markdown bolding
                body += (
                    f"\n*🏆 {f['tournament']}*\n"
                    f"  {f['match']} @ {f['time']}\n"
                    f"  (Focus: {f['teams_of_interest']})"
                )
            
            final_message = header + body
            
        else:
            final_message = header + "No relevant fixtures found for today."
            
        # --- Send Message ---
        
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
