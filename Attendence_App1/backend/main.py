from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from dotenv import load_dotenv
load_dotenv()

from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, relationship, joinedload
import datetime
import pytz

import smtplib
from email.mime.text import MIMEText
try:
    import database
    import schemas
except ImportError:
    from . import database
    from . import schemas

from typing import List

# --- TIMEZONE CONFIGURATION ---
IST = pytz.timezone('Asia/Kolkata')

def get_now_ist():
    return datetime.datetime.now(IST).replace(tzinfo=None)

def get_today_ist():
    return datetime.datetime.now(IST).date()


# --- EMAIL CONFIGURATION ---
SENDER_EMAIL = "madasuvenky263@gmail.com"

import os
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
print(f"DEBUG: EMAIL_PASSWORD loaded: {'Yes (Ends with ' + EMAIL_PASSWORD[-4:] + ')' if EMAIL_PASSWORD else 'No (None)'}")


from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os

load_dotenv()

app = FastAPI()

# Mount frontend static files relative to backend
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
print(f"DEBUG: BASE_DIR: {BASE_DIR}")
print(f"DEBUG: FRONTEND_DIR: {FRONTEND_DIR}")
print(f"DEBUG: FRONTEND_DIR exists: {os.path.exists(FRONTEND_DIR)}")

app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")



# Redirect root to frontend index
@app.get("/", include_in_schema=False)
def read_root():
    print("DEBUG: Root endpoint hit! Redirecting to /frontend/index.html")
    return RedirectResponse(url="/frontend/index.html")

@app.get("/health")
def health_check():
    return {"status": "ok", "frontend_exists": os.path.exists(FRONTEND_DIR)}


# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def send_email(to_email: str, subject: str, body: str):
    if EMAIL_PASSWORD == "YOUR_APP_PASSWORD_HERE" or not EMAIL_PASSWORD:
        print(f"SKIPPING REAL EMAIL (No Password): {subject}")
        return

    try:
        import traceback
        import socket
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email

        print(f"\n--- SMTP DEBUG START ---")
        print(f"Target: {to_email}")
        print(f"Server: smtp.gmail.com:465")
        
        # Using SMTP_SSL with a timeout to catch hanging connections
        with smtplib.SMTP_SSL("smtp.gmail.com", 587, timeout=10) as server:
            server.set_debuglevel(2) # Even more verbose
            print("Action: Logging in...")
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            print("Action: Sending message...")
            server.send_message(msg)
        
        print(f"--- SMTP DEBUG END: SUCCESS ✅ ---")
        print(f"✅ REAL EMAIL SENT successfully to {to_email}")
    except socket.timeout:
        print(f"--- SMTP DEBUG END: FAILED ❌ ---")
        print(f"❌ ERROR: Connection timed out. Your network or firewall might be blocking port 465.")
    except smtplib.SMTPAuthenticationError:
        print(f"--- SMTP DEBUG END: FAILED ❌ ---")
        print(f"❌ ERROR: Authentication failed. Please double-check your App Password in main.py at line 14.")
    except Exception as e:
        print(f"--- SMTP DEBUG END: FAILED ❌ ---")
        print(f"❌ SMTP ERROR: {e}")
        traceback.print_exc()

@app.get("/test-email")
def test_email(email: str = SENDER_EMAIL):
    send_email(
        email, 
        "Test Email from Attendance App", 
        f"If you see this, your email configuration is working! Sent to: {email}"
    )
    return {"message": f"Test email triggered to {email}. Check your terminal logs for results."}

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/check-in")
def check_in(employee_id: str, db: Session = Depends(get_db)):
    date_str = get_today_ist().isoformat()
    record = db.query(database.Attendance).options(joinedload(database.Attendance.breaks)).filter(
        database.Attendance.employee_id == employee_id,
        database.Attendance.date == date_str
    ).first()

    if record and record.status != "checked_out":
        raise HTTPException(status_code=400, detail="Already checked in for today")

    if not record:
        record = database.Attendance(
            employee_id=employee_id,
            name="Venkanna Madasu",
            email="madasuvenky263@gmail.com",
            date=date_str,
            status="checked_in",
            check_in=get_now_ist()
        )
        db.add(record)
    else:
        record.status = "checked_in"
        record.check_in = get_now_ist()
        record.check_out = None
        record.total_break_seconds = 0.0
        record.effective_hours = 0.0
        # Clear old breaks for a fresh day if record existed
        for b in record.breaks:
            db.delete(b)
    
    db.commit()
    db.refresh(record)
    return record

