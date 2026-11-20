#!/bin/bash
cd ~/guard
nohup timeout 3000 python3 run_guard.py --stream --verbose --log log_stream.csv > run_stream.log 2>&1 < /dev/null &
