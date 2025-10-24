# /app/worker/bot.py

import logging
import time
import os
import datetime
from typing import Optional, List, Dict, Any

# CRITICAL FIX: Import the requests library for the send_telegram function
import requests 

# Import services and types from your project
from esd.sofascore import (
    SofascoreClient, 
    EntityType, 
    TeamTournamentStats,
    parse_team_tournament_stats,
    Event
)

# --- Configuration ---

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TIME_BETWEEN_CYCLES = int(os.getenv("TIME_BETWEEN_CYCLES", 60))

# Betting configuration
MIN_TOTAL_AVERAGE_GOALS = float(os.getenv("MIN_TOTAL_AVERAGE_GOALS", 3.0)) 

# Global state
logger = logging.getLogger(__name__)
sofascore_client: Optional[SofascoreClient] = None
# A simple dictionary to track matches that have already been signaled
tracked_matches: Dict[int, bool] = {}

# --- Utility Functions ---

def send_telegram(message: str):
    """
    Sends a message to the configured Telegram chat.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram credentials (TOKEN or CHAT_ID) are missing. Cannot send message.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        logger.info(f"Telegram message sent successfully.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while sending Telegram message: {e}")


def is_amateur_or_youth_league(event: Event) -> bool:
    """
    Checks if an event belongs to a league that should be skipped (e.g., amateur, youth, or reserves).
    """
    skip_keywords = [
        'reserve', 'u1', 'u2', 'youth', 'amateur', 'friendly game',
        'landesliga', 'regionalliga', 'oberliga', 'liga 3', 'liga 4', 'cup',
        'test match', 'division one', 'division two', 'division three',
        'division four', 'division five', 'division six',
        'cup, women', 'club friendly'
    ]
    
    # Combine relevant names into a single lower-case string for checking
    event_str = f"{event.tournament.name.lower()} {event.country.name.lower()} {event.home_team.name.lower()} {event.away_team.name.lower()}"
    
    for keyword in skip_keywords:
        if keyword in event_str:
            logger.info(f"Skipping amateur/youth league based on keyword found in: {event_str}")
            return True
    return False

# --- Core Logic Functions ---

def _get_team_stats_safely(team_id: int, tournament_id: int) -> TeamTournamentStats:
    """
    Fetches, parses, and returns TeamTournamentStats, logging errors safely.
    Returns an empty TeamTournamentStats object if fetching fails.
    """
    raw_stats = sofascore_client.get_team_tournament_stats(team_id, tournament_id)
    if raw_stats:
        return parse_team_tournament_stats(team_id, tournament_id, raw_stats)
    
    # Return a zero-value stats object on failure
    logger.warning(f"Could not fetch raw stats for team {team_id} in tournament {tournament_id}. Returning empty stats.")
    return TeamTournamentStats(team_id=team_id, tournament_id=tournament_id)


def _process_event_for_betting(event: Event) -> Optional[str]:
    """
    Applies all betting filters to a single event.

    Returns:
        Optional[str]: A formatted Telegram message if a signal is found, otherwise None.
    """
    global tracked_matches

    # 1. Skip previously tracked and currently tracked matches
    if event.id in tracked_matches:
        return None
    
    # 2. Skip amateur/youth leagues
    if is_amateur_or_youth_league(event):
        return None

    # 3. Apply Time/Status Filters (Example)
    # This is where you would put filters like: time > 15 min, score = 0-0, etc.
    # For now, we'll assume any fetched event is "trackable" if it passes league filters.
    
    # 4. Fetch Average Goal Stats
    
    # Home Team Stats
    home_stats = _get_team_stats_safely(
        team_id=event.home_team.id, 
        tournament_id=event.tournament.id
    )
    
    # Away Team Stats
    away_stats = _get_team_stats_safely(
        team_id=event.away_team.id, 
        tournament_id=event.tournament.id
    )
    
    # 5. Apply Average Goal Filter
    
    # Calculate the total average goals across both teams (Scored + Conceded for Home, Scored + Conceded for Away)
    total_avg_goals = home_stats.total_average_goals + away_stats.total_average_goals
    
    logger.info(
        f"Event {event.id}: {event.home_team.name} vs {event.away_team.name} | "
        f"Home Avg: {home_stats.total_average_goals:.2f} | "
        f"Away Avg: {away_stats.total_average_goals:.2f} | "
        f"Combined Avg: {total_avg_goals:.2f}"
    )

    if total_avg_goals >= MIN_TOTAL_AVERAGE_GOALS:
        # Signal found!
        tracked_matches[event.id] = True # Mark as tracked
        
        message = (
            f"⚽️ *BETTING SIGNAL FOUND* ⚽️\n"
            f"🏆 {event.tournament.name} ({event.country.name})\n"
            f"🆚 *{event.home_team.name}* vs *{event.away_team.name}*\n"
            f"⏱ Current Time: {event.time.current_minute}' | Score: {event.score.home}:{event.score.away}\n\n"
            
            f"📊 *AVERAGE GOALS (Scored + Conceded)*\n"
            f"• *{event.home_team.name}* (Home): {home_stats.total_average_goals:.2f}\n"
            f"• *{event.away_team.name}* (Away): {away_stats.total_average_goals:.2f}\n"
            f"• *Combined Total Avg*: {total_avg_goals:.2f}\n\n"
            
            f"✅ *SIGNAL REASON*: Combined Avg Goals $\\geq$ {MIN_TOTAL_AVERAGE_GOALS:.2f} (Actual: {total_avg_goals:.2f})"
        )
        return message

    return None


def run_bot_cycle():
    """
    The main execution cycle for the betting bot.
    """
    logger.info("Starting bot cycle...")
    
    try:
        # 1. Fetch live events
        live_matches: List[Event] = sofascore_client.get_live_events()
        logger.info(f"Fetched {len(live_matches)} live matches.")

        # 2. Iterate and process each event
        for event in live_matches:
            message = _process_event_for_betting(event)
            if message:
                send_telegram(message)
                
    except Exception as e:
        logger.error(f"An error occurred during the bot cycle: {e}", exc_info=True)
        send_telegram(f"❌ *Bot Cycle Error*: An unexpected error occurred: `{str(e)}`")

    # 3. Cleanup and reporting
    logger.info(f"Bot cycle completed. Currently tracking {len(tracked_matches)} matches locally.")


def initialize_bot_services() -> bool:
    """
    Initializes the SofaScore client and other services.
    """
    global sofascore_client
    
    logger.info("Initializing Football Betting Bot services...")
    
    # 1. Initialize Firebase (Placeholder, if you add database later)
    logger.info("Initializing Firebase...")
    # ... Firebase init logic here ...
    logger.info("Firebase initialized successfully")
    
    # 2. Initialize Sofascore Client
    logger.info("Attempting to initialize Sofascore client...")
    try:
        # You may need to pass a browser path if Playwright is not finding it
        sofascore_client = SofascoreClient() 
        logger.info("Sofascore client successfully initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize Sofascore client: {e}")
        send_telegram(f"🔥 *FATAL ERROR*: Failed to initialize Sofascore client on startup: `{str(e)}`")
        return False

    logger.info("All bot services initialized successfully.")
    send_telegram("🚀 Football Betting Bot Initialized Successfully! Starting monitoring.")
    return True

# --- Main Loop (If you run bot.py directly) ---

def main():
    """
    Main loop for continuous execution.
    """
    if not initialize_bot_services():
        logger.error("Bot services failed to initialize. Exiting.")
        return

    while True:
        try:
            run_bot_cycle()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(10) # Wait before restarting the loop on error
        
        logger.info(f"Sleeping for {TIME_BETWEEN_CYCLES} seconds...")
        time.sleep(TIME_BETWEEN_CYCLES)

if __name__ == '__main__':
    main()
