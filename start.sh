#!/bin/bash
#
# Startup script for a raspberry pi... Lazy man doesn't want to make 
# a proper startup script and will use crontab to start this on reboot
# @reboot /path/to/this/script

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PYTHON=${DIR}/../virt/bin/python

${PYTHON} ./lightmachine.py 2>&1 | tee -o ${DIR}/porch-light.log 