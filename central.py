
# Import the Adafruit Bluetooth library, part of Blinka.  Technical reference:
# https://circuitpython.readthedocs.io/projects/ble/en/latest/api.html

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

from typing import Iterator, Dict

import time

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(min(v, hi), lo)

# helper to prse the CSV from code.py
def _parse_csv(line: str) -> Dict:
    # expect: t_c,rh_pct,td_c,dpd_c
    parts = [p.strip() for p in line.split(",")]

    if len(parts) < 5:
        raise ValueError("not enough fields")
    
    ts_ms = int(float(parts[0]))
    t_c = float(parts[1])
    rh = float(parts[2])
    td = float(parts[3])
    dpd = float(parts[4])

    t_c = _clamp(t_c, -40, 85.0)
    rh = _clamp(rh, 0.0, 100)

    reading = {
        "ts_ms": ts_ms,
        "temperature_c": round(t_c, 2),
        "humidity_pct": round(rh, 2),
        "dewpoint_c": round(td, 2),
        "dpd_c": round(dpd, 2)
    }

    return reading

# iterable for gateway_iothub.py
def iter_readings() -> Iterator[Dict]:

    # Initialize global variables for the main loop.
    ble = BLERadio()
    uart_connection = None

    while True:
        # (re)connect if needed
        if not uart_connection:
            for adv in ble.start_scan(ProvideServicesAdvertisement):
                if UARTService in adv.services:
                    try:
                        uart_connection = ble.connection(adv)
                        break
                    except Exception:
                        # try next advertisement
                        pass
            ble.stop_scan()

        if not uart_connection:
            # brief backoff before rescanning
            time.sleep(1.0)
            continue

        # read lines while connected
        try:
            uart_service = uart_connection[UARTService]
            while uart_connection.connected:
                raw = uart_service.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", "ignore").rstrip()
                #parse to dict and yield
                try: 
                    yield _parse_csv(line)
                except Exception:
                    # skip malformed lines
                    continue
        except Exception:
            # drop connection + rescan
            try:
                uart_connection.disconnect()
            except Exception:
                pass
            uart_connection = None    
                

# ----------------------------------------------------------------
# Begin the main processing loop.
if __name__ == "__main__":

    ble = BLERadio()
    uart_connection = None

    while True:
        if not uart_connection:
            print("Trying to connect...")
            # Check for any device advertising services
            for adv in ble.start_scan(ProvideServicesAdvertisement):
                # Print name of the device
                name = adv.complete_name
                if name:
                    print(name)
                # Print what services that are being advertised
                for svc in adv.services:
                    print(str(svc))
                # Look for UART service and establish connection
                if UARTService in adv.services:
                    uart_connection = ble.connect(adv)
                    print("Connected")
                    break
            ble.stop_scan()
    
        # Once connected start receiving data
        if uart_connection and uart_connection.connected:
            uart_service = uart_connection[UARTService]
            while uart_connection.connected:
                print(uart_service.readline().decode("utf-8").rstrip())