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
EMA_ALPHA = 0.3     # smoothing factor

# Risk thresholds
RH_WARN = 60.0      # % RH
RH_HIGH = 75.0      # % RH
DPD_HIGH = 3.0      # °C (T - Td)

# Persistence windows (seconds)
PERSIST_WARN_S = 30 * 60        # 30 mins for WARN
PERSIST_HIGH_S = 2 * 60 * 60    # 2 hrs for HIGH

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
sampling_interval = 1.0 / SAMPLE_HZ
boot_time = last_time   # for relative timestamps

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

def ema(prev, new, alpha=0.3):
    """
    Exponential Moving Average to smooth sensor noise
    alpha ~ 0.3 gives moderate smoothing without excessive lag
    """
    if prev is None:
        return new
    else:
        return (alpha * new + (1 - alpha) * prev)
    

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


# ----------- Main loop ------------------------------------------
while True:

    # wait until sampling interval has elapsed
    now = time.monotonic()

    # clamp extreme gaps to avoid big accumulator jumps
    interval = now - last_time
    if interval > 5 * sampling_interval:
        interval = sampling_interval

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

        # --- Calculations ---
        # dew point (Td) & Dew-Point (DPD = T - Td)
        td = None
        dpd = None
        if (temp_c is not None) and (humidity_rh is not None):
            try:
                td = dew_point_c(temp_c, humidity_rh)
                dpd = temp_c - td 
            except Exception as e:
                print("Dew point calc error", e)
                td = None
                dpd = None

            # smooth signals to avoid twitchy alerts due to momentary spikes
            if temp_c is not None:
                t_ema = ema(t_ema, temp_c)
            if humidity_rh is not None:
                rh_ema = ema(rh_ema, humidity_rh)
            if td is not None:
                td_ema = ema(td_ema, td)
            if dpd is not None:
                dpd_ema = ema(dpd_ema, dpd)
            
            # --- Persistance logic ---
                # WARN: rh sustained above RH_WARN
                # HIGH: rh sustained above RH_HIGH or DPD sustained <= DPD_HIGH (if available)
            if (rh_ema is not None) and (dpd_ema is not None):
                cond_warn = (rh_ema >= RH_WARN)
                cond_high = (rh_ema >= RH_HIGH) or ((dpd_ema is not None) and (dpd_ema <= DPD_HIGH))

                # accumulate while condition holds
                # decay while not
                if cond_warn:
                    warn_accum = max(0.0, warn_accum + interval)
                else:
                    warn_accum = max(0.0, warn_accum - interval)

                if cond_high:
                    high_accum = max(0.0, high_accum + interval)
                else:
                    high_accum = max(0.0, high_accum - interval)
                
                # state transition
                if high_accum >= PERSIST_HIGH_S:
                    risk_state = "HIGH"
                elif warn_accum >=  PERSIST_WARN_S:
                    risk_state = "WARN"
                else:
                    risk_state = "SAFE"

                # set LED per state
                if risk_state == "HIGH":
                    set_led("on")
                elif risk_state == "WARN":
                    set_led("blink")
                else:
                    set_led("off")


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
        if (temp_c is not None) and (humidity_rh is not None):
            #use smoothed values when available
            t_out = t_ema if t_ema is not None else temp_c
            rh_out = rh_ema if rh_ema is not None else humidity_rh
            td_out = td_ema if td_ema is not None else dew_point_c(temp_c, humidity_rh)
            dpd_out = dpd_ema if dpd_ema is not None else (t_out - td_out)

            
            if risk_state == "HIGH":
                risk_flag = 2
            elif risk_state == "WARN":
                risk_flag = 1
            else:
                risk_flag = 0

            try: 
                uart.write(b"%.3f,%.3f,%.3f,%.3f,%d\n" % (t_out, rh_out, td_out, dpd_out, risk_flag))
            except Exception as e:
                print("UART write error:", e)