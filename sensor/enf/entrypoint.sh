#!/bin/bash

set -e

echo "Setting up enftun"
/usr/bin/enftun-setup up /etc/enftun/enf0.conf
/usr/bin/enftun -c /etc/enftun/enf0.conf &

exec python /sensor.py "$@"
