import logging
import yaml
from datetime import datetime, timedelta

"""
def set_log_level(level):
    logger = logging.getLogger()
    logger.setLevel(level)
"""
def set_log_level(log_level):
    """ the purpose of this function is to do nothing bc
        setting log_level is causing confusion sa I debug """
    return

def load_conf(config):
    with open (config) as f: 
        conf = yaml.load(f, yaml.FullLoader)
    return conf

def info_jobs(jobs):
    ret = '\n'
    for j in jobs:
        ret += f"👷 JOB: {j.name} 📆 {j.next_run_time.ctime()}\n"
    return ret

def synth_off_time(off_time_str):
    now = datetime.now()
    h,m,s = off_time_str.split(':')
    return now.replace(hour=int(h), minute=int(m), second=int(s))

def synth_sched_time(sched_time_str):
    now = datetime.now()
    h,m = sched_time_str.split(':')
    sched_time = now.replace(hour=int(h), minute=int(m))
    if sched_time > now:
        return sched_time
    else:
        return sched_time + timedelta(hours=24)
