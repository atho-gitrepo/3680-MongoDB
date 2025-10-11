# bot.py

import requests
import os
import json
import time
import logging
from datetime import datetime, timedelta
# REMOVED: import firebase_admin
# REMOVED: from firebase_admin import credentials, firestore
# Correct import structure for your local library
from esd.sofascore import SofascoreClient, EntityType 

# --- GLOBAL VARIABLES ---
SOFASCORE_CLIENT = None 
# Renamed from firebase_manager to local_file_manager
local_file_manager = None 

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
API_KEY = os.getenv("API_KEY") 
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# REMOVED: FIREBASE_CREDENTIALS_JSON_STRING = os.getenv("FIREBASE_CREDENTIALS_JSON")

# --- CONSTANTS ---
SLEEP_TIME = 75
FIXTURE_API_INTERVAL = 900
MINUTES_REGULAR_BET = [36, 37]
# 32_over Bet Block Start
#MINUTES_32_MINUTE_BET = [32, 33]
# 32_over Bet Block End
# 80_minute Bet Block Start
#MINUTES_80_MINUTE_BET = [79, 80]
# 80_minute Bet Block End
BET_TYPE_REGULAR = 'regular'
# 32_over Bet Block Start
#BET_TYPE_32_OVER = '32_over' 
# 32_over Bet Block End
# 80_minute Bet Block Start
#BET_TYPE_80_MINUTE = '80_minute'
# 80_minute Bet Block End
STATUS_LIVE = ['LIVE', '1H', '2H', 'ET', 'P']
STATUS_HALFTIME = 'HT'
STATUS_FINISHED = ['FT', 'AET', 'PEN'] 
# 80_minute Bet Block Start
#BET_SCORES_80_MINUTE = ['3-1','2-0']
# 80_minute Bet Block End
MAX_FETCH_RETRIES = 3 
BET_RESOLUTION_WAIT_MINUTES = 180 

# --- LOCAL FILE CONSTANTS ---
TRACKED_MATCHES_FILE = 'tracked_matches.json'
UNRESOLVED_BETS_FILE = 'unresolved_bets.json'
RESOLVED_BETS_FILE = 'resolved_bets.json'
CONFIG_FILE = 'config.json'

# =========================================================
# 📌 INITIALIZATION FUNCTIONS (LocalFileManager)
# =========================================================

