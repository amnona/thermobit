#!/bin/bash

source activate thermobit
echo "running thermobit"
cd /home/pi/git/thermobit/thermobit
DEBUG=0 authbind gunicorn 'server:gunicorn(debug_level=4)' -b 0.0.0.0:80 --workers 1 --name=thermobit-server --reload