@app.post("/break-start")
def break_start(employee_id: str, db: Session = Depends(get_db)):
    date_str = get_today_ist().isoformat()
    record = db.query(database.Attendance).options(joinedload(database.Attendance.breaks)).filter(
        database.Attendance.employee_id == employee_id,
        database.Attendance.date == date_str
    ).first()

    if not record or record.status != "checked_in":
        raise HTTPException(status_code=400, detail="Must be checked in to start break")

    record.status = "on_break"
    record.break_start = get_now_ist() 
    
    # Create new break log entry
    new_break = database.BreakLog(
        attendance_id=record.id,
        start_time=record.break_start
    )
    db.add(new_break)
    
    db.commit()
    db.refresh(record)
    return record

@app.post("/break-end")
def break_end(employee_id: str, db: Session = Depends(get_db)):
    date_str = get_today_ist().isoformat()
    record = db.query(database.Attendance).options(joinedload(database.Attendance.breaks)).filter(
        database.Attendance.employee_id == employee_id,
        database.Attendance.date == date_str
    ).first()

    if not record or record.status != "on_break":
        raise HTTPException(status_code=400, detail="Must be on break to end it")

    # Find the latest open break log
    open_break = db.query(database.BreakLog).filter(
        database.BreakLog.attendance_id == record.id,
        database.BreakLog.end_time == None
    ).order_by(database.BreakLog.id.desc()).first()
    
    if open_break:
        open_break.end_time = get_now_ist()
        break_duration = (open_break.end_time - open_break.start_time).total_seconds()
        record.total_break_seconds += break_duration
    
    record.status = "checked_in"
    record.break_end = get_now_ist()
    db.commit()
    db.refresh(record)
    return record

@app.post("/check-out")
def check_out(employee_id: str, db: Session = Depends(get_db)):
    date_str = get_today_ist().isoformat()
    record = db.query(database.Attendance).options(joinedload(database.Attendance.breaks)).filter(
        database.Attendance.employee_id == employee_id,
        database.Attendance.date == date_str
    ).first()

    if not record or record.status == "checked_out":
        raise HTTPException(status_code=400, detail="Must be checked in or on break to check out")

    if record.status == "on_break":
        # Automatically end break
        end_time = get_now_ist()
        
        # Also close the BreakLog entry
        open_break = db.query(database.BreakLog).filter(
            database.BreakLog.attendance_id == record.id,
            database.BreakLog.end_time == None
        ).order_by(database.BreakLog.id.desc()).first()
        if open_break:
            open_break.end_time = end_time
            break_duration = (open_break.end_time - open_break.start_time).total_seconds()
            record.total_break_seconds += break_duration

    record.check_out = get_now_ist()
    record.status = "checked_out"
    
    # Calculate effective hours (Total Duration + Total Break Seconds as requested)
    total_duration = (record.check_out - record.check_in).total_seconds()
    effective_seconds = total_duration + record.total_break_seconds
    record.effective_hours = effective_seconds / 3600.0
    
    db.commit()
    db.refresh(record)
    return record

@app.post("/reset")
def reset_status(employee_id: str, db: Session = Depends(get_db)):
    today = get_today_ist()
    record = db.query(database.Attendance).filter(
        database.Attendance.employee_id == employee_id,
        database.Attendance.date == today.isoformat()
    ).first()
    if record:
        db.delete(record)
        db.commit()
    return {"message": "Reset successful"}

@app.get("/status/{employee_id}")
def get_status(employee_id: str, db: Session = Depends(get_db)):
    date_str = get_today_ist().isoformat()
    record = db.query(database.Attendance).options(joinedload(database.Attendance.breaks)).filter(
        database.Attendance.employee_id == employee_id,
        database.Attendance.date == date_str
    ).first()
    
    if not record:
        return {"status": "checked_out", "effective_hours": 0.0}
    
    # Check for break alerts if currently on break
    if record.status == "on_break":
        # Find the open break log
        open_break = db.query(database.BreakLog).filter(
            database.BreakLog.attendance_id == record.id,
            database.BreakLog.end_time == None
        ).order_by(database.BreakLog.id.desc()).first()
        
        if open_break:
            duration_sec = (get_now_ist() - open_break.start_time).total_seconds()
            print(f"DEBUG: Break duration for {record.name}: {duration_sec}s (Target: 60s)")
            
            # 1 minute alert (60 sec) for testing (originally 30 mins)
            if duration_sec > 60 and not open_break.alert_sent_30m:
                print(f"DEBUG: Triggering 1-minute alert for {record.name}")
                open_break.alert_sent_30m = get_now_ist()
                send_email(
                    record.email, 
                    "Break Reminder", 
                    f"Hi {record.name},\n\nThis is a reminder that you have exceeded 1 minute of break time. Please resume your work."
                )
                db.commit()
            
            # 1 hour alert (3600 sec)
            if duration_sec > 3600 and not open_break.alert_sent_1h:
                open_break.alert_sent_1h = get_now_ist()
                send_email(
                    record.email, 
                    "URGENT: Break Warning (1 Hour)", 
                    f"Hi {record.name},\n\nYou have exceeded 1 hour of break time. This is a formal warning."
                )
                db.commit()
    
    return record

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)
