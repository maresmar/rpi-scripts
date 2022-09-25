#!/bin/python3
import json
import os
import time

from dotenv import load_dotenv
from PyP100 import PyP110

import paho.mqtt.publish as publish

load_dotenv()
MQTT_PREFIX = os.getenv("MQTT_PREFIX");
MQTT_CLIENT = os.getenv("MQTT_CLIENT");
P110_USERNAME = os.getenv("P110_USERNAME");
P110_PASSWORD = os.getenv("P110_PASSWORD");
P110_HOST = os.getenv("P110_HOST");

if __name__ == "__main__":
    p110 = PyP110.P110(P110_HOST, P110_USERNAME, P110_PASSWORD)
    p110.handshake()
    p110.login()
    device_info=p110.getDeviceInfo()
    energy_data=p110.getEnergyUsage()

    # Prepare data
    data = {"today_runtime": energy_data["result"]["today_runtime"], "today_energy": energy_data["result"]["today_energy"], "current_power": energy_data["result"]["current_power"]/1000, "rssi": device_info["result"]["rssi"]}
    print(json.dumps(data))

    # Current time in milis
    data["time"] = int(time.time()*1000)

    publish.single(f"{MQTT_PREFIX}/power",
               payload=json.dumps(data),
               hostname="localhost",
               client_id=MQTT_CLIENT,
               retain=True)

