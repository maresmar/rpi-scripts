import json
import os
import time
from typing import Tuple

import mh_z19
import paho.mqtt.publish as publish
import smbus
import zc.lockfile
from bmp280 import BMP280
from dotenv import load_dotenv

load_dotenv()
MQTT_PREFIX = os.getenv("MQTT_PREFIX");
MQTT_CLIENT = os.getenv("MQTT_CLIENT");


def crc_checksum(data):
    POLYNOMIAL = 0x131  # //P(x)=x^8+x^5+x^4+1 = 100110001
    crc = 0xFF

    # calculates 8-Bit checksum with given polynomial
    for byte in data:
        crc ^= byte
        for bit in range(8, 0, -1):
            if crc & 0x80:
                crc = (crc << 1) ^ POLYNOMIAL
            else:
                crc = (crc << 1)
    return crc


def read_sht31(bus) -> Tuple[float, float]:
    # SHT31 address, 0x44(68)
    bus.write_i2c_block_data(0x44, 0x2C, [0x06])

    time.sleep(0.5)

    # SHT31 address, 0x44(68)
    # Read data back from 0x00(00), 6 bytes
    # Temp MSB, Temp LSB, Temp CRC, Humididty MSB, Humidity LSB, Humidity CRC
    data = bus.read_i2c_block_data(0x44, 0x00, 6)

    # Convert the data
    temp = data[0] * 256 + data[1]
    if crc_checksum(data[0:2]) == data[2] and crc_checksum(data[3:5]) == data[5]:
        temp = -45 + (175 * temp / 65535.0)
        humidity = 100 * (data[3] * 256 + data[4]) / 65535.0
    else:
        temp = None
        humidity = None

    return temp, humidity


def read_light(bus) -> float:
    # BH1750

    # Constants
    LIGHT_ADDRS = 0x23
    POWER_ON = 0x01
    ONE_TIME_HIGH_RES_MODE_2 = 0x21
    # Start measurement at 0.5lx resolution. Time typically 120ms
    # Device is automatically set to Power Down after measurement.

    # Measurement
    time.sleep(0.180)
    bus.write_byte(LIGHT_ADDRS, POWER_ON)
    time.sleep(0.180)
    bus.write_byte(LIGHT_ADDRS, ONE_TIME_HIGH_RES_MODE_2)
    time.sleep(0.180)
    data = bus.read_i2c_block_data(LIGHT_ADDRS, ONE_TIME_HIGH_RES_MODE_2)
    light = ((data[0] << 8) + data[1]) / 1.2

    return light


if __name__ == "__main__":
    # Lock the GPIO access
    lock = zc.lockfile.LockFile('/tmp/gpio.lock')

    try:
        # Get I2C bus
        bus = smbus.SMBus(1)

        # Temp
        temp, humidity = read_sht31(bus)

        # Light
        light = read_light(bus)

        # Pressure - BMP280
        bmp280 = BMP280(i2c_dev=bus)
        bmp280.setup()
        pressure = bmp280.get_pressure()
        if pressure < 900:
            pressure = None

        # CO2 - MH-Z19B
        mh_z19.abc_off()
        mh_z19.detection_range_10000()
        data = mh_z19.read(True)
        if data:
            co2 = data["co2"]
        else:
            co2 = None

        # Preperat output data
        data = {"temp": temp,
                "humidity": humidity,
                "light": light,
                "pressure": pressure,
                "co2": co2
                }
        print(json.dumps(data))

        # Current time in milis
        data["time"] = int(time.time()*1000)

        publish.single(f"{MQTT_PREFIX}/sensors",
                       payload=json.dumps(data),
                       hostname="localhost",
                       client_id=MQTT_CLIENT,
                       retain=True)

    finally:
        if bus:
            bus.close()
        if lock:
            lock.close()
