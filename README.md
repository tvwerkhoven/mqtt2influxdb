# mqtt2influxdb - very simple mqtt to influxdb pusher

Some IoT devices have mqtt pushers but not http pushers, I use this script to
bridge that gap.

The script listens to all 'influx/#' topic the broker has. Influxdb 
measurement ('table' in SQL lingo) and field ('column') can be encoded in the
topic, like

    influx/<measurement>/<field_name>/state

e.g.

    influx/environv2/pm25/state
