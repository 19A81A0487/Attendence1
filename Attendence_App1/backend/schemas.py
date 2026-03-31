from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class AttendanceBase(BaseModel):
    employee_id: str
    name: str
    email: str

class AttendanceCreate(AttendanceBase):
    pass

class BreakLog(BaseModel):
    id: int
    attendance_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    alert_sent_30m: Optional[datetime] = None
    alert_sent_1h: Optional[datetime] = None

    class Config:
        from_attributes = True

class Attendance(AttendanceBase):
    id: int
    date: str
    status: str
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    total_break_seconds: float
    effective_hours: float
    breaks: List[BreakLog] = []

    class Config:
        from_attributes = True
