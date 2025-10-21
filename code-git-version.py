# Provide a remote sensing service over Bluetooth Low-Energy (BLE).
# ----------------------------------------------------------------
# Import the standard Python time functions.
import time
import digitalio
import board

# Import the Adafruit Bluetooth library.  Technical reference:
# https://circuitpython.readthedocs.io/projects/ble/en/latest/api.html
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

from adafruit_bmp280 import Adafruit_BMP280_I2C

# ----------------------------------------------------------------
# Initialize global variables for the main loop.
ledpin= digitalio.DigitalInOut(board.BLUE_LED)
ledpin.direction = digitalio.Direction.OUTPUT

# I2C + BMP280 (for temperature)
i2c = board.I2C()  # uses board.SCL and board.SDA
bmp280 = Adafruit_BMP280_I2C(i2c)

ble = BLERadio()
ble.name = "21399066"
uart = UARTService()
advertisement = ProvideServicesAdvertisement(uart)

# Flags for detecting state changes.
advertised = False
connected  = False

# The sensor sampling rate is precisely regulated using the following timer variables.
sampling_timer    = 0.0
last_time         = time.monotonic()
sampling_interval = 0.10

# ----------------------------------------------------------------
# Begin the main processing loop.

while True:

    # Read the accelerometer at regular intervals.  Measure elapsed time and
    # wait until the update timer has elapsed.
    now = time.monotonic()
    interval = now - last_time
    last_time = now
    sampling_timer -= interval
    if sampling_timer < 0.0:
        sampling_timer += sampling_interval
        x = bmp280.temperature
        y, z = (20,30)
    else:
        x = None

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
            if x is not None:
                uart.write(b"%.3f,%.3f,%.3f\n" % (x, y, z))