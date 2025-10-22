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

from adafruit_bmp280 import Adafruit_BMP280_I2C
import adafruit_sht31d

# ----------- LEDs -----------------------
# Initialize global variables for the main loop.
ledpin= digitalio.DigitalInOut(board.BLUE_LED)
ledpin.direction = digitalio.Direction.OUTPUT

def set_led(mode):
    """
    LED rules:
    on  - solid ON for HIGH risk
    off - OFF for SAFE
    blink - toggled each sample for WARN
    """
    if mode == "on":
        ledpin.value = True
    elif mode == "off":
        ledpin.value = False
    elif mode == "blink":
        ledpin.value = not ledpin.value

# ----------- I2C + sensors -----------------------
i2c = board.I2C()                       # uses board.SCL and board.SDA
bmp280 = Adafruit_BMP280_I2C(i2c)       # pressure + temp (not used for temp here)
sht31 = adafruit_sht31d.SHT31D(i2c)     # temp + humidity

# ----------- BLE setup ----------------------------
ble = BLERadio()
ble.name = "21399066"
uart = UARTService()
advertisement = ProvideServicesAdvertisement(uart)

# Flags for detecting state changes.
advertised = False
connected  = False

# ----------- Simulation setup ----------------------------
USE_SIMULATION = False
SIM_ROWS = []
sim_idx = 0

try:
    if "sim_data.csv" in os.listdir("/"):
        with open("/sim_data.csv") as f:
            lines = f.readlines()

        for i, line in enumerate(lines):          
            if i == 0:  # skip header
                continue
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) >= 2:
                try:
                    t = float(parts[0])
                    rh = float(parts[1])
                    SIM_ROWS.append((t, rh))
                except ValueError:
                    pass

        if SIM_ROWS:
            USE_SIMULATION = True
            print(f"Simulation enabled: {len(SIM_ROWS)} rows loaded.")
        else:
            print("sim_data.csv empty/invalid; using real sensors")

    else:
        print("No sim_data.csv found; using real sensors.")
except Exception as e:
    print("Error loading sim_data.csv; using real sensors. Err: ", e)

# ----------- Timing setup ---------------------------
# The sensor sampling rate is precisely regulated using the following timer variables.
sampling_timer    = 0.0
last_time         = time.monotonic()
sampling_interval = 1.0     # 1 Hz  

# ----------- Dew point & Risk Config ---------------------------
# Magnus constants for dew point
A, B = 17.62, 243.12

def dew_point_c(t_c, rh_pct):
    """
    Compute dew point from air temp and relative humidity
    using Magnus-type formulation
    """
    # Bound RH to avoid log(0) and >100% anomalities
    rh = max(1e-6, min(100.0, rh_pct))
    gamma = math.log(rh/100.0) + (A * t_c) / (B + t_c)

    return (B * gamma)/(A - gamma)

def ema(prev, new, alpha=0.3):
    """
    Exponential Moving Average to smooth sensor noise
    alpha ~ 0.3 gives moderate smoothing without excessive lag
    """
    if prev is None:
        return new
    else:
        return (alpha * new + (1 - alpha) * prev)
    
# Risk thresholds
RH_WARN = 60.0  # % RH
RH_HIGH = 75.0  # % RH
DPD_HIGH = 3.0  # °C (T - Td)

# Persistence windows, mould growth needs time at high moisture
PERSIST_WARN_S = 30 * 60        # 30 mins for WARN
PERSIST_HIGH_S = 2 * 60 * 60    # 2 hrs for HIGH

# ----------- State (smoothed) ------------------------------------------
t_ema = None
rh_ema = None
td_ema = None
dpd_ema = None

# Persistence accumlators (seconds)
warn_accum = 0.0
high_accum = 0.0
risk_state =  "SAFE"

# Pre-init
temp_c = None
humidity_rh = None
pressure_hpa = None

# ----------- Main loop ------------------------------------------
while True:

    # wait until sampling interval has elapsed
    now = time.monotonic()
    interval = now - last_time
    last_time = now
    sampling_timer -= interval

    did_sample = False
    if sampling_timer < 0.0:
        sampling_timer += sampling_interval
        did_sample = True

        #use dataset for simulation if available
        if USE_SIMULATION:
            temp_c, humidity_rh = SIM_ROWS[sim_idx]
            sim_idx = (sim_idx + 1) % len(SIM_ROWS)
        else:

            # read temp + humidity sensors
            try:
                temp_c = sht31.temperature
                humidity_rh = sht31.relative_humidity
            except Exception as e:
                # if SHT31 errors, skip this cycle
                print("SHT31 read error:", e)
                temp_c = None
                humidity_rh = None

        # read real pressure
        try: 
            pressure_hpa = bmp280.pressure
        except Exception as e:
            print("BMP280 read error", e)
            pressure_hpa = None

        # --- Calculations ---
        # dew point (Td) & Dew-Point (DPD = T - Td)
        if (temp_c is not None) and (humidity_rh is not None):
            try:
                td = dew_point_c(temp_c, humidity_rh)
                dpd = temp_c - td 
            except Exception as e:
                print("Dew point calc error", e)
                td = None
                dpd = None

    # --- BLE state machine ---
    if not advertised:
        ble.start_advertising(advertisement)
        print("Waiting for connection.")
        advertised = True

    if not connected and ble.connected:
        print("Connection received.")
        connected = True
        ledpin.value = True
        
    if connected and not ble.connected:
            print("Connection lost.")
            connected = False
            advertised = False
            ledpin.value = False            

    if connected and did_sample:
        if (temp_c is not None) and (humidity_rh is not None) and (pressure_hpa is not None):
            try: 
                uart.write(b"%.3f,%.3f,%.3f\n" % (temp_c, humidity_rh, pressure_hpa))
            except Exception as e:
                print("UART write error:", e)