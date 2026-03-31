from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./attendance_app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, index=True)
    name = Column(String)
    email = Column(String)
    date = Column(String) # YYYY-MM-DD
    check_in = Column(DateTime, nullable=True)
    check_out = Column(DateTime, nullable=True)
    break_start = Column(DateTime, nullable=True)
    break_end = Column(DateTime, nullable=True)
    total_break_seconds = Column(Float, default=0.0)
    effective_hours = Column(Float, default=0.0)
    status = Column(String, default="checked_out") # checked_in, on_break, checked_out

    # Relationship for multiple breaks
    breaks = relationship("BreakLog", back_populates="attendance", cascade="all, delete-orphan")

class BreakLog(Base):
    __tablename__ = "break_logs"

    id = Column(Integer, primary_key=True, index=True)
    attendance_id = Column(Integer, ForeignKey("attendance.id"))
    start_time = Column(DateTime)
    end_time = Column(DateTime, nullable=True)
    alert_sent_30m = Column(DateTime, nullable=True)
    alert_sent_1h = Column(DateTime, nullable=True)

    attendance = relationship("Attendance", back_populates="breaks")

Base.metadata.create_all(bind=engine)
