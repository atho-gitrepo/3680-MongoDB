import time
import signal
import sys
import logging
import os
import threading
import json
from datetime import datetime
from flask import Flask, jsonify, request
import requests

# Import your bot logic
from bot import run_bot_cycle, SLEEP_TIME, initialize_bot_services, shutdown_bot

# ============================================
# CONFIGURATION
# ============================================

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FootballBotCloudRun")

# Flask app for Cloud Run
app = Flask(__name__)

# Global state
RUNNING = False
BOT_THREAD = None
CYCLE_COUNT = 0
LAST_ERROR = None

# ============================================
# FLASK ROUTES FOR CLOUD RUN
# ============================================

@app.route('/')
def home():
    """Root endpoint"""
    return jsonify({
        "status": "running",
        "service": "football-betting-bot",
        "timestamp": datetime.now().isoformat(),
        "bot_status": "active" if RUNNING else "inactive",
        "cycle_count": CYCLE_COUNT,
        "health": "healthy",
        "environment": os.environ.get("ENVIRONMENT", "production")
    })

@app.route('/health')
def health():
    """Cloud Run health check endpoint (required)"""
    try:
        # Check if bot thread is alive
        if RUNNING and (not BOT_THREAD or not BOT_THREAD.is_alive()):
            return jsonify({"status": "unhealthy", "reason": "Bot thread died"}), 503
        
        # Basic health check
        return jsonify({"status": "healthy"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/status')
def status():
    """Detailed bot status"""
    return jsonify({
        "running": RUNNING,
        "thread_alive": BOT_THREAD.is_alive() if BOT_THREAD else False,
        "cycle_count": CYCLE_COUNT,
        "last_error": LAST_ERROR,
        "sleeptime_seconds": SLEEP_TIME,
        "uptime": get_uptime() if hasattr(status, 'start_time') else "unknown"
    })

@app.route('/start', methods=['POST'])
def start_bot():
    """Start the bot"""
    global RUNNING, BOT_THREAD
    
    if RUNNING and BOT_THREAD and BOT_THREAD.is_alive():
        return jsonify({"message": "Bot already running", "status": "running"}), 200
    
    RUNNING = True
    BOT_THREAD = threading.Thread(target=bot_main_loop, daemon=True)
    BOT_THREAD.start()
    
    logger.info("🚀 Bot started via API")
    return jsonify({"message": "Bot started successfully", "status": "started"}), 200

@app.route('/stop', methods=['POST'])
def stop_bot():
    """Gracefully stop the bot"""
    global RUNNING
    
    if not RUNNING:
        return jsonify({"message": "Bot not running", "status": "stopped"}), 200
    
    RUNNING = False
    
    # Wait for bot thread to finish
    if BOT_THREAD and BOT_THREAD.is_alive():
        BOT_THREAD.join(timeout=30)
    
    logger.info("🛑 Bot stopped via API")
    return jsonify({"message": "Bot stopping gracefully", "status": "stopping"}), 200

@app.route('/cycle', methods=['POST'])
def trigger_cycle():
    """Manually trigger a single bot cycle"""
    try:
        logger.info("🔄 Manually triggered bot cycle")
        run_bot_cycle()
        return jsonify({"message": "Cycle completed successfully"}), 200
    except Exception as e:
        logger.error(f"Manual cycle failed: {e}")
        return jsonify({"message": f"Cycle failed: {str(e)}"}), 500

# ============================================
# BOT EXECUTION LOGIC
# ============================================

def bot_main_loop():
    """Main bot execution loop (runs in background thread)"""
    global RUNNING, CYCLE_COUNT, LAST_ERROR
    
    logger.info("🤖 Bot main loop started")
    
    # Initialize services
    try:
        if not initialize_bot_services():
            logger.error("❌ Bot services initialization failed")
            LAST_ERROR = "Initialization failed"
            RUNNING = False
            return
    except Exception as e:
        logger.error(f"❌ Initialization error: {e}")
        LAST_ERROR = str(e)
        RUNNING = False
        return
    
    # MAIN EXECUTION LOOP
    while RUNNING:
        try:
            cycle_start = datetime.now()
            logger.info(f"[{cycle_start.strftime('%Y-%m-%d %H:%M:%S')}] 🔄 Starting bot cycle #{CYCLE_COUNT + 1}")
            
            run_bot_cycle()
            
            CYCLE_COUNT += 1
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            
            logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Cycle #{CYCLE_COUNT} completed in {cycle_duration:.1f}s")
            
        except Exception as e:
            logger.critical(f"❌ Unexpected error in cycle: {e}", exc_info=True)
            LAST_ERROR = str(e)
            
        finally:
            if RUNNING: 
                # Calculate sleep time, but don't sleep if we're stopping
                sleep_time = SLEEP_TIME
                for _ in range(sleep_time):
                    if not RUNNING:
                        break
                    time.sleep(1)
    
    # GRACEFUL SHUTDOWN
    logger.info("🛑 Shutting down bot resources...")
    try:
        shutdown_bot()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    logger.info("👋 Bot thread terminated")

def signal_handler(signum, frame):
    """Handle shutdown signals from Cloud Run"""
    global RUNNING
    logger.warning(f"⚠️ Received signal {signum}. Initiating graceful shutdown...")
    RUNNING = False

# ============================================
# UTILITY FUNCTIONS
# ============================================

def get_uptime():
    """Calculate application uptime"""
    if not hasattr(get_uptime, 'start_time'):
        get_uptime.start_time = datetime.now()
    
    delta = datetime.now() - get_uptime.start_time
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    else:
        return f"{minutes}m {seconds}s"

# ============================================
# APPLICATION STARTUP
# ============================================

def start_bot_background():
    """Start the bot in a background thread on startup"""
    global RUNNING, BOT_THREAD
    
    # Check if we should auto-start bot
    auto_start = os.environ.get("AUTO_START_BOT", "true").lower() == "true"
    
    if auto_start:
        logger.info("🔄 Auto-starting bot on initialization")
        RUNNING = True
        BOT_THREAD = threading.Thread(target=bot_main_loop, daemon=True)
        BOT_THREAD.start()
    else:
        logger.info("⏸️ Bot auto-start disabled. Use POST /start to begin.")
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

# ============================================
# CLOUD RUN ENTRY POINT
# ============================================

# Initialize bot when module loads
start_bot_background()

# This allows gunicorn to find the app
if __name__ == "__main__":
    # Local development
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🌐 Starting Flask server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)