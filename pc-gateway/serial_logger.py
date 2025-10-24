import serial
import csv
import sys
from datetime import datetime, timezone

# --- config -----------
PORT = "/dev/ttyACM0"
BAUD = 115200
OUT_FILE = "run_log.csv"
# ----------------------

ser = serial.Serial(PORT, BAUD, timeout=1)
print(f"Connected to {PORT} at {BAUD} baud.")
print("Logging started...")

with open(OUT_FILE, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["iso_time","t_c","rh_pct","td_c","dpd_c","risk"])
    try:
        while True:
            line = ser.readline().decode("utf-8", "ignore").strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) == 5:
                try:
                    t, rh, td, dpd, risk = parts
                    writer.writerow([
                        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        float(t), float(rh), float(td), float(dpd), int(risk)
                    ])
                    f.flush()
                    print(line)
                except ValueError:
                    pass
    except KeyboardInterrupt:
        print("\nLogging stopped by user.")

ser.close()
print(f"Data saved to {OUT_FILE}")