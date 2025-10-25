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
    writer.writerow(["iso_time", "timestamp_ms", "t_c", "rh_pct", "td_c", "dpd_c", "device_id"])
    try:
        while True:
            line = ser.readline().decode("utf-8", "ignore").strip()
            if not line or line.startswith("#"):  # skip blank/header lines
                continue
            parts = line.split(",")
            if len(parts) == 6:
                try:
                    ts_ms, t, rh, td, dpd, device_id = parts
                    writer.writerow([
                        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),  # actual UTC time
                        int(ts_ms),
                        float(t),
                        float(rh),
                        float(td),
                        float(dpd),
                        device_id.strip()
                    ])
                    f.flush()
                    print(line)
                except ValueError:
                    pass
            else:
                # optional: print malformed lines for debugging
                if line:
                    print(f"Ignored line: {line}")
    except KeyboardInterrupt:
        print("\nLogging stopped by user.")

ser.close()
print(f"Data saved to {OUT_FILE}")
