# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.
import os
import json
import time
from azure.iot.device import IoTHubDeviceClient, Message
from central import iter_readings

# The device connection authenticates your device to your IoT hub. The connection string for 
# a device should never be stored in code. For the sake of simplicity we're using an environment 
# variable here. If you created the environment variable with the IDE running, stop and restart 
# the IDE to pick up the environment variable.
#
# You can use the Azure CLI to find the connection string:
# az iot hub device-identity show-connection-string --hub-name {YourIoTHubName} --device-id MyNodeDevice --output table


CONNECTION_STRING = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING")

def run_telemetry_sample(client):
    # This sample will send temperature telemetry every second
    print("IoT Hub device sending periodic messages")

    client.connect()
    
    # read dicts from central.py
    for reading in iter_readings():
        body = json.dumps(reading)
        message = Message(body)


        # Add a custom application property to the message.
        # An IoT hub can filter on these properties without access to the message body.
        rh = float(reading.get("humidity_pct", 0) or 0)
        dpd = float(reading.get("dpd_c", 0) or 0)

        message.custom_properties["rhBand"] = (
            "high" if rh >= 80 else "warning" if rh >= 60 else "normal"
        )
        message.custom_properties["dpdBand"] = (
            "high" if dpd <= 4 else "safe"
        )


        # Send the message.
        print("Sending message:", body)
        client.send_message(message)
        print("Message successfully sent")
        time.sleep(0.1)


def main():
    print("IoT Hub Quickstart #1 - Simulated device")
    print("Press Ctrl-C to exit")

    # Instantiate the client. Use the same instance of the client for the duration of
    # your application
    client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)

    # Run Sample
    try:
        run_telemetry_sample(client)
    except KeyboardInterrupt:
        print("IoTHubClient sample stopped by user")
    finally:
        # Upon application exit, shut down the client
        print("Shutting down IoTHubClient")
        client.shutdown()

if __name__ == '__main__':
    main()