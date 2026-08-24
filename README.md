# AquaSentry Backend

Backend + database for the AI-assisted arsenic-detection water robot.

## How data flows

```
Arduino (arsenic sensor + HC-05 Bluetooth)
        │  Bluetooth serial, CSV line
        ▼
Bridge script (bridge/serial_bridge.py) — runs on a laptop/Raspberry Pi
        │  HTTP POST /api/readings
        ▼
FastAPI backend (app/main.py) — classifies + stores in database
        │  HTTP GET /api/readings, /api/stats, ...
        ▼
Your website dashboard (fetch/AJAX)
```

Nothing here talks to Bluetooth directly except the bridge script — the
backend only ever speaks plain HTTP/JSON, so it doesn't care whether data
arrives from Bluetooth, WiFi, or a manual test with curl.

## 1. Install and run the backend

```bash
cd aquasentry-backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API root: `http://localhost:8000`
- Interactive docs (test endpoints in the browser): `http://localhost:8000/docs`
- A SQLite file `aquasentry.db` is created automatically on first run —
  no separate database install needed. To switch to PostgreSQL later,
  just set an environment variable, no code changes required:
  ```bash
  export DATABASE_URL="postgresql://user:password@localhost:5432/aquasentry"
  ```

## 2. Database schema

**`devices`** — one row per physical robot
| column | type | notes |
|---|---|---|
| id | int | primary key |
| device_code | string | unique, e.g. `AQUA-001` |
| name | string | optional friendly name |
| location_label | string | optional, e.g. "Powai Lake North" |
| first_seen / last_seen | datetime | auto-updated |

**`readings`** — one row per water sample
| column | type | notes |
|---|---|---|
| id | int | primary key |
| device_id | int | FK -> devices |
| arsenic_ppb | float | µg/L, the core measurement |
| classification | string | Safe / Caution / Unsafe / Hazardous |
| ph, temperature_c, conductivity_us_cm, turbidity_ntu, dissolved_oxygen_mg_l | float | optional context readings |
| latitude, longitude | float | optional GPS tag |
| recorded_at | datetime | when the sample was taken |
| received_at | datetime | when the server got it |
| raw_payload | text | original string from the Arduino, for debugging |

## 3. Classification logic (`app/classification.py`)

Based on WHO and Indian BIS 10500 reference points:

| Range (µg/L) | Label | Meaning |
|---|---|---|
| 0 – 10 | **Safe** | Within WHO provisional guideline |
| 10 – 50 | **Caution** | Above WHO, within India's permissible limit |
| 50 – 150 | **Unsafe** | Not safe untreated, needs lab confirmation |
| > 150 | **Hazardous** | Critical, do not use |

This is deliberately isolated in its own file/function so you can later
swap it for a trained ML model without touching the API or database —
just change what happens inside `classify_arsenic()`.

## 4. API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/readings` | Ingest a new reading (called by the bridge) |
| GET | `/api/readings` | List readings (filter by `device_code`, `classification`; paginate with `limit`/`offset`) |
| GET | `/api/readings/latest` | Most recent reading |
| GET | `/api/readings/{id}` | One specific reading |
| GET | `/api/devices` | List all known devices |
| GET | `/api/stats` | Totals, breakdown by classification, average arsenic level |
| GET | `/api/dashboard/latest` | Latest reading normalized for the frontend |

Example POST body:
```json
{
  "device_code": "AQUA-001",
  "arsenic_ppb": 6.2,
  "ph": 7.1,
  "temperature_c": 26.4,
  "conductivity_us_cm": 420,
  "turbidity_ntu": 3.1,
  "latitude": 19.0760,
  "longitude": 72.8777
}
```

Example response:
```json
{
  "reading": { "id": 1, "device_id": 1, "arsenic_ppb": 6.2, "classification": "Safe", "...": "..." },
  "label": "Safe",
  "severity": 0,
  "message": "Arsenic level is within the WHO provisional guideline (\u226410 \u00b5g/L).",
  "action": "No action needed. Continue routine monitoring."
}
```

## 5. Arduino + Bluetooth setup

`arduino/aquasentry_sensor/aquasentry_sensor.ino` reads sensor pins and
sends one CSV line every 10 seconds over an HC-05/HC-06 Bluetooth module:

