import json
import re
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import pg8000
import requests
from http.server import BaseHTTPRequestHandler
from dotenv import load_dotenv

# Import your existing modules
from api.database import ScheduleManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token: str):
        self.bot_token = token  
        self.bot_username = os.getenv("BOT_USERNAME")
        self.chat_id = None
        self.manager = ScheduleManager()

    def send_message(self, chat_id, text, parse_mode="Markdown"):
        """Send message to Telegram using API"""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
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

    def handle_message(self, message_text, chat_id):
        """Handle incoming message and return response"""
        message_text = message_text.strip()
        
        try:
            # Route message to appropriate handler
            if message_text.lower().startswith('tambah'):
                return self.process_add_command(message_text)
            elif message_text.lower() in ('jadwal hari ini', 'hari ini') :
                return self.today()
            elif message_text.lower() in ('jadwal minggu ini', 'minggu ini'):
                return self.week()
            elif message_text.lower().startswith(('ganti nama', 'update nama')):
                return self.update_name(message_text)
            elif message_text.lower().startswith(('ganti tanggal', 'update tanggal')):
                return self.update_date(message_text)
            elif message_text.lower().startswith('hapus'):
                return self.delete_activity(message_text)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            return "Terjadi kesalahan saat memproses perintah."

    def process_add_command(self, message_body):
        pattern = r'^tambah(\s+.+?)\s+jam\s+(\d{1,2}:\d{2})(?:\s+tanggal\s+(\d{1,2})(?:\s+(\w+))?)?$'
        match = re.match(pattern, message_body, re.IGNORECASE)
        
        if not match:
            return "Format pesan salah. Contoh: *Tambah [aktivitas] jam [HH:MM] tanggal [DD] [Bulan]*"
        
        activity = match.group(1).strip()
        time = match.group(2).strip()
        date = match.group(3).strip() if match.group(3) else None
        month = match.group(4).strip() if match.group(4) else None

        try:
            response = self.manager.add_schedule(time=time, date=date, month=month, activity=activity)
        except pg8000.IntegrityError as e:
            response = f"DB constraint error: {e}"
        except ValueError as e:
            response = f"Validation error: {e}"
        except Exception as e:
            response = f"Unexpected error: {e}"
        
        return response

    def today(self): 
        day_info, schedules = self.manager.get_today_schedules()

        if schedules:
            response = f"Jadwal untuk {day_info}:\n"
            for time, activity in schedules:
                response += f"- {time}: {activity}\n"
        else:
            response = f"Tidak ada jadwal untuk {day_info}"
            
        return response

    def week(self): 
        all_schedules = self.manager.get_weekly_schedules()
            
        if not all_schedules:
            return "Tidak ada jadwal untuk minggu ini."
        
        grouped_schedules = {}
        for time, activity, date, month in all_schedules:
            day_key = f"{date} {month}"
            if day_key not in grouped_schedules:
                grouped_schedules[day_key] = []
            grouped_schedules[day_key].append((time, activity))
        
        response = "Jadwal minggu ini:\n\n"
        for day_key, schedules in grouped_schedules.items():
            response += f"🗓️ {day_key}:\n"
            for time, activity in schedules:
                response += f"⏰ {time} - {activity}\n"
            response += "\n"
        
        return response.strip()

    def update_name(self, message_body): 
        pattern = r'^(?:ganti nama|update nama)\s+(.+?)\s+menjadi\s+(.+?)(?:\s+tanggal\s+(\d{1,2})(?:\s+(\w+))?)?$'
        match = re.match(pattern, message_body, re.IGNORECASE)
        
        if not match:
            return "Format pesan salah. Contoh: *ganti nama [aktivitas lama] menjadi [aktivitas baru] tanggal [DD] [Bulan]*"
        
        old_activity = match.group(1).strip()
        new_activity = match.group(2).strip()
        date = match.group(3).strip() if match.group(3) else None
        month = match.group(4).strip() if match.group(4) else None
        
        try:
            success = self.manager.update_activity_name(
                activity=old_activity, 
                date=date, 
                month=month, 
                new_activity=new_activity
            )
            if success:
                return f"Jadwal '{old_activity}' berhasil diubah menjadi '{new_activity}'."
            else:
                return f"Jadwal '{old_activity}' tidak ditemukan."
        except ValueError as e:
            return f"Validation error: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"
        
    def update_date(self, message_body): 
        pattern = r'^(?:ganti tanggal|update tanggal)\s+(.+?)\s+dari\s+(\d{1,2})\s+menjadi\s+(\d{1,2})(?:\s+(\w+))?$'
        match = re.match(pattern, message_body, re.IGNORECASE)
        
        if not match:
            return "Format pesan salah. Contoh: *ganti tanggal [aktivitas] dari [tanggal lama] menjadi [tanggal baru] [Bulan]*"
        
        activity = match.group(1).strip()
        old_date = match.group(2).strip()
        new_date = match.group(3).strip()
        month = match.group(4).strip().lower() if match.group(4) else None
        
        try:
            success = self.manager.update_schedule_time(
                activity=activity, 
                date=old_date, 
                new_date=new_date, 
                month=month
            )
            if success:
                return f"Jadwal '{activity}' berhasil diubah dari tanggal {old_date} ke tanggal {new_date}."
            else:
                return f"Jadwal '{activity}' pada tanggal {old_date} tidak ditemukan."
                
        except ValueError as e:
            return f"Validation error: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"
        
    def delete_activity(self, message_body):
        pattern = r'^hapus\s+(.+?)(?:\s+tanggal\s+(\d{1,2})(?:\s+(\w+))?)?$'
        match = re.match(pattern, message_body, re.IGNORECASE)
        
        if not match:
            return "Format pesan salah. Contoh: *hapus [aktivitas] tanggal [DD] [Bulan]*"
        
        activity = match.group(1).strip()
        date = match.group(2).strip() if match.group(2) else None 
        month = match.group(3).strip() if match.group(3) else None

        try:
            success = self.manager.remove_activity(activity=activity, date=date, month=month)
            if success:
                return f"Aktivitas '{activity}' berhasil dihapus."
            else:
                return f"Aktivitas '{activity}' tidak ditemukan."

        except pg8000.IntegrityError as e:
            return f"DB constraint error: {e}"
        except ValueError as e:
            return f"Validation error: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"

    # Schedule checking functions
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

# Global bot instance
bot_instance = None
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN not set!")
bot_instance = TelegramBot(BOT_TOKEN)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            data = json.loads(post_data.decode('utf-8'))
            
            bot = TelegramBot()
            
            if 'message' in data and 'text' in data['message']:
                message_text = data['message']['text']
                response = bot.handle_message(message_text)
                
                if response:
                    bot.send_message(response)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
            
        except Exception as e:
            logger.error(f"Error in webhook handler: {str(e)}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_GET(self):
        # Health check endpoint
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "Bot is running"}).encode())