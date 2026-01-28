import time
import signal
import sys
import logging
import os
import threading
import http.server
import socketserver
from datetime import datetime

# Import your bot logic
from bot import run_bot_cycle, SLEEP_TIME, initialize_bot_services, shutdown_bot

# Logger setup
logger = logging.getLogger("MainExecutor")
logging.basicConfig(level=logging.INFO)

RUNNING = True
CHECK_INTERVAL = SLEEP_TIME

def run_health_server():
    """
    Cloud Run requires a web server to be listening on $PORT.
    This simple server satisfies that requirement.
    """
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"📡 Health check server active on port {port}")
        httpd.serve_forever()

def signal_handler(signum, frame):
    global RUNNING
    logger.warning(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Signal {signum} received. Cleaning up...")
    RUNNING = False

def main():
    print("🚀 Football Betting Bot Executor Started")
    
    # 1. Start the Cloud Run Health Check in a background thread
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # 2. Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 3. Initialize Bot Services
    if not initialize_bot_services():
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ FATAL: Initialization failed.")
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
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 💤 Sleeping for {CHECK_INTERVAL}s...")
                time.sleep(CHECK_INTERVAL)

    # 5. GRACEFUL SHUTDOWN
    print("Shutting down bot resources...")
    shutdown_bot()
    sys.exit(0)

if __name__ == "__main__":
    main()