```
AS:6.20,PH:7.10,T:26.40,EC:420.00,TURB:3.10
```

Wiring notes and pin assignments are commented at the top of the sketch.
**The arsenic reading function (`readArsenicPPB()`) is a placeholder** —
replace it with your real sensor/module's calibration curve once your
arsenic detection hardware (ASV or electrochemical module) is finalized.
Everything downstream (bridge, backend, classification, database,
dashboard) already works end-to-end with the placeholder, so you can
swap in real calibration later without changing anything else.

## 6. Bridge script setup

1. Pair the HC-05 with your laptop/Raspberry Pi over Bluetooth (default
   PIN is usually `1234` or `0000`).
2. Find the serial port it was assigned:
   - Windows: check Device Manager → Ports (COM&Ltx)
   - macOS: `ls /dev/tty.*`
   - Linux: `sudo rfcomm bind 0 <MAC_ADDRESS>` then use `/dev/rfcomm0`
3. Make sure the backend is running.
4. Run:
   ```bash
   pip install pyserial requests
   python bridge/serial_bridge.py --port COM5
   ```
   (swap `COM5` for your actual port)

The bridge prints every line it receives and the classification result
returned by the backend, so you can watch it work live.

## 7. Running the complete local system

Use the single PowerShell runner from the canonical project folder:

```powershell
cd "AquaSentry\aquasentry-backend\aquasentry-backend"
.\run-aquasentry.cmd
```

The runner starts both the backend and frontend, waits for the dashboard server,
and opens the dashboard automatically in your default browser. Press `Ctrl+C`
once to stop both servers.

The dashboard includes an `MAS-G1 device simulator` for testing. Choose `Safe`,
`Warning`, or `Spike`, then press `Run scan`. It updates the dashboard preview
without writing simulated data to the backend database.

If PowerShell blocks local scripts, run this once for the current user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Open `http://127.0.0.1:8001/index.html` in a browser. The dashboard requests
the latest `AQUA-001` reading from the backend. If no reading exists or the
backend is offline, it keeps the sample data and shows `DEMO DATA · API OFFLINE`.

## 8. Connecting your website dashboard

The dashboard in `frontend/` calls `/api/dashboard/latest`, which converts
the backend's arsenic `ppb` value to `mg/L` and includes the latest status,
source, battery, and patrol metadata. Local dashboard origins are enabled by
default. For deployment, set `AQUASENTRY_ALLOWED_ORIGINS` to a comma-separated
list of trusted website origins.

```javascript
// Dashboard-shaped latest reading
const res = await fetch("http://localhost:8000/api/dashboard/latest?device_code=AQUA-001");
const data = await res.json();

// Full history for a chart
const history = await fetch("http://localhost:8000/api/readings?limit=200")
  .then(r => r.json());

// Summary stats for dashboard cards
const stats = await fetch("http://localhost:8000/api/stats").then(r => r.json());
```

When you're ready to deploy for real (not just localhost), host this
FastAPI app somewhere reachable (Render, Railway, a VPS, etc.), tighten
`allow_origins` in `app/main.py` to your actual website domain instead of
`"*"`, and point your dashboard's fetch calls at that public URL instead
of `localhost:8000`.

## 9. Project structure

```
aquasentry-backend/
├── app/
│   ├── main.py            # FastAPI app, all endpoints
│   ├── models.py          # SQLAlchemy DB models (Device, Reading)
│   ├── schemas.py         # Pydantic request/response schemas
│   ├── classification.py  # Arsenic level -> Safe/Caution/Unsafe/Hazardous
│   └── database.py        # DB engine/session setup (SQLite by default)
├── bridge/
│   └── serial_bridge.py   # Reads Bluetooth serial, POSTs to backend
├── arduino/
│   └── aquasentry_sensor/
│       └── aquasentry_sensor.ino
├── frontend/
│   ├── index.html
│   ├── script.js
│   ├── style.css
│   └── AquaSentry-Explanation.md
├── run-aquasentry.cmd   # One-command Windows launcher
├── run-aquasentry.ps1   # Backend/frontend process runner
├── requirements.txt
└── README.md
```

All of this has been tested end-to-end (POST a reading → classified →
stored → fetched back correctly, plus invalid input correctly rejected
with HTTP 422) before packaging.
