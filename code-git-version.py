# -----------------------------------------------------------------
# Mould Risk Detection - BLE Remote Sensing Service
# Simulates temperature and humidty readings and transmits via BLE
# -----------------------------------------------------------------

import time
import digitalio
import board

# Import the Adafruit Bluetooth library.  Technical reference:
# https://circuitpython.readthedocs.io/projects/ble/en/latest/api.html
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

from adafruit_bmp280 import Adafruit_BMP280_I2C

import adafruit_sht31d

# ----------- LEDs -----------------------
# Initialize global variables for the main loop.
ledpin= digitalio.DigitalInOut(board.BLUE_LED)
ledpin.direction = digitalio.Direction.OUTPUT

# ----------- I2C + sensors -----------------------
i2c = board.I2C()                       # uses board.SCL and board.SDA
bmp280 = Adafruit_BMP280_I2C(i2c)       # pressure + temp (not used for temo here)
sht31 = adafruit_sht31d.SHT31D(i2c)     # temp + humidity

# ----------- BLE setup ----------------------------
ble = BLERadio()
ble.name = "21399066"
uart = UARTService()
advertisement = ProvideServicesAdvertisement(uart)

# Flags for detecting state changes.
advertised = False
connected  = False

# ----------- Simulation dataset -----------------------
simulated_data = [
    (19.5, 45.0),
    (20.0, 47.5),
    (21.0, 50.0),
    (22.5, 52.5),
    (23.5, 55.0),
    (24.0, 60.0),
    (24.5, 65.0),
    (25.0, 70.0),
    (25.5, 75.0),
    (26.0, 80.0),
]

data_index = 0

# ----------- Timing setup ---------------------------
# The sensor sampling rate is precisely regulated using the following timer variables.
sampling_timer    = 0.0
last_time         = time.monotonic()
sampling_interval = 1.0     # ~1 Hz

# ----------- Main loop ------------------------------------------
# Begin the main processing loop.

while True:

    # wait until sampling interval has elapsed
    now = time.monotonic()
    interval = now - last_time
    last_time = now
    sampling_timer -= interval

    if sampling_timer < 0.0:
        sampling_timer += sampling_interval

        # read sensors
        try:
            temp_c = sht31.temperature
            humidity_rh = sht31.relative_humidity
        except Exception as e:
            # if SHT31 errors, skip this cycle
            print("SHT31 read error:", e)
            temp_c = None
            humidity_rh = None

        try: 
            pressure_hpa = bmp280.pressure
        except Exception as e:
            print("BMP280 read error", e)
            pressure_hpa = None

    if not advertised:
        ble.start_advertising(advertisement)
        print("Waiting for connection.")
        advertised = True

    if not connected and ble.connected:
        print("Connection received.")
        connected = True
        ledpin.value = True
        
    if connected:
        if not ble.connected:
            print("Connection lost.")
            connected = False
            advertised = False
            ledpin.value = False            
        else:
            if (temp_c is not None) and (humidity_rh is not None) and (pressure_hpa is not None):
                uart.write(b"%.3f,%.3f,%.3f\n" % (temp_c, humidity_rh, pressure_hpa))