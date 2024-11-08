#!/usr/bin/env python3
# 
# mqtt to influxdb bridge
# based on https://github.com/gonzalo123/iot.grafana/blob/master/client.py
# depends on https://pypi.org/project/paho-mqtt/#client
#
# Start in crontab as 
# @reboot <path>/mqtt2influxdb.py 
# Debug with 
# @reboot ( <path>/mqtt2influxdb.py ) >> /tmp/mqtt2influxdb-debug.log 2>&1
#
# Alternatively, run using systemd after influxdb & mosquitto are up
# - https://stackoverflow.com/questions/21830670/start-systemd-service-after-specific-service
# - https://unix.stackexchange.com/questions/47695/how-to-write-startup-script-for-systemd
# /etc/systemd/system/mqtt2influxdb.service && systemctl enable mqtt2influxdb.service
# [Unit]
# Description=mqtt2influxdb
# After=influxdb.service mosquitto.service

# [Service]
# User=tim
# Group=tim
# Type=oneshot
# ExecStart=/home/tim/workers/mqtt2influxdb/mqtt2influxdb.py
# Restart=on-failure

# [Install]
# WantedBy=multi-user.target

import paho.mqtt.client as mqtt
import datetime
import requests
import logging
import logging.handlers
import yaml
import os, sys
import json
import time
import re

# Init logger
# https://docs.python.org/3/howto/logging.html#configuring-logging
my_logger = logging.getLogger("MyLogger")
my_logger.setLevel(logging.WARNING)

# create console handler and set level to debug
handler_stream = logging.StreamHandler()
handler_stream.setLevel(logging.DEBUG)
my_logger.addHandler(handler_stream)

# create syslog handler which also shows filename in log
handler_syslog = logging.handlers.SysLogHandler(address = '/dev/log')
formatter = logging.Formatter('%(filename)s: %(message)s')
handler_syslog.setFormatter(formatter)
#handler_syslog.setLevel(logging.INFO)
handler_syslog.setLevel(logging.WARNING)
my_logger.addHandler(handler_syslog)

my_logger.info("Starting mqtt2influxdb...")

# Load config from same dir as file. hacky? yes.
# https://www.tutorialspoint.com/How-to-open-a-file-in-the-same-directory-as-a-Python-script
# with open("./config.yaml", 'r') as stream:
with open(os.path.join(sys.path[0], "config.yaml"), 'r') as stream:
    try:
        data = yaml.safe_load(stream)
        MQTT_SERVER_HOST = data['mqtt2influxdb']['mqqt_server_host']
        MQTT_CLIENT_USERNAME = data['mqtt2influxdb']['mqqt_client_username']
        MQTT_CLIENT_PASSWD = data['mqtt2influxdb']['mqqt_client_passwd']
        INFLUX_WRITE_URI = data['mqtt2influxdb']['influx_write_uri']
        INFLUX_QUERY_URI = data['mqtt2influxdb']['influx_query_uri']

        # Influxdb settings URI
        INFLUX_USER = data['influx_username']
        INFLUX_PASSWD = data['influx_password']
    except yaml.YAMLError as exc:
        my_logger.exception('Could not load config from yaml file: {}'.format(exc))

def do_connect(client, mosq, obj, rc):
    if rc == 0:
        client.subscribe("influx/#")
        client.subscribe("plugwise2mqtt/#")
    else:
        my_logger.error("Connection to broker failed")

def parse_message(client, userdata, msg):
    msgarr = msg.topic.split("/")

    try:
        if msgarr[0] == 'influx':
            parse_esphome(msg)
        elif msgarr[0] == 'plugwise2mqtt':
            parse_plugwise(msg)
    except:
        my_logger.error('Could not parse message: {} with payload: {}'.format(msg.topic, msg.payload))
        pass

def parse_plugwise(msg):
    # msg.topic should be like 
    # plugwise2mqtt/state/energy/000D6F0002588E41
    # msg.payload should be like
    # {"typ":"pwenergy","ts":1645123620,"mac":"000D6F0002588E41","power":0.0000,"energy":0.0000,"cum_energy":23816.2021,"interval":1}, which is 
    # 
    # energyv3,quantity='electricity',type='consumption',source=,uniqueid=000D6F0002588E41 value=msg.payload.cum_energy msg.payload.ts

    id_sourcemap = {
        '88e41':'thermomix',
        '86bc9':'washingmachine',
        '81600':'dishwasher',
        '2664c':'oven'
    }
    payloadjson = json.loads(msg.payload)

    thisuniqueid = str.lower(payloadjson['mac'])
    thissource = id_sourcemap[thisuniqueid[-5:]]
    # Convert from Wh to Joule
    thisenergy = int(payloadjson['cum_energy']*3600)
    thisdate = int(payloadjson['ts'])

    # plugwise2mqtt/state/energy/000D6F0002588E41 {"typ":"pwenergy","ts":1645123620,"mac":"000D6F0002588E41","power":0.0000,"energy":0.0000,"cum_energy":23816.2021,"interval":1}
    query = f"energyv3,quantity=electricity,type=consumption,uniqueid={thisuniqueid},source={thissource} value={thisenergy} {thisdate}"

    my_logger.debug(query)
    r = requests.post(INFLUX_WRITE_URI, data=query, timeout=10, auth=(INFLUX_USER, INFLUX_PASSWD))

def parse_esphome(msg):
    # msg.topic should be like 
    # influx/<measurement>/[<tagname>/<tagvalue>/]*<field>/state, which is 
    # converted into 
    # measurement,[tagname=tagvalue]* field=msg.payload

    msgarr = msg.topic.split("/")

    # Check topic has even number of fields
    if (len(msgarr) % 2 != 0):
        my_logger.warning("Malformed topic does not have even number of fields: {}".format(msg.topic))
        return

    # Check topic starts with 'influx' and ends with 'state'
    i_influx = msgarr.pop(0)
    i_state = msgarr.pop()
    if (i_state != 'state' or i_influx != 'influx'):
        my_logger.warning("Malformed topic not ending in 'state' or starting with 'influx': {}".format(msg.topic))
        return

    # Get measurement & field name
    i_meas = msgarr.pop(0)
    i_field = msgarr.pop()

    # Init query, check for any remaining tags
    query = "{}".format(i_meas)

    for tag_key, tag_val in zip(msgarr[::2], msgarr[1::2]):
        query += ",{}={}".format(tag_key, tag_val)

    # Check if payload is nan or empty, in which case we don't push as InfluxDB does not support nan/null.
    p = msg.payload.decode('utf-8')
    if p == 'nan' or p == '':
        my_logger.warning("Topic has nan or empty payload {}".format(msg.topic))
        return

    # Strip all non-numeric data
    p = re.sub("[^0-9.\-]","",p)

    query += " {}={}".format(i_field, float(p))

    my_logger.debug(query)
    r = requests.post(INFLUX_WRITE_URI, data=query, timeout=10, auth=(INFLUX_USER, INFLUX_PASSWD))


client = mqtt.Client()
client.username_pw_set(MQTT_CLIENT_USERNAME, MQTT_CLIENT_PASSWD)

client.on_connect = do_connect
client.on_message = parse_message

my_logger.info("Connecting to {}:1883".format(MQTT_SERVER_HOST))
client.connect(MQTT_SERVER_HOST, 1883, 60)

my_logger.info("Starting listen loop forever...")
client.loop_forever()

my_logger.warning("Listen loop stopped, this should not happen.")
