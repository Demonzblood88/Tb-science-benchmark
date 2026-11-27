#!/bin/sh
set -eu
python /opt/task/opsd.py &
exec "$@"
