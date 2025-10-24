import serial
import csv
import sys
from datetime import datetime, timezone

# --- config -----------
PORT = "/dev/ttyACM0"
BAUD = 115200
OUT_FILE = "run_log.csv"
# ----------------------

def find_port():
    # Prefer /dev/ttyACM* (CircuitPython/Feather on Linux)
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if "ACM" in p.device or "usbmodem" in p.device:
            return p.device
    # Fallback: first available
    return ports[0].device if ports else None

def open_port():
    dev = find_port()
    if not dev:
        print("No serial ports found.")
        sys.exit(1)
    print(f"Opening {dev} @ {BAUD}…")
    ser = serial.Serial(dev, BAUD, timeout=1)
    # Clear any partial line
    try:
        ser.reset_input_buffer()
    except Exception:
        pass
    return ser

def now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

while True:
    try:
        ser = open_port()
        print("Logging started… (Ctrl+C to stop)")
        with open(OUT_FILE, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["iso_time","t_c","rh_pct","td_c","dpd_c","risk"])
            while True:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", "ignore").strip()
                parts = line.split(",")
                if len(parts) != 5:
                    # ignore any non-data lines
                    continue
                try:
                    t, rh, td, dpd, risk = parts
                    w.writerow([now_utc(), float(t), float(rh), float(td), float(dpd), int(risk)])
                    f.flush()
                    print(line)
                except ValueError:
                    # malformed numeric line; skip
                    continue
    except KeyboardInterrupt:
        print("\nStopped by user.")
        break
    except (serial.SerialException, OSError) as e:
        # Device was unplugged, rebooted, or port busy—retry after a short pause
        print(f"[warn] Serial error: {e}. Reconnecting in 2s…")
        try:
            ser.close()
        except Exception:
            pass
        time.sleep(2)
        continue