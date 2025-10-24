import requests
import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# --- Sofascore Imports ---
from esd.sofascore import (
    SofascoreClient, 
    EntityType, 
    TeamTournamentStats,
    parse_team_tournament_stats,
    Event
) 

# --- GLOBAL VARIABLES ---
SOFASCORE_CLIENT = None 
LOCAL_TRACKED_MATCHES: Dict[str, Dict[str, Any]] = {} 

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("FootballBettingBot")

# Load environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- CONSTANTS ---
SLEEP_TIME = 60
MINUTES_REGULAR_BET = [36, 37]
BET_TYPE_REGULAR = 'regular'
STATUS_LIVE = ['LIVE', '1H', '2H', 'ET', 'P']
STATUS_HALFTIME = 'HT'
STATUS_FINISHED = ['FT', 'AET', 'PEN'] 
MAX_FETCH_RETRIES = 3 

# --- 🟢 AVERAGE GOAL CONSTANT (Kept for reference/logging) ---
MIN_TOTAL_AVERAGE_GOALS = float(os.getenv("MIN_TOTAL_AVERAGE_GOALS", 3.0)) 
# --------------------------------------

# --- FILTER CONSTANTS (Kept) ---
AMATEUR_KEYWORDS = [
    'amateur', 'youth', 'reserve', 'friendly', 'u23', 'u21', 'u19', 
    'liga de reservas', 'division b', 'm-league', 'liga pro','u17'
]

# =========================================================
# 📌 INITIALIZATION FUNCTIONS
# =========================================================

def initialize_sofascore_client():
    """
    Initializes and sets the global SOFASCORE_CLIENT object.
    
    CRITICAL FIX: This now explicitly calls the initialize method on the
    SofascoreClient, which in turn starts the Playwright browser.
    """
    global SOFASCORE_CLIENT
    
    if SOFASCORE_CLIENT is not None: 
        logger.info("Sofascore client already initialized.")
        return True 

    logger.info("Attempting to initialize Sofascore client...")
    try:
        # 1. Instantiate the Client (Lightweight)
        SOFASCORE_CLIENT = SofascoreClient()
        
        # 2. Explicitly start the underlying Playwright Service (Heavy)
        SOFASCORE_CLIENT.initialize() 
        
        logger.info("Sofascore client successfully initialized and service is ready.")
        return True
    except Exception as e:
        logger.critical(f"FATAL: SofascoreClient failed to initialize. Error: {e}", exc_info=True)
        SOFASCORE_CLIENT = None
        return False

def initialize_bot_services():
    """Initializes all external services (Sofascore Client)."""
    
    logger.info("Initializing Football Betting Bot services...")
    
    # 1. Initialize the Sofascore Client
    if not initialize_sofascore_client():
        logger.critical("Bot cannot proceed. Sofascore client initialization failed.")
        return False
        
    logger.info("All bot services initialized successfully.")
    send_telegram("🚀 Football Betting Bot Initialized Successfully! Starting monitoring.")
    return True
    
def shutdown_bot():
    """Closes the Sofascore client resources gracefully. Crucial for Playwright stability."""
    global SOFASCORE_CLIENT
    if SOFASCORE_CLIENT:
        SOFASCORE_CLIENT.close()
        logger.info("Sofascore Client resources closed.")

# =========================================================
# 🟢 AVERAGE GOALS & TELEGRAM FUNCTIONS
# =========================================================

def _get_team_stats_safely(team_id: int, tournament_id: int) -> TeamTournamentStats:
    """
    Fetches, parses, and returns TeamTournamentStats, logging errors safely.
    Returns an empty TeamTournamentStats object if fetching fails.
    """
    if not SOFASCORE_CLIENT:
        logger.error("Client not initialized. Cannot fetch team stats.")
        return TeamTournamentStats(team_id=team_id, tournament_id=tournament_id)
        
    raw_stats = SOFASCORE_CLIENT.get_team_tournament_stats(team_id, tournament_id)
    if raw_stats:
        return parse_team_tournament_stats(team_id, tournament_id, raw_stats)
    
    logger.warning(f"Could not fetch raw stats for team {team_id} in tournament {tournament_id}. Returning empty stats.")
    return TeamTournamentStats(team_id=team_id, tournament_id=tournament_id)


