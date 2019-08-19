# mqtt2influxdb - very simple mqtt to influxdb pusher

Some IoT devices have mqtt pushers but not http pushers, I use this script to
bridge that gap.

The script listens to all 'influx/#' topic the broker has. Influxdb 
measurement ('table' in SQL lingo) and field ('column') can be encoded in the
topic, like

    influx/<measurement>/<field_name>/state

e.g.

    influx/environv2/pm25/state

# Sources

1. https://dzone.com/articles/playing-with-docker-mqtt-grafana-influxdb-python-a
2. https://github.com/gonzalo123/iot.grafana/blob/master/client.py
3. https://github.com/Nilhcem/home-monitoring-grafana
4. https://thingsmatic.com/2017/03/02/influxdb-and-grafana-for-sensor-time-series/
5. https://pypi.org/project/paho-mqtt/