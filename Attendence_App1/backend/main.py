from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, relationship, joinedload
import datetime
import smtplib
from email.mime.text import MIMEText
from backend import database
from backend import schemas
from typing import List

# --- EMAIL CONFIGURATION ---
SENDER_EMAIL = "madasuvenky263@gmail.com"

import os
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

# Mount frontend static files relative to backend
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.mount("/frontend", StaticFiles(directory=os.path.join(BASE_DIR, "frontend")), name="frontend")
app.mount("/assets", StaticFiles(directory=os.path.join(BASE_DIR, "assets")), name="assets")

# Redirect root to frontend index
from fastapi.responses import RedirectResponse
@app.get("/")
def read_root():
    return RedirectResponse(url="/frontend/index.html")

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
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
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
    date_str = datetime.date.today().isoformat()
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
            check_in=datetime.datetime.now()
        )
        db.add(record)
    else:
        record.status = "checked_in"
        record.check_in = datetime.datetime.now()
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
    date_str = datetime.date.today().isoformat()
    record = db.query(database.Attendance).options(joinedload(database.Attendance.breaks)).filter(
        database.Attendance.employee_id == employee_id,
        database.Attendance.date == date_str
    ).first()

    if not record or record.status != "checked_in":
        raise HTTPException(status_code=400, detail="Must be checked in to start break")

    record.status = "on_break"
    record.break_start = datetime.datetime.now() 
    
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
    date_str = datetime.date.today().isoformat()
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
        open_break.end_time = datetime.datetime.now()
        break_duration = (open_break.end_time - open_break.start_time).total_seconds()
        record.total_break_seconds += break_duration
    
    record.status = "checked_in"
    record.break_end = datetime.datetime.now()
    db.commit()
    db.refresh(record)
    return record

@app.post("/check-out")
def check_out(employee_id: str, db: Session = Depends(get_db)):
    date_str = datetime.date.today().isoformat()
    record = db.query(database.Attendance).options(joinedload(database.Attendance.breaks)).filter(
        database.Attendance.employee_id == employee_id,
        database.Attendance.date == date_str
    ).first()

    if not record or record.status == "checked_out":
        raise HTTPException(status_code=400, detail="Must be checked in or on break to check out")

    if record.status == "on_break":
        # Automatically end break
        end_time = datetime.datetime.now()
        
        # Also close the BreakLog entry
        open_break = db.query(database.BreakLog).filter(
            database.BreakLog.attendance_id == record.id,
            database.BreakLog.end_time == None
        ).order_by(database.BreakLog.id.desc()).first()
        if open_break:
            open_break.end_time = end_time
            break_duration = (open_break.end_time - open_break.start_time).total_seconds()
            record.total_break_seconds += break_duration

    record.check_out = datetime.datetime.now()
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
    today = datetime.date.today()
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
    date_str = datetime.date.today().isoformat()
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
            duration_sec = (datetime.datetime.now() - open_break.start_time).total_seconds()
            
            # 1 minute alert (60 sec) for testing (originally 30 mins)
            if duration_sec > 60 and not open_break.alert_sent_30m:
                open_break.alert_sent_30m = datetime.datetime.now()
                send_email(
                    record.email, 
                    "Break Reminder", 
                    f"Hi {record.name},\n\nThis is a reminder that you have exceeded 1 minute of break time. Please resume your work."
                )
                db.commit()
            
            # 1 hour alert (3600 sec)
            if duration_sec > 3600 and not open_break.alert_sent_1h:
                open_break.alert_sent_1h = datetime.datetime.now()
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
