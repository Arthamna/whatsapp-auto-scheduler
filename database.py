import pg8000
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Tuple, Optional, Dict, Any

class ScheduleManager:
    
    def __init__(self):
        self._init_db()

        self._month_names = {
            1: 'januari',
            2: 'februari',
            3: 'maret',
            4: 'april',
            5: 'mei',
            6: 'juni',
            7: 'juli',
            8: 'agustus',
            9: 'september',
            10: 'oktober',
            11: 'november',
            12: 'desember'
        }
        self._month_indices = {v: k for k, v in self._month_names.items()}

    
    def _init_db(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedules (
                id SERIAL PRIMARY KEY,
                time TEXT NOT NULL,
                date TEXT NOT NULL,
                month TEXT NOT NULL,
                activity TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _get_connection(self) -> pg8000.Connection:
        load_dotenv()
        conn = pg8000.connect(
            user     = os.getenv("DB_USER"),
            password  = os.getenv("DB_PASS"),
            host  = os.getenv("DB_HOST"),
            port  = os.getenv("DB_PORT"),
            database  = os.getenv("DB_NAME"),
        )
        return conn
    
    def _validate_time_format(self, time_str: str) -> bool:
        try:
            datetime.strptime(time_str, "%H:%M")
            return True
        except ValueError:
            raise ValueError("Time must be in HH:MM format (e.g., 09:30)")
    
    def _validate_date(self, date: str) -> None:
        date = int(date)
        if not (1 <= date <= 31):
            raise ValueError("Date must be an integer between 1 and 31")
        
    def _validate_month(self, month: str) -> None:
        if month not in self._month_indices:
            raise ValueError(f"Use month names e.g Januari")
        
    
    def _find_schedule_by_activity(self, activity: str, date : str, month) -> Dict[str, Any]:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, date, time, activity, month FROM schedules WHERE activity = %s AND date = %s AND month = %s", (activity, date, month))
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            raise ValueError(f"No schedule found with activity: {activity}")
        
        return {
        "id":     row[0],       
        "date":     row[1],   
        "time":     row[2],   
        "activity": row[3],   
        "month":    row[4],   
    }
    
    def add_schedule(self, time: str, date: Optional[str], month: Optional[str], activity: str) -> str:
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.now(ZoneInfo("Asia/Jakarta"))
        if month is None :
            month = self._month_names[now.month]
        if date is None :
            date = now.day
                
        self._validate_time_format(time)
        self._validate_date(date)
        self._validate_month(month)
        cursor.execute("SELECT COUNT(*) FROM schedules WHERE date = %s AND activity = %s AND time = %s ", (date, activity, time))
        if cursor.fetchone()[0] > 0:
            conn.close()
            raise ValueError(f"An activity with the name '{activity}' already exists")
        
        cursor.execute(
            "INSERT INTO schedules (time, date, month, activity) VALUES (%s, %s, %s, %s)",
            (time, date, month, activity)
        )
                
        # new_id = cursor.lastrowid
        conn.commit()
        conn.close()
                
        return f"Jadwal '{activity}' berhasil ditambahkan pada {date} {month}, pukul {time}" 
    

    def get_today_schedules(self) -> Tuple[str, List[Tuple[str, str]]]:

        today = datetime.now(ZoneInfo("Asia/Jakarta"))
        current_date = today.day
        month_name = self._month_names[today.month]
            
        conn = self._get_connection()
        cursor = conn.cursor()
            
        cursor.execute(
            "SELECT time, activity FROM schedules WHERE date = %s AND month = %s ORDER BY time",
            (current_date, month_name)
        )
        schedules = cursor.fetchall()
            
        conn.close()
            
        day_info = f"{current_date} {month_name}"
        return day_info, schedules

    def get_weekly_schedules(self) -> List[Tuple[str, str, str, str]]:

        today = datetime.now(ZoneInfo("Asia/Jakarta"))
        start_of_week = today - timedelta(days=today.weekday())
        
        week_dates = []
        for i in range(7):  # 7 hari dalam seminggu
            day = start_of_week + timedelta(days=i)
            week_dates.append((day.day, self._month_names[day.month]))
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        all_schedules = []
        
        for date, month in week_dates:
            cursor.execute(""" SELECT time, activity, date, month FROM schedules WHERE date = %s AND month = %s ORDER BY time """, (date, month))
            
            day_schedules = cursor.fetchall()
            all_schedules.extend(day_schedules)
        
        conn.close()
        
        all_schedules.sort(key=lambda x: (self._month_indices[x[3]], x[2], x[0]))
        
        return all_schedules
    
    # check every 30 min
    def check_schedules(self) -> Dict[str, List[Dict[str, str]]]:

        now = datetime.now(ZoneInfo("Asia/Jakarta"))
        current_day = now.day
        current_month = now.month
        current_time = now.strftime("%H:%M")

        #range notification
        future_time_dt = now + timedelta(minutes=35)
        future_time = future_time_dt.strftime("%H:%M")

        conn = self._get_connection()
        cursor = conn.cursor()

        self.clean_outdated_activities()

        cursor.execute(
            """
            SELECT activity, time FROM schedules WHERE date = %s AND month = %s AND time::time > %s::time AND time::time <= %s::time
            """,
            (str(current_day), self._month_names[current_month], current_time, future_time)
        )
        upcoming = [
            {"activity": act, "time": t}
            for act, t in cursor.fetchall()
        ]

        conn.close()
        return {
            "upcoming": upcoming
        }
    
    def update_activity_name(self, activity: str, date: Optional[str], month : Optional[str] ,new_activity: str) -> bool: 

        if month is None :
            now = datetime.now(ZoneInfo("Asia/Jakarta"))

            month = self._month_names[now.month]
        if date is None :
            date = now.day

        self._validate_date(date)
        self._validate_month(month)

        try:
            schedule = self._find_schedule_by_activity(activity, date, month)
        except ValueError:
            return False

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE schedules SET activity = %s WHERE id = %s",
            (new_activity, schedule["id"])
        )

        success = (cursor.rowcount == 1)
        conn.commit()
        conn.close()

        return success
    
    def update_schedule_time(self, activity: str, date : str, new_date: str, month: Optional[str]) -> bool:
        self._validate_date(date)
        self._validate_date(new_date)

        if month is None:
            now = datetime.now(ZoneInfo("Asia/Jakarta"))

            month = self._month_names[now.month]  
        
        try:
            schedule = self._find_schedule_by_activity(activity, date, month)
        except ValueError:
            return False
    
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE schedules SET date = %s WHERE id = %s", (new_date, schedule["id"]))
        
        success = (cursor.rowcount == 1)
        conn.commit()
        conn.close()
        
        return success
        
    def remove_activity(self, activity: str,  date : Optional[str] , month: Optional[str] ) -> bool:

        if month is None:
            now = datetime.now(ZoneInfo("Asia/Jakarta"))

            month = self._month_names[now.month] 
        if date is None :
            date = now.day

        self._validate_date(date)
        self._validate_month(month)

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            schedule = self._find_schedule_by_activity(activity, date, month)
        except ValueError:
            return False
        
        cursor.execute("DELETE FROM schedules WHERE activity = %s AND id = %s", (activity, schedule["id"]))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def clean_outdated_activities(self):
        now = datetime.now(ZoneInfo("Asia/Jakarta"))
        current_year = now.year

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, date, month, time FROM schedules")
        rows = cursor.fetchall()
        for _id, date_str, month_str, time_str in rows: #check based on dateformat
            try:
                day = int(date_str)
                month = self._month_indices.get(month_str.lower())
                sched_dt = datetime.strptime(
                    f"{current_year}-{month:02d}-{day:02d} {time_str}",  
                    "%Y-%m-%d %H:%M")
            except Exception:
                continue

            if sched_dt.replace(tzinfo=ZoneInfo("Asia/Jakarta")) < now:
                cursor.execute("DELETE FROM schedules WHERE id = %s", (_id,))

        conn.commit()
        conn.close()
        return 
    