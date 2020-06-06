#!/usr/bin/env python3
# 
# mqtt to influxdb bridge
# based on https://github.com/gonzalo123/iot.grafana/blob/master/client.py
# depends on https://pypi.org/project/paho-mqtt/#client
#
# Start in crontab as 
# @reboot <path>/mqtt2influxdb.py 

import paho.mqtt.client as mqtt
import datetime
import requests
import logging
import logging.handlers
import yaml

my_logger = logging.getLogger('MyLogger')
my_logger.setLevel(logging.INFO)

handler = logging.handlers.SysLogHandler(address = '/dev/log')
my_logger.addHandler(handler)

with open("config.yasml", 'r') as stream:
    try:
        data = yaml.safe_load(stream)
        MQTT_SERVER_HOST = data['mqtt2influxdb']['mqqt_server_host']
        MQTT_CLIENT_USERNAME = data['mqtt2influxdb']['mqqt_client_username']
        MQTT_CLIENT_PASSWD = data['mqtt2influxdb']['mqqt_client_passwd']
        INFLUX_WRITE_URI = data['mqtt2influxdb']['influx_write_uri']
    except yaml.YAMLError as exc:
        my_logger.exception('Could not load yaml file')

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
        my_logger.warn("Malformed topic does not have even number of fields: {}".format(msg.topic))
        return

    # Check topic starts with 'influx' and ends with 'state'
    i_influx = msgarr.pop(0)
    i_state = msgarr.pop()
    if (i_state != 'state' or i_influx != 'influx'):
        my_logger.warn("Malformed topic not ending in 'state' or starting with 'influx': {}".format(msg.topic))
        return

    # Get measurement & field name
    i_meas = msgarr.pop(0)
    i_field = msgarr.pop()

    # Init query, check for any remaining tags
    query = "{}".format(i_meas)

    for tag_key, tag_val in zip(msgarr[::2], msgarr[1::2]):
        query += ",{}={}".format(tag_key, tag_val)

    query += " {}={}".format(i_field, float(msg.payload))

    my_logger.info(query)
    r = requests.post(INFLUX_WRITE_URI, data=query, timeout=10)


client = mqtt.Client()
client.username_pw_set(MQTT_CLIENT_USERNAME, MQTT_CLIENT_PASSWD)

client.on_connect = lambda self, mosq, obj, rc: self.subscribe("influx/#")
client.on_message = lambda client, userdata, msg: persists(msg)

my_logger.info("Connecting to {}:1883".format(MQTT_SERVER_HOST))
client.connect(MQTT_SERVER_HOST, 1883, 60)

my_logger.info("Starting listen loop forever...")
client.loop_forever()