def _get_average_goal_stats(event: Event) -> Dict[str, float]:
    """
    Calculates combined average goals and returns the stats.
    NOTE: This function performs CALCULATION only, not filtering.
    """
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
    
    # Calculate the total average goals across both teams
    total_avg_goals = home_stats.total_average_goals + away_stats.total_average_goals
    
    logger.info(
        f"Avg Goal Calc: {event.home_team.name} vs {event.away_team.name} | "
        f"Combined Avg: {total_avg_goals:.2f} (Min Ref: {MIN_TOTAL_AVERAGE_GOALS:.2f})"
    )

    # Return the stats
    return {
        'home_avg': home_stats.total_average_goals,
        'away_avg': away_stats.total_average_goals,
        'total_avg': total_avg_goals,
    }


def send_telegram(msg, max_retries=3):
    """Send Telegram message with retry mechanism"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(f"Telegram credentials missing. Message not sent: {msg}")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'} 
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Telegram error (attempt {attempt + 1}): {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Network Error sending Telegram message (attempt {attempt + 1}): {e}")
        
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)
    
    return False

# =========================================================
# 🏃 CORE LOGIC FUNCTIONS
# =========================================================

def get_live_matches():
    """Fetch ONLY live matches using the Sofascore client."""
    if not SOFASCORE_CLIENT:
        logger.error("Sofascore client is not initialized.")
        return []
    try:
        live_events = SOFASCORE_CLIENT.get_events(live=True) 
        logger.info(f"Fetched {len(live_events)} live matches.")
        return live_events
    except Exception as e:
        logger.error(f"Sofascore API Error fetching live matches: {e}")
        return []


def place_regular_bet(state, fixture_id, score, match_info, avg_goal_stats: Dict[str, float]):
    """
    Handles placing the initial 36' bet and storing its data locally.
    Includes avg goal stats in the Telegram message.
    """
    
    # Check local state (LOCAL_TRACKED_MATCHES) for an *unresolved* bet
    if LOCAL_TRACKED_MATCHES.get(fixture_id, {}).get('bet_status') == 'unresolved':
        logger.info(f"Regular bet already tracked as 'unresolved' for fixture {fixture_id}. Skipping placement.")
        return

    if score in ['1-1', '2-2', '3-3']:
        state['36_bet_placed'] = True
        state['36_score'] = score
        state['bet_status'] = 'unresolved' 
        LOCAL_TRACKED_MATCHES[fixture_id] = state 

        message = (
            f"⏱️ **36' - {match_info['match_name']}**\n"
            f"🌍 {match_info['country']} | 🏆 {match_info['league_name']}\n"
            f"🔢 Score: {score}\n"
            f"🎯 Correct Score Bet Placed for Half Time\n\n"
            
            f"📊 *Average Goal Stats* (Min Ref: {MIN_TOTAL_AVERAGE_GOALS:.2f}):\n"
            f"• *Home Avg*: {avg_goal_stats['home_avg']:.2f}\n"
            f"• *Away Avg*: {avg_goal_stats['away_avg']:.2f}\n"
            f"• *Total Avg*: {avg_goal_stats['total_avg']:.2f}"
        )
        send_telegram(message)
    else:
        state['36_bet_placed'] = True
        LOCAL_TRACKED_MATCHES[fixture_id] = state 


def check_ht_result(state, fixture_id, score, match_info):
    """Checks the result of locally tracked bets at halftime."""
    
    local_bet_data = LOCAL_TRACKED_MATCHES.get(fixture_id)

    if local_bet_data and local_bet_data.get('bet_status') == 'unresolved':
        
        current_score = score
        bet_score = local_bet_data.get('36_score', 'N/A')
        outcome = 'win' if current_score == bet_score else 'loss'
            
        country_name = match_info['country']
        league_name = match_info['league_name']
        
        if outcome == 'win':
            message = (
                f"✅ **HT Result: {match_info['match_name']}**\n"
                f"🌍 {country_name} | 🏆 {league_name}\n"
                f"🔢 HT Score: **{current_score}**\n"
                f"🎯 Bet Score: **{bet_score}**\n"
                f"🎉 36' Bet WON"
            )
        else:
            message = (
                f"❌ **HT Result: {match_info['match_name']}**\n"
                f"🌍 {country_name} | 🏆 {league_name}\n"
                f"🔢 HT Score: **{current_score}**\n"
                f"🎯 Bet Score: **{bet_score}**\n"
                f"🔁 36' Bet LOST"
            )
            
        send_telegram(message)
        
        local_bet_data['bet_status'] = 'resolved'
        LOCAL_TRACKED_MATCHES[fixture_id] = local_bet_data
        logger.info(f"Bet {fixture_id} resolved as {outcome} and marked locally.")
    

def process_live_match(match: Event):
    """
    Processes a single live match, calculating stats and checking betting conditions.
    """
    fixture_id = str(match.id) 
    
    # 0. Calculate Average Goals Stats (NO FILTER APPLIED)
    avg_goal_stats = _get_average_goal_stats(match)
    
    match_name = f"{match.home_team.name} vs {match.away_team.name}"

    # 1. AMATEUR TOURNAMENT FILTER LOGIC (RETAINED)
    tournament = match.tournament
    category_name = tournament.category.name if hasattr(tournament, 'category') and tournament.category else ''
    
    full_filter_text = (
        f"{tournament.name} "
        f"{category_name} "
        f"{match.home_team.name} "
        f"{match.away_team.name}"
    ).lower()

    if any(keyword in full_filter_text for keyword in AMATEUR_KEYWORDS):
        cleaned_text = full_filter_text.replace('\n', ' ')
        logger.info(f"Skipping amateur/youth league based on keyword found in: {cleaned_text}")
        return
    # END FILTERS

    minute = match.total_elapsed_minutes 
    status_description = match.status.description.upper()
    status = 'N/A' 
    
    if '1ST HALF' in status_description: status = '1H'
    elif '2ND HALF' in status_description: status = '2H'
    elif 'HALFTIME' in status_description: status = STATUS_HALFTIME
    elif 'FINISHED' in status_description or 'ENDED' in status_description or 'CANCELLED' in status_description: status = 'FT'
    elif status_description in STATUS_LIVE: status = status_description

    home_goals = match.home_score.current
    away_goals = match.away_score.current
    score = f"{home_goals}-{away_goals}"
    
    if status.upper() not in STATUS_LIVE and status.upper() != STATUS_HALFTIME: return
    
    # Get or create local state
    state = LOCAL_TRACKED_MATCHES.get(fixture_id) or {
        '36_bet_placed': False,
        '36_score': None,
        'bet_status': 'none' # 'none', 'unresolved', 'resolved'
    }
    LOCAL_TRACKED_MATCHES[fixture_id] = state

    match_info = {
        'match_name': match_name,
        'league_name': tournament.name if hasattr(match, 'tournament') else 'N/A',
        'country': tournament.category.name if hasattr(match, 'tournament') and hasattr(tournament, 'category') else 'N/A', 
        'league_id': tournament.id if hasattr(match, 'tournament') else 'N/A'
    }
        
    # 2. Bet Placement Check
    if status.upper() == '1H' and minute in MINUTES_REGULAR_BET and not state.get('36_bet_placed'):
        # Pass the calculated stats to the bet placement function
        place_regular_bet(state, fixture_id, score, match_info, avg_goal_stats)
        
    # 3. Halftime Resolution Check
    elif status.upper() == STATUS_HALFTIME and state.get('bet_status') == 'unresolved':
        check_ht_result(state, fixture_id, score, match_info)
        
    # 4. Cleanup (Finished matches)
    if status in STATUS_FINISHED and state.get('bet_status') in ['none', 'resolved']:
        if fixture_id in LOCAL_TRACKED_MATCHES:
            del LOCAL_TRACKED_MATCHES[fixture_id]
            logger.info(f"Cleaned up local tracking for finished fixture {fixture_id}.")


def run_bot_cycle():
    """Run one complete cycle of the bot"""
    logger.info("Starting bot cycle...")
    
    if not SOFASCORE_CLIENT:
        logger.error("Services are not initialized. Skipping cycle.")
        return
        
    live_matches = get_live_matches() 
    
    for match in live_matches:
        process_live_match(match)
    
    logger.info(f"Bot cycle completed. Currently tracking {len(LOCAL_TRACKED_MATCHES)} matches locally.")

if __name__ == "__main__":
    if initialize_bot_services():
        try:
            if not SOFASCORE_CLIENT:
                raise Exception("Sofascore Client not available after initialization.")
            
            while True:
                run_bot_cycle()
                logger.info(f"Sleeping for {SLEEP_TIME} seconds...")
                time.sleep(SLEEP_TIME)
        except KeyboardInterrupt:
            logger.info("Bot shutting down due to user interrupt.")
        except Exception as e:
            logger.critical(f"FATAL UNHANDLED ERROR IN MAIN LOOP: {e}", exc_info=True)
            send_telegram(f"❌ CRITICAL BOT ERROR: {e}. Check logs immediately!")
        finally:
            shutdown_bot()
            logger.info("Bot terminated.")