class LocalFileManager:
    """Manages all interactions with local JSON files."""
    def __init__(self):
        self._tracked_matches = self._load_data(TRACKED_MATCHES_FILE)
        self._unresolved_bets = self._load_data(UNRESOLVED_BETS_FILE)
        self._resolved_bets = self._load_data(RESOLVED_BETS_FILE)
        self._config = self._load_data(CONFIG_FILE)
        # Cache is now a reference to the main dict
        self._unresolved_bets_cache = self._unresolved_bets
        logger.info("Local File Manager initialized successfully.")

    def _load_data(self, filename: str) -> dict:
        """Helper to load data from a JSON file."""
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load data from {filename}: {e}. Starting with empty data.")
                return {}
        return {}

    def _save_data(self, data: dict, filename: str):
        """Helper to save data to a JSON file."""
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=4)
        except IOError as e:
            logger.error(f"Failed to save data to {filename}: {e}")

    # --- SAVE ALL DATA ---
    def save_all(self):
        """Saves all in-memory data to their respective files."""
        self._save_data(self._tracked_matches, TRACKED_MATCHES_FILE)
        self._save_data(self._unresolved_bets, UNRESOLVED_BETS_FILE)
        self._save_data(self._resolved_bets, RESOLVED_BETS_FILE)
        self._save_data(self._config, CONFIG_FILE)

    # --- UNRESOLVED BET METHODS ---
    def is_bet_unresolved(self, match_id: int or str) -> bool:
        """Checks for an unresolved bet using a direct dictionary lookup."""
        match_id_str = str(match_id)
        return match_id_str in self._unresolved_bets_cache

    def get_unresolved_bet_data(self, match_id: int or str) -> dict or None:
        """Retrieves an unresolved bet's data."""
        match_id_str = str(match_id)
        return self._unresolved_bets_cache.get(match_id_str)
            
    def get_stale_unresolved_bets(self, minutes_to_wait=BET_RESOLUTION_WAIT_MINUTES):
        """Finds unresolved bets that are older than the wait time."""
        stale_bets = {}
        time_threshold = datetime.utcnow() - timedelta(minutes=minutes_to_wait)
        
        for match_id, bet_info in self._unresolved_bets.items():
            if bet_info.get('bet_type') not in [BET_TYPE_REGULAR]:
                placed_at_str = bet_info.get('placed_at')
                if placed_at_str:
                    try:
                        placed_at_dt = datetime.strptime(placed_at_str, '%Y-%m-%d %H:%M:%S')
                        if placed_at_dt < time_threshold:
                            stale_bets[match_id] = bet_info
                    except ValueError:
                        logger.warning(f"Could not parse placed_at timestamp for bet {match_id}")
                        continue
        return stale_bets

    def add_unresolved_bet(self, match_id, data):
        """Adds a new bet to the unresolved list and saves to file."""
        match_id_str = str(match_id)
        data['placed_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        self._unresolved_bets[match_id_str] = data
        self.save_all()

    def move_to_resolved(self, match_id, bet_info, outcome):
        """Moves a bet from unresolved to resolved and saves to file."""
        match_id_str = str(match_id)
        resolved_data = {
            **bet_info,
            'outcome': outcome,
            'resolved_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'resolution_timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') 
        } 
        self._resolved_bets[match_id_str] = resolved_data
        self._unresolved_bets.pop(match_id_str, None) 
        self.save_all()
        return True

    # --- TRACKED MATCH METHODS ---
    def get_tracked_match(self, match_id):
        """Retrieves a tracked match's data."""
        return self._tracked_matches.get(str(match_id))

    def update_tracked_match(self, match_id, data):
        """Updates a tracked match's data."""
        match_id_str = str(match_id)
        current_data = self._tracked_matches.get(match_id_str, {})
        current_data.update(data)
        self._tracked_matches[match_id_str] = current_data
        self.save_all()
            
    def delete_tracked_match(self, match_id):
        """Deletes a tracked match and saves to file."""
        self._tracked_matches.pop(str(match_id), None)
        self.save_all()

    # --- CONFIG METHODS ---
    def get_last_api_call(self):
        """Retrieves the last API call timestamp from config."""
        return self._config.get('api_tracker', {}).get('last_resolution_api_call')

    def update_last_api_call(self):
        """Updates the last API call timestamp in config and saves to file."""
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        if 'api_tracker' not in self._config:
             self._config['api_tracker'] = {}
        self._config['api_tracker']['last_resolution_api_call'] = timestamp
        self.save_all()


def initialize_sofascore_client():
    """
    Initializes and sets the global SOFASCORE_CLIENT object.
    """
    global SOFASCORE_CLIENT
    
    if SOFASCORE_CLIENT is not None: 
        logger.info("Sofascore client already initialized.")
        return True 

    logger.info("Attempting to initialize Sofascore client...")
    try:
        SOFASCORE_CLIENT = SofascoreClient()
        SOFASCORE_CLIENT.initialize() 
        logger.info("Sofascore client successfully initialized.")
        return True
    except Exception as e:
        logger.critical(f"FATAL: SofascoreClient failed to initialize. Error: {e}", exc_info=True)
        SOFASCORE_CLIENT = None
        return False

# =========================================================
# 🏃 CORE LOGIC FUNCTIONS
# =========================================================

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

def initialize_bot_services():
    """Initializes all external services (Local File Manager and Sofascore Client)."""
    global local_file_manager

    logger.info("Initializing Football Betting Bot services...")
    
    # 1. Initialize Local File Manager
    try:
        local_file_manager = LocalFileManager()
    except Exception as e:
        logger.critical(f"Bot cannot proceed. Local File Manager initialization failed: {e}")
        return False
        
    if local_file_manager is None:
         logger.critical("Bot cannot proceed. Local File Manager initialization failed.")
         return False

    # 2. Initialize the Sofascore Client
    if not initialize_sofascore_client():
        logger.critical("Bot cannot proceed. Sofascore client initialization failed.")
        return False
        
    logger.info("All bot services initialized successfully.")
    # This call is now safe because send_telegram is defined above this function
    send_telegram("🚀 Football Betting Bot Initialized Successfully! Starting monitoring.")
    return True
    
def shutdown_bot():
    """Closes the Sofascore client resources gracefully and saves data."""
    global SOFASCORE_CLIENT
    global local_file_manager

    # Save all data one last time on shutdown
    if local_file_manager:
        logger.info("Saving final state to local files...")
        local_file_manager.save_all()

    if SOFASCORE_CLIENT:
        SOFASCORE_CLIENT.close()
        logger.info("Sofascore Client resources closed.")

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
        
def get_finished_match_details(sofascored_id):
    """
    Fetches the full event details for a match ID using the active Sofascore client.
    """
    if not SOFASCORE_CLIENT: 
        logger.error("Sofascore client is not initialized.")
        return None
    
    sofascored_id = int(sofascored_id) 
    
    try:
        match_data = SOFASCORE_CLIENT.get_event(sofascored_id)
        
        if match_data and match_data.id == sofascored_id:
            return match_data
        
        logger.warning(f"Failed to fetch event {sofascored_id} via get_event. Returned data was invalid or mismatched ID.")
        return None
        
    except Exception as e:
        logger.error(f"Sofascore Client Error fetching finished event {sofascored_id}: {e}")
        return None

def robust_get_finished_match_details(sofascored_id):
    """
    Wrapper to attempt fetching match details with retries and client refresh on persistent failure.
    """
    global SOFASCORE_CLIENT
    
    for attempt in range(MAX_FETCH_RETRIES):
        result = get_finished_match_details(sofascored_id)
        if result:
            if attempt > 0:
                logger.info(f"Successfully fetched {sofascored_id} on attempt {attempt + 1}.")
            return result
        
        if attempt == MAX_FETCH_RETRIES - 1:
            logger.error(f"Permanent failure fetching {sofascored_id} after {MAX_FETCH_RETRIES} attempts. Attempting full client restart.")
            try:
                if SOFASCORE_CLIENT:
                    SOFASCORE_CLIENT.close()
                    SOFASCORE_CLIENT = None 
                initialize_sofascore_client()
                final_result = get_finished_match_details(sofascored_id)
                if final_result:
                    logger.info(f"Successfully fetched {sofascored_id} after client restart.")
                    return final_result
            except Exception as e:
                logger.critical(f"FATAL: Client restart failed for {sofascored_id}: {e}")
            
        
        logger.warning(f"Failed to fetch final data for Sofascore ID {sofascored_id}. Retrying in {2 ** attempt}s (Attempt {attempt + 1}/{MAX_FETCH_RETRIES}).")
        time.sleep(2 ** attempt)
        
    return None

def place_regular_bet(state, fixture_id, score, match_info):
    """Handles placing the initial 36' bet."""
    
    if local_file_manager.is_bet_unresolved(fixture_id):
        logger.info(f"Regular bet already exists in 'unresolved_bets' for fixture {fixture_id}. Skipping placement and Telegram message.")
        if not state.get('36_bet_placed'):
            state['36_bet_placed'] = True
            local_file_manager.update_tracked_match(fixture_id, state)
        return

    if score in ['1-1', '2-2', '3-3']:
        state['36_bet_placed'] = True
        state['36_score'] = score
        local_file_manager.update_tracked_match(fixture_id, state)
        unresolved_data = {
            'match_name': match_info['match_name'],
            'placed_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'league': match_info['league_name'],
            'country': match_info['country'],
            'league_id': match_info['league_id'],
            'bet_type': BET_TYPE_REGULAR,
            '36_score': score,
            'fixture_id': fixture_id,
            'sofascored_id': fixture_id 
        }
        local_file_manager.add_unresolved_bet(fixture_id, unresolved_data)
        
        message = (
            f"⏱️ **36' - {match_info['match_name']}**\n"
            f"🌍 {match_info['country']} | 🏆 {match_info['league_name']}\n"
            f"🔢 Score: {score}\n"
            f"🎯 Correct Score Bet Placed for Half Time"
        )
        send_telegram(message)
    else:
        state['36_bet_placed'] = True
        local_file_manager.update_tracked_match(fixture_id, state)


def check_ht_result(state, fixture_id, score, match_info):
    """Checks the result of all placed bets at halftime, skipping 32' over bets."""
    
    current_score = score
    unresolved_bet_data = local_file_manager.get_unresolved_bet_data(fixture_id) 

    if unresolved_bet_data:
        bet_type = unresolved_bet_data.get('bet_type')
        outcome = None
        message = ""

        country_name = unresolved_bet_data.get('country', 'N/A') 
        league_name = unresolved_bet_data.get('league', 'N/A')
        
        if bet_type == BET_TYPE_REGULAR:
            bet_score = unresolved_bet_data.get('36_score', 'N/A')
            outcome = 'win' if current_score == bet_score else 'loss'
            
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
            
        # 32_over Bet Block Start
        #elif bet_type == BET_TYPE_32_OVER:
            #logger.info(f"Skipping HT resolution for 32' Over bet on fixture {fixture_id}. Awaiting FT.")
            #return 
        # 32_over Bet Block End
            
        if outcome:
            local_file_manager.move_to_resolved(fixture_id, unresolved_bet_data, outcome)
            send_telegram(message)
    
    if not local_file_manager.is_bet_unresolved(fixture_id):
        local_file_manager.delete_tracked_match(fixture_id)

# 80_minute Bet Block Start
#def place_80_minute_bet(state, fixture_id, score, match_info, actual_minute):
    #"""Handles placing the new 80' bet."""
    #if local_file_manager.is_bet_unresolved(fixture_id):
        #logger.info(f"80_minute bet already exists in 'unresolved_bets' for fixture {fixture_id}. Skipping placement and Telegram message.")
        #if not state.get('80_bet_placed'):
            #state['80_bet_placed'] = True
            #local_file_manager.update_tracked_match(fixture_id, state)
        #return
    #if score in BET_SCORES_80_MINUTE:
        #state['80_bet_placed'] = True
        #state['80_score'] = score
        #local_file_manager.update_tracked_match(fixture_id, state)
        #unresolved_data = {
            #'match_name': match_info['match_name'],
            #'placed_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            #'league': match_info['league_name'],
            #'country': match_info['country'],
            #'league_id': match_info['league_id'],
            #'bet_type': BET_TYPE_80_MINUTE,
            #'80_score': score,
            #'fixture_id': fixture_id,
            #'sofascored_id': fixture_id 
        #}
        #local_file_manager.add_unresolved_bet(fixture_id, unresolved_data)
        #message = (
            #f"⏱️ **80' - {match_info['match_name']}**\n"
            #f"🌍 {match_info['country']} | 🏆 {match_info['league_name']}\n"
            #f"🔢 Score: {score}\n"
            #f"🎯 80' Correct Score Bet Placed for Full Time"
        #)
        #send_telegram(message)
    #else:
        #state['80_bet_placed'] = True
        #local_file_manager.update_tracked_match(fixture_id, state)
# 80_minute Bet Block End

def process_live_match(match):
    """
    Processes a single live match using the Sofascore object structure.
    """
    fixture_id = match.id 
    match_name = f"{match.home_team.name} vs {match.away_team.name}"
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
    if minute is None and status.upper() not in [STATUS_HALFTIME]: return
    
    state = local_file_manager.get_tracked_match(fixture_id) or {
        '36_bet_placed': False,
        # 32_over Bet Block Start
        #'32_bet_placed': False, 
        # 32_over Bet Block End
        # 80_minute Bet Block Start
        #'80_bet_placed': False,
        # 80_minute Bet Block End
        '36_score': None,
        # 80_minute Bet Block Start
        #'80_score': None,
        # 80_minute Bet Block End
    }
    
    match_info = {
        'match_name': match_name,
        'league_name': match.tournament.name if hasattr(match, 'tournament') else 'N/A',
        'country': match.tournament.category.name if hasattr(match, 'tournament') and hasattr(match.tournament, 'category') else 'N/A', 
        'league_id': match.tournament.id if hasattr(match, 'tournament') else 'N/A'
    }
        
    # 32_over Bet Block Start
    #if status.upper() == '1H' and minute in MINUTES_32_MINUTE_BET and not state.get('32_bet_placed'):
        #place_32_over_bet(state, fixture_id, score, match_info) 
    # 32_over Bet Block End
        
    if status.upper() == '1H' and minute in MINUTES_REGULAR_BET and not state.get('36_bet_placed'):
        place_regular_bet(state, fixture_id, score, match_info)
        
    elif status.upper() == STATUS_HALFTIME and local_file_manager.is_bet_unresolved(fixture_id):
        check_ht_result(state, fixture_id, score, match_info)
        
    # 80_minute Bet Block Start
    #elif status.upper() == '2H' and minute is not None and minute >= 79 and not state.get('80_bet_placed'):
        #place_80_minute_bet(state, fixture_id, score, match_info, minute)
    # 80_minute Bet Block End
    
    if status in STATUS_FINISHED and not local_file_manager.is_bet_unresolved(fixture_id):
        local_file_manager.delete_tracked_match(fixture_id)


def check_and_resolve_stale_bets():
    """
    Checks and resolves old, unresolved bets by fetching their final status.
    """
    stale_bets = local_file_manager.get_stale_unresolved_bets(BET_RESOLUTION_WAIT_MINUTES)
    if not stale_bets:
        return
    
    last_call_str = local_file_manager.get_last_api_call()
    last_call_dt = None
    if last_call_str:
        try:
            last_call_dt = datetime.strptime(last_call_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            logger.warning("Could not parse last_resolution_api_call timestamp. Proceeding with API call.")

    time_since_last_call = (datetime.utcnow() - last_call_dt).total_seconds() if last_call_dt else FIXTURE_API_INTERVAL + 1
    
    if time_since_last_call < FIXTURE_API_INTERVAL:
        logger.info(f"Skipping FT resolution API call. Last call was {int(time_since_last_call)}s ago. Next in {int(FIXTURE_API_INTERVAL - time_since_last_call)}s.")
        return

    logger.info(f"Initiating FT resolution API calls for {len(stale_bets)} stale bets.")
    successful_api_call = False
    
    for match_id, bet_info in stale_bets.items():
        sofascored_id = bet_info.get('sofascored_id', match_id) 

        match_data = robust_get_finished_match_details(sofascored_id)
        
        if not match_data:
            logger.warning(f"Failed to fetch final data for fixture {match_id} (Sofascore ID: {sofascored_id}). Will retry on next interval.")
            continue
        
        successful_api_call = True 

        status_description = match_data.status.description.upper()
        
        if 'FINISHED' in status_description or 'ENDED' in status_description:
            final_score = f"{match_data.home_score.current or 0}-{match_data.away_score.current or 0}"
            match_name = bet_info.get('match_name', f"Match {match_id}")
            bet_type = bet_info.get('bet_type', 'unknown')
            
            country_name = bet_info.get('country', 'N/A') 
            league_name = bet_info.get('league', 'N/A') 
            
            outcome = None
            message = ""

            # 80_minute Bet Block Start
            #if bet_type == BET_TYPE_80_MINUTE:
                #bet_score = bet_info.get('80_score')
                #outcome = 'win' if final_score == bet_score else 'loss'
                #message = (
                    #f"🏁 **FINAL RESULT - 80' Bet**\n"
                    #f"⚽ {match_name}\n"
                    #f"🌍 {country_name} | 🏆 {league_name}\n"
                    #f"🔢 Final Score: {final_score}\n"
                    #f"🎯 Bet on 80' Score: {bet_score}\n"
                    #f"📊 Outcome: {'✅ WON' if outcome == 'win' else '❌ LOST'}"
                #)
            # 80_minute Bet Block End
            # 32_over Bet Block Start
            #elif bet_type == BET_TYPE_32_OVER:
                #over_line = bet_info.get('over_line')
                #try:
                    #home_goals, away_goals = map(int, final_score.split('-'))
                    #total_goals = home_goals + away_goals
                    
                    #if total_goals > over_line: outcome = 'win'
                    #elif total_goals < over_line: outcome = 'loss'
                    #else: outcome = 'push'
                        
                    #message = (
                        #f"🏁 **FINAL RESULT - 32' Over Bet**\n"
                        #f"⚽ {match_name}\n"
                        #f"🌍 {country_name} | 🏆 {league_name}\n"
                        #f"🔢 Final Score: {final_score}\n"
                        #f"🎯 Bet: Over {over_line}\n"
                        #f"📊 Outcome: {'✅ WON' if outcome == 'win' else '❌ LOST' if outcome == 'loss' else '➖ PUSH'}"
                    #)
                #except ValueError:
                    #outcome = 'error'
                    #message = f"⚠️ FINAL RESULT: {match_name}\n❌ Bet could not be resolved due to score format issue."
            # 32_over Bet Block End

            
            if outcome and outcome != 'error':
                if send_telegram(message):
                    local_file_manager.move_to_resolved(match_id, bet_info, outcome)
                    local_file_manager.delete_tracked_match(match_id) 
                time.sleep(1)
        
        else:
            logger.info(f"Match {match_id} is stale but not yet finished. Current status: {status_description}. Retrying later.")

    if successful_api_call:
        local_file_manager.update_last_api_call()
        
def run_bot_cycle():
    """Run one complete cycle of the bot"""
    logger.info("Starting bot cycle...")
    
    if not SOFASCORE_CLIENT or not local_file_manager:
        logger.error("Services are not initialized. Skipping cycle.")
        return
        
    live_matches = get_live_matches() 
    
    for match in live_matches:
        process_live_match(match)
    
    check_and_resolve_stale_bets()
    
    logger.info("Bot cycle completed.")

if __name__ == "__main__":
    if initialize_bot_services():
        try:
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
