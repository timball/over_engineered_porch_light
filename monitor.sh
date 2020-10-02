#!/bin/bash
(while true
do
    echo ==============
    ps auxwww | grep lightmachine | grep -v grep
    grep -A 8 -E ' scheduler\(\).*level' porch_light.log | grep -v apscheduler | grep -A 8 -- --  | grep INFO
    grep -vE  'verify_state|quiet' porch_light.log  |  tail -n 4 | grep status
    #./python-memory-monitor.sh
    ps -eo size,pid,user,command --sort -size | awk '{ hr=$1/1024 ; printf("%13.2f Mb ",hr) } { for ( x=4 ; x<=NF ; x++ ) { printf("%s ",$x) } print "" }'  | grep python | grep -v grep
    ls -lah porch_light.log
     wc -l porch_light.log
    date
    sleep 600
done ) | tee -a mem_use.log
