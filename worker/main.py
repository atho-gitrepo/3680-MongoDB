import time
import signal
import sys
import logging
import os
import threading
import http.server
import socketserver
from datetime import datetime
from bot import run_bot_cycle, SLEEP_TIME, initialize_bot_services, shutdown_bot

logger = logging.getLogger("MainExecutor")
logger.setLevel(logging.INFO)

RUNNING = True
CHECK_INTERVAL = SLEEP_TIME

# --- NEW: HEALTH CHECK SERVER FOR CLOUD RUN ---
def run_health_server():
    """Starts a simple server to satisfy Cloud Run's port requirement."""
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    # This prevents 'Address already in use' errors on restarts
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"📡 Health check server active on port {port}")
        httpd.serve_forever()

def signal_handler(signum, frame):
    global RUNNING
    logger.warning(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Signal {signum} received.")
    RUNNING = False

def main():
    print("🚀 Football Betting Bot Executor Started")
    
    # 1. Start Health Check Thread
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # 2. Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 3. Initialize Bot Services
    if not initialize_bot_services():
        print("❌ FATAL: Bot services failed to initialize.")
        sys.exit(1)
    
    # 4. MAIN EXECUTION LOOP
    while RUNNING:
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🤖 Starting bot cycle...")
            run_bot_cycle() 
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Cycle complete.")
            
        except Exception as e:
            logger.critical(f"Unexpected error in cycle: {e}", exc_info=True)
            
        finally:
            if RUNNING: 
                time.sleep(CHECK_INTERVAL)

    # 5. GRACEFUL SHUTDOWN
    shutdown_bot()
    sys.exit(0)

if __name__ == "__main__":
    main()
