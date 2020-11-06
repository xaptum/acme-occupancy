#!/bin/bash

set -e

docker run \
       --volume $(pwd)/enf0:/data/enf0 \
       -it \
       --entrypoint /usr/bin/enftun-keygen \
       sensor-enf $@

docker run --volume $(pwd)/enf0:/data/enf0 -it --entrypoint /usr/bin/enftun-keygen sensor-enf -c /etc/enftun/enf0.conf -u xap@test -a 2607:8f80:8080:c:1::1
