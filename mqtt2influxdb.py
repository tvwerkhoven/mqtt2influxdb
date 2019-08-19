#!/usr/bin/env python3
# 
# mqtt to influxdb bridge, based on https://github.com/gonzalo123/iot.grafana/blob/master/client.py
# docs at https://pypi.org/project/paho-mqtt/#client
# 

import paho.mqtt.client as mqtt
import datetime
import requests
import logging

MQTT_SERVER_IP="172.16.0.2"
INFLUX_WRITE_URI="http://rpi3b:8086/write?db=smarthome&precision=s"


def persists(msg):
    # msg should be like influx/environv2/pm25/state, get measurement and field value to push
    _, measurement, field, _ = msg.topic.split("/")
    query = "{} {}={}".format(measurement, field, float(msg.payload))
    logging.info(query)
    r = requests.post(INFLUX_WRITE_URI, data=query, timeout=10)


logging.basicConfig(level=logging.INFO)
client = mqtt.Client()

client.on_connect = lambda self, mosq, obj, rc: self.subscribe("influx/#")
client.on_message = lambda client, userdata, msg: persists(msg)

client.connect(MQTT_SERVER_IP, 1883, 60)

client.loop_forever()