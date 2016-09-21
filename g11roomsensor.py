#!/usr/bin/env python3

import network
import onewire
import time
import ujson
from machine import Pin, unique_id
from ubinascii import hexlify
from umqtt.robust import MQTTClient

onewire_pin = 5
pir_pin = 14

def main():
    config = ujson.loads(open("config.json", "r").read())

    ap = network.WLAN(network.AP_IF)
    ap.active(False)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(config["ssid"], config["password"])
    while not wlan.isconnected():
        pass
    print('network config:', wlan.ifconfig())

    client_id = hexlify(unique_id()).decode()
    mqtt = MQTTClient(client_id, config["mqtt_host"], config["mqtt_port"])
    mqtt.connect()

    ds = onewire.DS18B20(onewire.OneWire(Pin(onewire_pin)))
    pir = Pin(pir_pin, mode=Pin.IN, pull=Pin.PULL_UP)

    devices = ds.scan()
    for device in devices:
        print("found %s" % (hexlify(device)))

    last_temperature_start = time.ticks_ms()
    last_temperature_publish = time.ticks_ms()
    last_pir_publish = time.ticks_ms()
    last_pir_state = None

    while True:

        if last_temperature_start is not None:
            if time.ticks_diff(last_temperature_start, time.ticks_ms()) > 750:
                for device in devices:
                    temperature = ds.read_temp(device)
                    device_string = hexlify(device).decode()
                    topic = config.get("ds18b20_topic_prefix", "test/ds18b20/" + client_id) + "/" + device_string
                    mqtt.publish(topic, "%.2f" % (temperature), retain=True)
                last_temperature_start = None
                last_temperature_publish = time.ticks_ms()
            else:
                # reading not ready yet
                pass
        else:
            if time.ticks_diff(last_temperature_publish, time.ticks_ms()) > 10000:
                ds.convert_temp()
                last_temperature_start = time.ticks_ms()

        new_pir_state = pir.value()

        if new_pir_state != last_pir_state:
            print("pir=%s" % (new_pir_state))
            mqtt.publish("test/%s/pir" % (client_id), str(new_pir_state))
            last_pir_state = new_pir_state

        if new_pir_state == 1:
            if time.ticks_diff(last_pir_publish, time.ticks_ms()) > 5000:
                mqtt.publish(config.get("pir_topic", "test/%s/pir" % (client_id)), "")
                last_pir_publish = time.ticks_ms()

main()
