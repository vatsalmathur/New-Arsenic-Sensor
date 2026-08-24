"""
Pydantic schemas: define exactly what the API accepts and returns.
Keeping these separate from the SQLAlchemy models means the API's public
shape doesn't accidentally change just because the DB schema does.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ---------- Incoming: what the Arduino / bridge sends ----------

class ReadingCreate(BaseModel):
    device_code: str = Field(..., description="Unique ID of the robot, e.g. 'AQUA-001'")
    arsenic_ppb: float = Field(..., ge=0, description="Measured arsenic concentration in µg/L")

    ph: Optional[float] = Field(None, ge=0, le=14)
    temperature_c: Optional[float] = None
    conductivity_us_cm: Optional[float] = Field(None, ge=0)
    turbidity_ntu: Optional[float] = Field(None, ge=0)
    dissolved_oxygen_mg_l: Optional[float] = Field(None, ge=0)

    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

    confidence: Optional[float] = Field(None, ge=0, le=1)
    battery_pct: Optional[float] = Field(None, ge=0, le=100)
    source_label: Optional[str] = Field(None, max_length=64)

    recorded_at: Optional[datetime] = Field(
        None, description="Timestamp the sample was taken. Defaults to server time if omitted."
    )
    raw_payload: Optional[str] = Field(
        None, description="Original raw string/JSON received over Bluetooth, for debugging."
    )


# ---------- Outgoing: what the API returns ----------

class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    arsenic_ppb: float
    classification: str
    ph: Optional[float] = None
    temperature_c: Optional[float] = None
    conductivity_us_cm: Optional[float] = None
    turbidity_ntu: Optional[float] = None
    dissolved_oxygen_mg_l: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    confidence: Optional[float] = None
    battery_pct: Optional[float] = None
    source_label: Optional[str] = None
    recorded_at: datetime
    received_at: datetime


class DashboardReading(BaseModel):
    contaminant: str
    value: float
    unit: str
    safeLimit: float
    confidencePct: Optional[float] = None
    confirmedByHomes: int
    source: str
    detectedAt: str
    batteryPct: Optional[float] = None
    lastPatrolMin: Optional[float] = None
    nextPatrolMin: Optional[float] = None
    classification: str


class ReadingResponse(BaseModel):
    """What we send back right after ingesting a new reading."""
    reading: ReadingOut
    label: str
    severity: int
    message: str
    action: str


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_code: str
    name: Optional[str] = None
    location_label: Optional[str] = None
    first_seen: datetime
    last_seen: datetime


class StatsOut(BaseModel):
    total_readings: int
    devices_count: int
    latest_reading: Optional[ReadingOut] = None
    breakdown: dict  # {"Safe": 12, "Caution": 3, "Unsafe": 1, "Hazardous": 0}
    average_arsenic_ppb: Optional[float] = None
