# for local debugging
import os
from http.server import HTTPServer
import logging 

from api.webhook import TelegramBot
from api.webhook import handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is required!")
        return
    
    global bot_instance
    bot_instance = TelegramBot(BOT_TOKEN)
    
    port = int(os.getenv("PORT", 8000)) # or default 
    
    logger.info("Bot initialized successfully!")
    logger.info("Starting webhook server...")
    
    try:
        server_address = ('', port) # all address
        httpd = HTTPServer(server_address, handler)
        logger.info(f"Starting server on port {port}...")
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")


if __name__ == "__main__" :
    main()