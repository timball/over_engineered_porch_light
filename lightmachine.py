"""
This is the main program that does the work.
"""
from apscheduler.schedulers.blocking import BlockingScheduler
from transitions import Machine
from datetime import datetime, timedelta
import ephem
import enum
import logging
import secrets
import os, sys
import yaml

from utils import set_log_level, load_conf, info_jobs, synth_off_time, synth_sched_time
from switchmate import SwitchMate


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
        self.obs = ephem.Observer()
        self.obs.lat = point['lat']
        self.obs.lon = point['lon']
        self.obs.elev = point['elev']
        self.point = point

    def calc_time_from_loc_and_schedule(self, schedule):
        point = self.conf['home']

        today = datetime.now()

        self.obs.date = today.replace(hour=12, minute=0, second=0)

        self.obs.horizon = str(schedule['horizon'])
        if schedule['when'] == "morning":
            utc_time = self.obs.previous_rising(ephem.Sun())
        elif schedule['when'] == "evening":
            utc_time = self.obs.next_setting(ephem.Sun())
        else:
            raise NameError("no idea when you want to calculate")
        time = ephem.localtime(utc_time)
        return time

    def rand_off_time(self, off_time_str):
        import secrets

        h,m,s = off_time_str.split(':')
        rand_minute = int(m) + secrets.randbelow(60 - int(m))

        now = datetime.now()
        off_time_adj = now.replace(hour=int(h), minute=rand_minute, second=int(s))

        return off_time_adj

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
        logging.info(sched.get_jobs())

class LightMachine(Machine, SwitchScheduler, SwitchMate):
    """ test a light switch with a random flipper """

    def __init__(self, conf):
        self.conf = conf
        self.mystery_state = Light.UNKN
        states = [Light.ON, Light.OFF, Light.BAT]

        t = self._add_times_to_schedule(self.conf['schedule'])
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
        logging.warning(f"status: {self.state}")
        two_mins = datetime.now() + timedelta(minutes=2)
        sched.add_job(lm.verify_state, 'date', run_date=two_mins)

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

    logging.basicConfig(level=logging.INFO,
                        filename=conf['logfile'],
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                        datefmt='%m-%d %H:%M')

    logging.info(f"making LightMachine()")
    lm = LightMachine(conf)

    logging.info(f"making BlockingScheduler()")
    sched = BlockingScheduler(daemon=True)

    logging.info(f"adding scheduler cron 🕙")
    # debug sched_time can be ':*/2' to fire every two minutes
    hour, minute = conf['sched_time'].split(':')
    if hour == '':
        hour = None

    sched.add_job(lm.scheduler, 'cron', hour=hour, minute=minute, args=[sched])
    sched.add_job(lm.verify_state, 'cron', minute=conf['verify_cron'])

    # determine if a one off scheduler is needed
    now = datetime.now()
    off_time = synth_off_time(conf['schedule']['off_time']['off_hour'])
    sched_time = synth_sched_time(conf['sched_time'])

    if now < off_time or now > sched_time:
        logging.info("sched_time < now < off_time gonna add a scheduler 📆 in 2️⃣")
        sched.add_job(lm.scheduler, 'date', run_date=(now+timedelta(minutes=2)), args=[sched])

    logging.info(f"start BlockingScheduler()")
    sched.start()
