import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from http.server import BaseHTTPRequestHandler
from api.webhook import TelegramBot
from api.database import ScheduleManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# class ScheduleChecker:
#     def __init__(self):
#         self.bot_token = os.getenv("BOT_TOKEN")
#         self.bot_username = os.getenv("BOT_USERNAME")
#         self.manager = ScheduleManager()
#         self.webhook = TelegramBot()
#         self.chat_id = os.getenv("CHAT_ID")

#     def send_message(self, text, chat_id, parse_mode="Markdown"):
#         url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
#         payload = {
#             "chat_id": chat_id,
#             "text": text,
#             "parse_mode": parse_mode
#         }
        
#         try:
#             response = requests.post(url, json=payload)
#             if response.status_code != 200:
#                 logger.error(f"Failed to send message: {response.text}")
#                 return False
#             return True
#         except Exception as e:
#             logger.error(f"Error sending message: {str(e)}")
#             return False

#     def check_schedules(self):
#         try:
#             current_time = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")
#             logger.info(f"{current_time} : Running schedule check")
            
#             schedule_data = self.manager.check_schedules()
#             self.process_schedule_data(schedule_data)
            
#             return {"status": "success", "message": "Schedule check completed"}
            
#         except Exception as e:
#             logger.error(f"Error in check_schedules: {str(e)}")
#             return {"status": "error", "message": str(e)}

#     def process_schedule_data(self, schedule_data):
#         upcoming_schedules = schedule_data.get("upcoming", [])
#         if not upcoming_schedules:
#             logger.info("No schedules found, skipping notification")
#             return
        
#         logger.info(f"Found schedules - Upcoming: {len(upcoming_schedules)}")
#         try:
#             current_message = self.format_schedule_message(upcoming_schedules)
#             logger.info(f"Sending notification for current schedules: {upcoming_schedules}")
#             self.send_message(current_message, self.chat_id)
#         except Exception as e:
#             logger.error(f"Error processing current schedules: {str(e)}")

#     def format_schedule_message(self, schedules):
#         header = "⚠️ *JADWAL MENDATANG :*\n\n"
#         message = header
#         for idx, schedule in enumerate(schedules, 1):
#             activity = schedule.get("activity", "")
#             time = schedule.get("time", "")
#             message += f"{idx}. {activity} - {time}\n"
        
#         return message

class handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        try:
            # checker = ScheduleChecker()
            webhook = TelegramBot()
            result = webhook.check_schedules()
            
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
        try:
            # checker = ScheduleChecker()
            # result = checker.check_schedules()
            webhook = TelegramBot()
            result = webhook.check_schedules()
            
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