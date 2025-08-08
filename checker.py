import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from http.server import BaseHTTPRequestHandler

# Import your existing modules
from database import ScheduleManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScheduleChecker:
    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN")
        self.bot_username = os.getenv("BOT_USERNAME")
        self.manager = ScheduleManager()

    def send_message(self, text, parse_mode="Markdown"):
        """Send message to Telegram using API"""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            # "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            response = requests.post(url, json=payload)
            if response.status_code != 200:
                logger.error(f"Failed to send message: {response.text}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return False

    def check_schedules(self):
        """Check schedules and send notifications"""
        try:
            current_time = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"{current_time} : Running schedule check")
            
            schedule_data = self.manager.check_schedules()
            self.process_schedule_data(schedule_data)
            
            return {"status": "success", "message": "Schedule check completed"}
            
        except Exception as e:
            logger.error(f"Error in check_schedules: {str(e)}")
            return {"status": "error", "message": str(e)}

    def process_schedule_data(self, schedule_data):
        """Process schedule data and send notifications"""
        upcoming_schedules = schedule_data.get("upcoming", [])
        if not upcoming_schedules:
            logger.info("No schedules found, skipping notification")
            return
        
        logger.info(f"Found schedules - Upcoming: {len(upcoming_schedules)}")
        try:
            current_message = self.format_schedule_message(upcoming_schedules)
            logger.info(f"Sending notification for current schedules: {upcoming_schedules}")
            self.send_message(current_message)
        except Exception as e:
            logger.error(f"Error processing current schedules: {str(e)}")

    def format_schedule_message(self, schedules):
        """Format schedule message for notification"""
        header = "⚠️ *JADWAL MENDATANG :*\n\n"
        
        message = header
        for idx, schedule in enumerate(schedules, 1):
            activity = schedule.get("activity", "")
            time = schedule.get("time", "")
            message += f"{idx}. {activity} - {time}\n"
        
        return message

# Vercel handler for schedule checking
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Initialize schedule checker
            checker = ScheduleChecker()
            
            # Run schedule check
            result = checker.check_schedules()
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            
        except Exception as e:
            logger.error(f"Error in schedule check handler: {str(e)}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())

    def do_GET(self):
        # Health check endpoint
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "Schedule checker is running"}).encode())