import enum
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, Enum, ForeignKey, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class AmbulanceStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    EN_ROUTE = "EN_ROUTE"
    AT_SCENE = "AT_SCENE"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"

class RequestStatus(str, enum.Enum):
    SEARCHING = "SEARCHING"
    ASSIGNED = "ASSIGNED"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED = "ARRIVED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_AMBULANCE_AVAILABLE = "NO_AMBULANCE_AVAILABLE"

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(32), unique=True)

class Hospital(Base):
    __tablename__ = "hospitals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    address: Mapped[str] = mapped_column(Text, default="")

class Ambulance(Base):
    __tablename__ = "ambulances"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    registration_number: Mapped[str] = mapped_column(String(32), unique=True)
    status: Mapped[AmbulanceStatus] = mapped_column(
        Enum(AmbulanceStatus), default=AmbulanceStatus.AVAILABLE, index=True
    )
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    hospital_id: Mapped[str | None] = mapped_column(ForeignKey("hospitals.id"), nullable=True)

class EmergencyRequest(Base):
    __tablename__ = "emergency_requests"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    emergency_type: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus), index=True)
    ambulance_id: Mapped[str | None] = mapped_column(ForeignKey("ambulances.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

Index("ix_ambulance_status_location", Ambulance.status, Ambulance.latitude, Ambulance.longitude)
