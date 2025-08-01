import os
import re
import logging
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
import pg8000
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from dotenv import load_dotenv

# Import your existing modules
from database import ScheduleManager
import schedule
import time
import threading

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramScheduleBot:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.manager = ScheduleManager()
        self.application = Application.builder().token(token).build()
        self._setup_handlers()
        
    def _setup_handlers(self):
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            self.handle_message
        ))

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_text = update.message.text.strip()
        
        try:
            if message_text.lower().startswith('tambah'):
                response = self.process_add_command(message_text)
            elif message_text.lower() in ('jadwal hari ini', 'hari ini') :
                response = self.today()
            elif message_text.lower() in ('jadwal minggu ini', 'minggu ini') :
                response = self.week()
            elif message_text.lower().startswith(('ganti nama', 'update nama')):
                response = self.update_name(message_text)
            elif message_text.lower().startswith(('ganti tanggal', 'update tanggal')):
                response = self.update_date(message_text)
            elif message_text.lower().startswith('hapus'):
                response = self.delete_activity(message_text)
            else:
                return
            
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            await update.message.reply_text("Terjadi kesalahan saat memproses perintah.")

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

    # Schedule checking and notification functions
    async def async_checking(self):
        """Check schedules and send notifications"""
        try:
            current_time = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"{current_time} : Running schedule check")
            
            schedule_data = self.manager.check_schedules()
            await self.process_schedule_data(schedule_data)
            
        except Exception as e:
            logger.error(f"Error in async_checking: {str(e)}")

    async def process_schedule_data(self, schedule_data):
        """Process schedule data and send notifications"""
        upcoming_schedules = schedule_data.get("upcoming", [])
        if not upcoming_schedules:
            logger.info("No schedules found, skipping notification")
            return
        
        logger.info(f"Found schedules - Upcoming: {len(upcoming_schedules)}")
        try:
            current_message = self.format_schedule_message(upcoming_schedules)
            logger.info(f"Sending notification for current schedules: {upcoming_schedules}")
            await self.send_schedule_notification(current_message)
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

    async def send_schedule_notification(self, message):
        """Send notification to Telegram chat"""
        try:
            await self.application.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info("Notification sent successfully")
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")

    def start_scheduler(self):
        """Start the scheduler in a separate thread"""
        def run_scheduler():
            # Schedule the check to run every 30 minutes
            schedule.every(30).minutes.do(self.schedule_check_wrapper)
            
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        logger.info("Scheduler started successfully")

    def schedule_check_wrapper(self):
        """Wrapper to run async checking in sync context"""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.async_checking())
            loop.close()
        except Exception as e:
            logger.error(f"Error in schedule check wrapper: {str(e)}")

    def run(self):
        """Start the bot"""
        logger.info("Starting Telegram Schedule Bot...")
        
        # Start the scheduler
        self.start_scheduler()
        
        # Start the bot
        self.application.run_polling(drop_pending_updates=True)

def main():
    load_dotenv()
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    BOT_USERNAME = os.getenv("BOT_USERNAME")    

    # Create and run bot
    bot = TelegramScheduleBot(BOT_TOKEN, BOT_USERNAME)
    bot.run()

if __name__ == "__main__":
    main()