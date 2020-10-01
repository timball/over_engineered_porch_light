"""
This is the main program that does the work.
"""
from apscheduler.schedulers.blocking import BlockingScheduler
from transitions import Machine
from datetime import datetime, timedelta
import ephem
import enum
import logging
import logging.handlers
import secrets
import os, sys
import yaml

from utils import set_log_level, load_conf, info_jobs, synth_off_time, synth_sched_time
from switchmate import SwitchMate


# XXX maybe what I want is a frozen bidict
# or better SwitchMate.switchon() should return these instead of a str
class Light(enum.Enum):
    ON = 1
    OFF = 0
    BAT = 2
    UNKN = 3

VERIFY_TABLE = {'on': Light.ON,
                'off': Light.OFF,
                False: Light.UNKN}


class SwitchScheduler():
    """ this is a scheduler that controls scheduling of an underlying switch """
    def __init__(self, point=None):
        self.point = point

    def calc_time_from_loc_and_schedule(self, schedule):
        point = self.conf['home']
        obs = ephem.Observer()
        obs.lat = point['lat']
        obs.lon = point['lon']
        obs.elev = point['elev']

        today = datetime.now()

        obs.date = today.replace(hour=12, minute=0, second=0)

        obs.horizon = str(schedule['horizon'])
        if schedule['when'] == "morning":
            utc_time = obs.previous_rising(ephem.Sun())
        elif schedule['when'] == "evening":
            utc_time = obs.next_setting(ephem.Sun())
        else:
            raise NameError("no idea when you want to calculate")
        time = ephem.localtime(utc_time)
        return time

    def rand_off_time(self, off_time_str):
        h,m,s = off_time_str.split(':')
        rand_minute = int(m) + secrets.randbelow(60 - int(m))

        now = datetime.now()
        return now.replace(hour=int(h), minute=rand_minute, second=int(s))

    def _add_times_to_schedule(self, schedule):
        for event, val in schedule.items():
            if event == 'off_time':
                schedule[event]['time'] = self.rand_off_time(val['off_hour'])
            else:
                schedule[event]['time'] = self.calc_time_from_loc_and_schedule(val)
        return schedule

    def scheduler(self, sched):
        set_log_level(logging.INFO)
        logging.info(f"scheduler() {self.batterystatus()}")

        timez = self._add_times_to_schedule(self.conf['schedule'])
        now = datetime.now()

        for run in timez.keys():
            if timez[run]['time'] > now:
                if timez[run]['state']:
                    state = self.switchon
                else:
                    state = self.switchoff
                sched.add_job(state, 'date', run_date=timez[run]['time'])
                logging.info(f"{timez[run]['emoji']} {run}: {timez[run]['time']}")
        logging.info(info_jobs(sched.get_jobs()))


class LightMachine(Machine, SwitchScheduler, SwitchMate):
    """ test a light switch with a random flipper """

    def __init__(self, conf):
        self.conf = conf
        self.mystery_state = Light.UNKN
        states = [Light.ON, Light.OFF, Light.BAT]

        # XXX this causes a weirdo hole and indeterminite startup if run in the off_hour hour I guess, I don't super care as verify_state will catch things
        t = self._add_times_to_schedule(self.conf['schedule'])
        #logging.info(f"__init__ t: {t}") # to debug that weirdo hole
        now = datetime.now()
        if (t['morn_twil']['time'] < now and now < t['post_sunl']['time']) or (t['aft_twil']['time'] < now and now < t['off_time']['time']):
            initial_state = Light.ON
        else:
            initial_state = Light.OFF

        Machine.__init__(self, states=states, initial=initial_state)
        SwitchScheduler.__init__(self, point=self.conf['home'])
        SwitchMate.__init__(self, self.conf)

        self.add_transition('on', Light.OFF, Light.ON, before='on_state', after='check_state')
        self.add_transition('off', Light.ON, Light.OFF, before='off_state', after='check_state')

    def on_state(self):
        set_log_level(logging.INFO)
        self.switchon()

    def off_state(self):
        set_log_level(logging.INFO)
        self.switchoff()

    def check_state(self):
        self.mystery_state = Light.UNKN
        logging.info(f"check_state: {self.state}")
        two_mins = datetime.now() + timedelta(minutes=2)
        sched.add_job(self.verify_state, 'date', run_date=two_mins)

    def verify_state(self):
        logging.debug("verify_state()")
        if self.mystery_state == Light.UNKN:
            status = self.status()

            # XXX wouldn't need VERIFY_TABLE if status & self.state were the same type to verify against
            if VERIFY_TABLE[status] == self.state:
                logging.info(f"status is ✅ {status} 💡")
                self.mystery_state =  VERIFY_TABLE[status]
            elif VERIFY_TABLE[status] == Light.UNKN:
                logging.info("status is ❓")
                self.mystery_state =  Light.UNKN
            elif VERIFY_TABLE[status] != self.state:
                logging.info("status is 🚫 toggling 💡")
                self.toggle()
                self.mystery_state =  Light.UNKN
        else:
            logging.info("✅ status correct. quieting log messages")
            set_log_level(logging.WARNING) # XXX this might not be working ... just suck it up and accept the log messages ... could do this via apscheduler.job.pause() but that would require a dance


if __name__ == "__main__":
    dir_path = os.path.dirname(os.path.realpath(__file__))
    conf = load_conf(f"{dir_path}/conf.yaml")

    # create a logging handler that rotates at 3MB
    handler = logging.handlers.RotatingFileHandler(conf['logfile'],
                                                   backupCount=3,
                                                   maxBytes=3*1000*1000)
    logging.basicConfig(level=logging.INFO,
                        handlers=[handler],
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                        datefmt='%m-%d %H:%M')

    logging.info(f"making LightMachine()")
    lm = LightMachine(conf)

    logging.info(f"making BlockingScheduler()")
    sched = BlockingScheduler(daemon=True,
                              'apscheduler.executors.default': {
                                  'class': 'apscheduler.executors.pool:ThreadPoolExecutor',
                                  'max_workers': '3'},
                              'apscheduler.job_defaults.coalesce': 'true',
                              'apscheduler.job_defaults.max_instances': '3')

    logging.info(f"adding scheduler cron 🕙")
    hour, minute = conf['sched_time'].split(':')
    sched.add_job(lm.scheduler, 'cron', hour=hour, minute=minute, args=[sched])
    del hour, minute

    logging.info(f"add verify_state cron")
    sched.add_job(lm.verify_state, 'cron', minute=conf['verify_cron'])

    # determine if a one off scheduler is needed
    now = datetime.now()
    off_time = synth_off_time(conf['schedule']['off_time']['off_hour'])
    sched_time = synth_sched_time(conf['sched_time'])

    if (off_time < sched_time) and (sched_time < now or now < off_time):
        logging.info("📆 sched_time < now < off_time need to add scheduler in 2️⃣ min")
        sched.add_job(lm.scheduler, 'date', run_date=(now+timedelta(minutes=2)), args=[sched])
    del now, off_time, sched_time

    logging.info(f"start BlockingScheduler()")
    sched.start()
