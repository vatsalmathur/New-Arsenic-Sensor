"""
AquaSentry backend API.

Run locally with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Then open http://localhost:8000/docs for interactive API docs (Swagger UI).

Flow:
    Arduino (sensor + HC-05 Bluetooth) --serial--> Bridge script (laptop/RPi)
        --HTTP POST--> /api/readings  --> classified & stored in DB
    Website dashboard --HTTP GET--> /api/readings, /api/stats, etc.
"""

from datetime import datetime, timedelta
import os
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, schemas
from .database import engine, get_db, Base, ensure_sqlite_columns
from .classification import classify_arsenic

# Create tables on startup if they don't exist yet.
Base.metadata.create_all(bind=engine)
ensure_sqlite_columns()

app = FastAPI(
    title="AquaSentry API",
    description="Backend for the AI-assisted arsenic-detection water robot.",
    version="1.0.0",
)

# Allow the local dashboard and simple static deployments to call the API.
# Set AQUASENTRY_ALLOWED_ORIGINS to a comma-separated list in production.
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "AQUASENTRY_ALLOWED_ORIGINS",
        "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8001,http://127.0.0.1:8001",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["Meta"])
def health_check():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


# ---------------------------------------------------------------------------
# Device helpers
# ---------------------------------------------------------------------------

def _get_or_create_device(db: Session, device_code: str) -> models.Device:
    device = db.query(models.Device).filter_by(device_code=device_code).first()
    now = datetime.utcnow()
    if device is None:
        device = models.Device(device_code=device_code, first_seen=now, last_seen=now)
        db.add(device)
        db.commit()
        db.refresh(device)
    else:
        device.last_seen = now
        db.commit()
    return device


# ---------------------------------------------------------------------------
# Readings: ingest (called by the bridge/Arduino side)
# ---------------------------------------------------------------------------

@app.post("/api/readings", response_model=schemas.ReadingResponse, tags=["Readings"])
def create_reading(payload: schemas.ReadingCreate, db: Session = Depends(get_db)):
    """
    Ingest a new arsenic reading from the robot.
    Classifies the arsenic level and stores everything in the database.
    """
    try:
        result = classify_arsenic(payload.arsenic_ppb)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    device = _get_or_create_device(db, payload.device_code)

    reading = models.Reading(
        device_id=device.id,
        arsenic_ppb=payload.arsenic_ppb,
        classification=result.label,
        ph=payload.ph,
        temperature_c=payload.temperature_c,
        conductivity_us_cm=payload.conductivity_us_cm,
        turbidity_ntu=payload.turbidity_ntu,
        dissolved_oxygen_mg_l=payload.dissolved_oxygen_mg_l,
        latitude=payload.latitude,
        longitude=payload.longitude,
        confidence=payload.confidence,
        battery_pct=payload.battery_pct,
        source_label=payload.source_label,
        recorded_at=payload.recorded_at or datetime.utcnow(),
        received_at=datetime.utcnow(),
        raw_payload=payload.raw_payload,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)

    return schemas.ReadingResponse(
        reading=schemas.ReadingOut.model_validate(reading),
        label=result.label,
        severity=result.severity,
        message=result.message,
        action=result.action,
    )


# ---------------------------------------------------------------------------
# Readings: query (called by the website dashboard)
# ---------------------------------------------------------------------------

