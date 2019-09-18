#!/usr/bin/env python3
# 
# mqtt to influxdb bridge, based on https://github.com/gonzalo123/iot.grafana/blob/master/client.py
# docs at https://pypi.org/project/paho-mqtt/#client
# 

import paho.mqtt.client as mqtt
import datetime
import requests
import logging

MQTT_SERVER_IP="localhost"
INFLUX_WRITE_URI="http://localhost:8086/write?db=smarthome&precision=s"


def persists(msg):
    # msg.topic should be like 
    # influx/<measurement>/[<tagname>/<tagvalue>/]*<field>/state, which is 
    # converted into 
    # measurement,[tagname=tagvalue]* field=msg.payload

    # Old code without tags:
    # _, measurement, field, _ = msg.topic.split("/")
    # query = "{} {}={}".format(measurement, field, float(msg.payload))

    msgarr = msg.topic.split("/")

    # Check topic has even number of fields
    if (len(msgarr) % 2 != 0):
        logging.warn("Malformed topic does not have even number of fields: {}".format(msg.topic))
        return

    # Check topic starts with 'influx' and ends with 'state'
    i_influx = msgarr.pop(0)
    i_state = msgarr.pop()
    if (i_state != 'state' or i_influx != 'influx'):
        logging.warn("Malformed topic not ending in 'state' or starting with 'influx': {}".format(msg.topic))
        return

    # Get measurement & field name
    i_meas = msgarr.pop(0)
    i_field = msgarr.pop()

    # Init query, check for any remaining tags
    query = "{}".format(i_meas)

    for tag_key, tag_val in zip(msgarr[::2], msgarr[1::2]):
        query += ",{}={}".format(tag_key, tag_val)

    query += " {}={}".format(i_field, float(msg.payload))

    logging.info(query)
    r = requests.post(INFLUX_WRITE_URI, data=query, timeout=10)


logging.basicConfig(level=logging.INFO)
client = mqtt.Client()
client.username_pw_set("username", "passwd")

client.on_connect = lambda self, mosq, obj, rc: self.subscribe("influx/#")
client.on_message = lambda client, userdata, msg: persists(msg)

logging.info("Connecting to {}:1883".format(MQTT_SERVER_IP))
client.connect(MQTT_SERVER_IP, 1883, 60)

logging.info("Starting listen loop forever...")
client.loop_forever()
