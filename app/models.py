"""
SQLAlchemy ORM models for AquaSentry.

Two tables:
- Device   : one row per physical robot/probe unit
- Reading  : one row per water sample / arsenic measurement event
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=True)
    location_label = Column(String(128), nullable=True)  # e.g. "Powai Lake North"
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)

    readings = relationship(
        "Reading", back_populates="device", cascade="all, delete-orphan"
    )


class Reading(Base):
    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)

    # --- core measurement ---
    arsenic_ppb = Column(Float, nullable=False)          # micrograms per litre (µg/L)
    classification = Column(String(32), nullable=False)  # Safe / Caution / Unsafe / Hazardous
    confidence = Column(Float, nullable=True)             # 0-1, model/sensor confidence if available

    # --- supporting water-quality context (improves classification & trust) ---
    ph = Column(Float, nullable=True)
    temperature_c = Column(Float, nullable=True)
    conductivity_us_cm = Column(Float, nullable=True)
    turbidity_ntu = Column(Float, nullable=True)
    dissolved_oxygen_mg_l = Column(Float, nullable=True)

    # --- geo / trace ---
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # --- optional dashboard metadata ---
    battery_pct = Column(Float, nullable=True)
    source_label = Column(String(64), nullable=True)

    # --- bookkeeping ---
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)  # when the sample was taken
    received_at = Column(DateTime, default=datetime.utcnow)              # when the server got it
    raw_payload = Column(Text, nullable=True)  # original string/JSON from Arduino, for debugging

    device = relationship("Device", back_populates="readings")