@app.get("/api/readings", response_model=List[schemas.ReadingOut], tags=["Readings"])
def list_readings(
    device_code: Optional[str] = Query(None, description="Filter by device code"),
    classification: Optional[str] = Query(
        None, description="Filter by Safe / Caution / Unsafe / Hazardous"
    ),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(models.Reading)
    if device_code:
        q = q.join(models.Device).filter(models.Device.device_code == device_code)
    if classification:
        q = q.filter(models.Reading.classification == classification)
    q = q.order_by(models.Reading.recorded_at.desc()).offset(offset).limit(limit)
    return q.all()


@app.get("/api/readings/latest", response_model=schemas.ReadingOut, tags=["Readings"])
def latest_reading(
    device_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(models.Reading)
    if device_code:
        q = q.join(models.Device).filter(models.Device.device_code == device_code)
    reading = q.order_by(models.Reading.recorded_at.desc()).first()
    if reading is None:
        raise HTTPException(status_code=404, detail="No readings found yet.")
    return reading


@app.get("/api/readings/{reading_id}", response_model=schemas.ReadingOut, tags=["Readings"])
def get_reading(reading_id: int, db: Session = Depends(get_db)):
    reading = db.query(models.Reading).filter_by(id=reading_id).first()
    if reading is None:
        raise HTTPException(status_code=404, detail="Reading not found.")
    return reading


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

@app.get("/api/devices", response_model=List[schemas.DeviceOut], tags=["Devices"])
def list_devices(db: Session = Depends(get_db)):
    return db.query(models.Device).order_by(models.Device.last_seen.desc()).all()


# ---------------------------------------------------------------------------
# Stats (for dashboard summary cards / charts)
# ---------------------------------------------------------------------------

@app.get("/api/stats", response_model=schemas.StatsOut, tags=["Meta"])
def get_stats(device_code: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(models.Reading)
    if device_code:
        q = q.join(models.Device).filter(models.Device.device_code == device_code)

    total = q.count()
    latest = q.order_by(models.Reading.recorded_at.desc()).first()
    avg = db.query(func.avg(models.Reading.arsenic_ppb))
    if device_code:
        avg = avg.join(models.Device).filter(models.Device.device_code == device_code)
    avg_value = avg.scalar()

    breakdown = {"Safe": 0, "Caution": 0, "Unsafe": 0, "Hazardous": 0}
    rows = q.with_entities(
        models.Reading.classification, func.count(models.Reading.id)
    ).group_by(models.Reading.classification).all()
    for label, count in rows:
        breakdown[label] = count

    devices_count = db.query(models.Device).count()
    if device_code:
        devices_count = db.query(models.Device).filter(
            models.Device.device_code == device_code
        ).count()

    return schemas.StatsOut(
        total_readings=total,
        devices_count=devices_count,
        latest_reading=latest,
        breakdown=breakdown,
        average_arsenic_ppb=round(avg_value, 3) if avg_value is not None else None,
    )


# ---------------------------------------------------------------------------
# Dashboard projection
# ---------------------------------------------------------------------------

SAFE_LIMIT_MG_L = 0.010


@app.get("/api/dashboard/latest", response_model=schemas.DashboardReading, tags=["Dashboard"])
def dashboard_latest(device_code: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(models.Reading)
    if device_code:
        q = q.join(models.Device).filter(models.Device.device_code == device_code)
    reading = q.order_by(models.Reading.recorded_at.desc()).first()
    if reading is None:
        raise HTTPException(status_code=404, detail="No readings found yet.")

    confirmed_count = 0
    if reading.classification in ("Unsafe", "Hazardous"):
        cutoff = datetime.utcnow() - timedelta(hours=24)
        confirmed_count = (
            db.query(models.Reading.device_id)
            .filter(
                models.Reading.classification.in_(["Unsafe", "Hazardous"]),
                models.Reading.recorded_at >= cutoff,
                models.Reading.device_id != reading.device_id,
            )
            .distinct()
            .count()
        )

    patrol_minutes = max(
        0,
        round((datetime.utcnow() - reading.recorded_at).total_seconds() / 60, 1),
    )
    return schemas.DashboardReading(
        contaminant="Arsenic (As)",
        value=round(reading.arsenic_ppb / 1000, 4),
        unit="mg/L",
        safeLimit=SAFE_LIMIT_MG_L,
        confidencePct=round(reading.confidence * 100, 1) if reading.confidence is not None else None,
        confirmedByHomes=confirmed_count,
        source=reading.source_label or "Groundwater",
        detectedAt=reading.recorded_at.strftime("%H:%M"),
        batteryPct=reading.battery_pct,
        lastPatrolMin=patrol_minutes,
        nextPatrolMin=None,
        classification=reading.classification,
    )


# ---------------------------------------------------------------------------
# AI Chatbot Integration
# ---------------------------------------------------------------------------
from pydantic import BaseModel
from google import genai
from google.genai import types

try:
    client = genai.Client()
except Exception as e:
    print(f"Warning: Failed to initialize Gemini client. Error: {e}")
    client = None

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

SYSTEM_PROMPT = """You are the official AquaSentry AI Assistant. Use the following project summary to answer user questions accurately. If asked about something outside this scope, politely decline. Here is the project knowledge:

AquaSentry: Solar-assisted water robot for arsenic screening | Project summary

What it is:
A small catamaran-style surface robot, roughly 1 m long and 8 to 20 kg, that drives itself across a lake, creek or reservoir. At each waypoint it stops, pulls water into a sealed internal chamber, screens it for arsenic, and tags the reading with GPS. A solar panel on the deck stretches the mission; the battery handles motor loads and cloudy stretches.

The important design choice is that the sensor never touches open water. Raw seawater fouls electrodes and throws off electrochemical readings because of chloride, sulfate and suspended solids. Instead the robot brings a filtered, temperature-controlled sample to the sensor. Same cell geometry every time, so results are repeatable.

Scope, stated honestly. This is a screening tool, not a certified lab instrument. It tells you which samples are worth sending to a lab. It does not replace one.

How it helps:
Arsenic has no colour, smell or taste. The WHO provisional guideline is 10 µg/L. You cannot find it without an instrument, and the instruments that reach that limit cost orders of magnitude more than this robot and never leave the building.

So the gap is not sensitivity. It is mobility. Today, mapping a water body means a person collecting bottles by hand, carrying them to a lab, and waiting. That is slow, expensive, and produces a handful of points instead of a map.

AquaSentry closes that gap three ways:
1. Coverage. A grid survey produces a contamination contour, not a single reading. You can see where the problem is, not just that it exists.
2. Cost per sample. Once built, each additional reading costs reagents and time, not a lab fee and a courier.
3. Context. Every arsenic value is logged with its location and supporting water-quality measurements.

What it achieves:
Direct output: a geotagged arsenic contour map of a water body, with pH, conductivity, turbidity and temperature logged at every point, plus a confidence range on each reading rather than a bare number.

What that changes: you stop guessing which wells, ponds or stretches of creek to test, and start testing the ones the map says are worth testing. Lab capacity goes to the samples that matter."""

@app.post("/api/chat", response_model=ChatResponse, tags=["AI Chat"])
async def chat(request: ChatRequest):
    if not client:
        raise HTTPException(status_code=500, detail="Gemini client not initialized. Check API key.")
    
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=request.message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.3,
            )
        )
        return ChatResponse(reply=response.text)
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        raise HTTPException(status_code=500, detail=str(e))
