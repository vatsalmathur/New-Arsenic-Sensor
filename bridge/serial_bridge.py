"""
AquaSentry Bluetooth-to-backend bridge.

Runs on a laptop / Raspberry Pi that is paired with the Arduino's HC-05/HC-06
Bluetooth module. The module shows up as a normal serial (COM) port once
paired, so this script just reads lines from that port and POSTs each one
to the backend API.

Expected line format from the Arduino (see arduino/aquasentry_sensor.ino):
    AS:6.20,PH:7.10,T:26.40,EC:420.00,TURB:3.10

SETUP
-----
1. Pair the HC-05 with your laptop/RPi via Bluetooth settings first
   (default pairing PIN is usually 1234 or 0000).
2. Find the serial port it was assigned:
     Windows : COM5, COM7, etc.  (check Device Manager -> Ports)
     macOS   : /dev/tty.HC-05-xxxx  (check `ls /dev/tty.*`)
     Linux   : /dev/rfcomm0  (may need: sudo rfcomm bind 0 <MAC_ADDRESS>)
3. Edit SERIAL_PORT below (or pass --port on the command line).
4. Make sure the backend is running (uvicorn app.main:app --reload).
5. Run: python bridge/serial_bridge.py --port COM5

Install deps: pip install pyserial requests
"""

import argparse
import sys
import time
from datetime import datetime

import requests
import serial

DEFAULT_BAUD_RATE = 9600
DEFAULT_BACKEND_URL = "http://localhost:8000/api/readings"
DEFAULT_DEVICE_CODE = "AQUA-001"


def parse_line(line: str) -> dict:
    """
    Parse a CSV line like:
        AS:6.20,PH:7.10,T:26.40,EC:420.00,TURB:3.10
    into a dict of floats keyed by field name.
    """
    fields = {}
    for part in line.strip().split(","):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        try:
            fields[key.strip().upper()] = float(value.strip())
        except ValueError:
            continue  # skip malformed field rather than crashing the bridge
    return fields


def build_payload(fields: dict, device_code: str, raw_line: str) -> dict:
    if "AS" not in fields:
        raise ValueError(f"No arsenic ('AS') value found in line: {raw_line!r}")

    payload = {
        "device_code": device_code,
        "arsenic_ppb": fields["AS"],
        "recorded_at": datetime.utcnow().isoformat(),
        "raw_payload": raw_line.strip(),
    }
    optional_map = {
        "PH": "ph",
        "T": "temperature_c",
        "EC": "conductivity_us_cm",
        "TURB": "turbidity_ntu",
        "DO": "dissolved_oxygen_mg_l",
    }
    for src_key, dest_key in optional_map.items():
        if src_key in fields:
            payload[dest_key] = fields[src_key]

    return payload


def run(port: str, baud: int, backend_url: str, device_code: str):
    print(f"Opening serial port {port} @ {baud} baud...")
    try:
        ser = serial.Serial(port, baud, timeout=5)
    except serial.SerialException as e:
        print(f"ERROR: could not open serial port {port}: {e}")
        sys.exit(1)

    time.sleep(2)  # let the connection settle
    print(f"Listening for readings. Forwarding to {backend_url}")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            raw = ser.readline()
            if not raw:
                continue  # timeout with no data, just loop again

            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            print(f"[Bluetooth] {line}")
            fields = parse_line(line)
            if not fields:
                print("  -> could not parse, skipping")
                continue

            payload = build_payload(fields, device_code, line)

            try:
                resp = requests.post(backend_url, json=payload, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"  -> stored. Classification: {data['label']} "
                          f"({data['message']})")
                else:
                    print(f"  -> backend rejected reading: "
                          f"HTTP {resp.status_code} {resp.text}")
            except requests.RequestException as e:
                print(f"  -> could not reach backend: {e}")

        except KeyboardInterrupt:
            print("\nStopping bridge.")
            break
        except Exception as e:
            # Never let one bad line crash the whole bridge process.
            print(f"  -> unexpected error, continuing: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AquaSentry Bluetooth-to-backend bridge")
    parser.add_argument("--port", required=True, help="Serial port, e.g. COM5 or /dev/rfcomm0")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD_RATE)
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--device-code", default=DEFAULT_DEVICE_CODE)
    args = parser.parse_args()

    run(args.port, args.baud, args.backend_url, args.device_code)
