import time
import signal
import sys
import logging
import os
import threading
from datetime import datetime
from flask import Flask, jsonify

# Import your bot logic
from bot import run_bot_cycle, SLEEP_TIME, initialize_bot_services, shutdown_bot

# ============================================
# FLASK APP FOR CLOUD RUN
# ============================================

app = Flask(__name__)
RUNNING = False
BOT_THREAD = None
CYCLE_COUNT = 0

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FootballBot")

# ============================================
# FLASK ROUTES
# ============================================

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "service": "football-betting-bot",
        "timestamp": datetime.now().isoformat(),
        "bot_status": "active" if RUNNING else "inactive"
    })

@app.route('/health')
def health():
    """Cloud Run health check endpoint"""
    if RUNNING and BOT_THREAD and not BOT_THREAD.is_alive():
        return jsonify({"status": "unhealthy", "reason": "Bot thread died"}), 503
    return jsonify({"status": "healthy"}), 200

@app.route('/status')
def status():
    return jsonify({
        "running": RUNNING,
        "thread_alive": BOT_THREAD.is_alive() if BOT_THREAD else False,
        "cycle_count": CYCLE_COUNT
    })

@app.route('/start', methods=['POST'])
def start_bot():
    global RUNNING, BOT_THREAD
    if RUNNING:
        return jsonify({"message": "Bot already running"}), 200
    
    RUNNING = True
    BOT_THREAD = threading.Thread(target=bot_main_loop, daemon=True)
    BOT_THREAD.start()
    return jsonify({"message": "Bot started"}), 200

@app.route('/stop', methods=['POST'])
def stop_bot():
    global RUNNING
    RUNNING = False
    return jsonify({"message": "Bot stopping"}), 200

# ============================================
# BOT LOGIC
# ============================================

def bot_main_loop():
    global RUNNING, CYCLE_COUNT
    
    logger.info("🤖 Bot main loop started")
    
    # Initialize services
    if not initialize_bot_services():
        logger.error("❌ Bot services initialization failed")
        return
    
    # Main loop
    while RUNNING:
        try:
            logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting cycle #{CYCLE_COUNT + 1}")
            run_bot_cycle()
            CYCLE_COUNT += 1
            logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Cycle #{CYCLE_COUNT} completed")
        except Exception as e:
            logger.error(f"Error in cycle: {e}")
        
        # Sleep but check RUNNING frequently
        for _ in range(SLEEP_TIME):
            if not RUNNING:
                break
            time.sleep(1)
    
    # Cleanup
    shutdown_bot()
    logger.info("👋 Bot thread terminated")

def signal_handler(signum, frame):
    global RUNNING
    logger.info(f"Received signal {signum}, shutting down...")
    RUNNING = False

# ============================================
# STARTUP
# ============================================

def start_bot_background():
    """Start bot in background thread"""
    global RUNNING, BOT_THREAD
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Auto-start based on environment variable
    auto_start = os.environ.get("AUTO_START_BOT", "true").lower() == "true"
    
    if auto_start:
        RUNNING = True
        BOT_THREAD = threading.Thread(target=bot_main_loop, daemon=True)
        BOT_THREAD.start()
        logger.info("🚀 Auto-started bot in background")

# Initialize on import
start_bot_background()

# This allows gunicorn to find the app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)