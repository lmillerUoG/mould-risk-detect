# -----------------------------------------------------------------
# Mould Risk Detection - BLE Remote Sensing Service
# Simulates temperature and humidty readings and transmits via BLE
# -----------------------------------------------------------------

import time
import digitalio
import board
import os
import math

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

import adafruit_sht31d

# ----------- Config -----------------------
DEVICE_ID = "21399066"
SAMPLE_HZ = 1.0     # sampling frequency
USE_SIMULATION = True

# ----------- Demo Mode/ Production Mode -----------------------
DEMO_MODE = True

# ----------- LEDs -----------------------
# Initialize global variables for the main loop.
ledpin= digitalio.DigitalInOut(board.BLUE_LED)
ledpin.direction = digitalio.Direction.OUTPUT

# ----------- I2C + sensors -----------------------
i2c = board.I2C()                       # uses board.SCL and board.SDA
sht31 = adafruit_sht31d.SHT31D(i2c)     # temp + humidity

# ----------- BLE setup ----------------------------
ble = BLERadio()
ble.name = DEVICE_ID
uart = UARTService()
advertisement = ProvideServicesAdvertisement(uart)

# Flags for detecting state changes.
advertised = False
connected  = False

# ----------- Simulation setup ----------------------------
sim_file = None

if USE_SIMULATION:
    try:
        if "sim_data.csv" in os.listdir("/"):
            sim_file = open("/sim_data.csv", "r")
            _ = sim_file.readline()  # skip header
            print("Simulation enabled: streaming sim_data.csv")
        else:
            print("sim_data.csv not found; switching to real sensor mode.")
            USE_SIMULATION = False
    except Exception as e:
        print("Error opening sim_data.csv; switching to real sensor mode. Err:", e)
        USE_SIMULATION = False
else:
    print("Simulation disabled; using real SHT31D sensor.")

def sim_next_row():
    """
    Return (temp_c, rh_pct) from the next line; loop to start at EOF.
    """
    global sim_file
    if sim_file is None:
        return None
    line = sim_file.readline()
    if not line: # end of file
        try:
            sim_file.seek(0)
            _ = sim_file.readline()
            line = sim_file.readline()
        except Exception:
            return None
        if not line:
            return None
    parts = line.strip().split(",")
    if len(parts) < 2:
        return sim_next_row()
    try:
        t = float(parts[0])
        rh = float(parts[1])
        return (t, rh)
    except ValueError:
        return sim_next_row()

# ----------- Timing setup ---------------------------
# The sensor sampling rate is precisely regulated using the following timer variables.
sampling_timer    = 0.0
last_time         = time.monotonic()
sampling_interval = 1.0 / SAMPLE_HZ

# ----------- Dew point & Risk Config ---------------------------
# Magnus constants for °C 
A, B = 17.62, 243.12

def dew_point_c(t_c, rh_pct):
    """
    Compute dew point from air temp and relative humidity
    using Magnus-type formulation
    """
    # Bound RH to avoid log(0) and >100% anormalities
    rh = max(1e-6, min(100.0, rh_pct))
    gamma = math.log(rh/100.0) + (A * t_c) / (B + t_c)

    return (B * gamma)/(A - gamma)

# Pre-init
temp_c = None
humidity_rh = None

# ----------- Main loop ------------------------------------------
while True:
    now = time.monotonic()
    interval = now - last_time
    if interval > 5 * sampling_interval:
        interval = sampling_interval
    last_time = now
    sampling_timer -= interval

    did_sample = False
    if sampling_timer < 0.0:
        sampling_timer += sampling_interval
        did_sample = True

        # choose data source
        if USE_SIMULATION:
            row = sim_next_row()
            if row:
                temp_c, humidity_rh = row
            else:
                temp_c = None
                humidity_rh = None
        else:
            try:
                temp_c = sht31.temperature
                humidity_rh = sht31.relative_humidity
            except Exception as e:
                print("SHT31 read error:", e)
                temp_c = None
                humidity_rh = None

    # --- BLE state machine ---
    if not advertised:
        ble.start_advertising(advertisement)
        print("Waiting for connection.")
        advertised = True

    if not connected and ble.connected:
        print("Connection received.")
        connected = True
        ledpin.value = False
        
    if connected and not ble.connected:
            print("Connection lost.")
            connected = False
            advertised = False
            ledpin.value = False

    if connected and did_sample and (temp_c is not None) and (humidity_rh is not None):
            try: 
                td = dew_point_c(temp_c, humidity_rh)
                dpd = temp_c - td
                ts_ms = int(time.monotonic()*1000)
               
                uart.write(b"%d,%.3f,%.3f,%.3f,%.3f\n" % (ts_ms, temp_c, humidity_rh, td, dpd))
            
                # USB serial print
                print("{},{:.3f},{:.3f},{:.3f},{:.3f}".format(ts_ms, temp_c, humidity_rh, td, dpd))
            except Exception as e:
                print("UART write error:", e)