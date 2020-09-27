"""
This is the main program that does the work.
"""
from apscheduler.schedulers.blocking import BlockingScheduler
from transitions import Machine
from datetime import datetime, timedelta
import enum
import logging
import secrets
import os, sys
import yaml

from utils import set_log_level
from switchmate import SwitchMate, FakeSwitch

Switch = SwitchMate

class Light(enum.Enum):
    ON = 1
    OFF = 0
    BAT = 2
    UNKN = 3


class SwitchScheduler(Switch):
    """ this is a scheduler that controls scheduling of an underlying switch """
    def calc_time_from_loc_and_schedule(self, point, schedule):
        import ephem

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
        import secrets
        h,m,s = off_time_str.split(':')
        rand_minute = int(m) + secrets.randbelow(60 - int(m))
        now = datetime.now()
        off_time_adj = now.replace(hour=int(h), minute=rand_minute, second=int(s))
        return off_time_adj

    def _add_times_to_schedule(self, schedule):
        for event, val in schedule.items():
            if event == 'off_time':
                schedule[event]['time'] = self.rand_off_time(val['time'])
            else:
                schedule[event]['time'] = self.calc_time_from_loc_and_schedule(self.conf['home'], val)
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

        sched.print_jobs()


class LightMachine(Machine, SwitchScheduler):
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

        self.readconf(self.conf)

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
        verify_table = {'on': Light.ON,
                        'off': Light.OFF,
                        False: Light.UNKN}

        if self.mystery_state == Light.UNKN:
            status = self.status()

            if verify_table[status] == self.state:
                logging.info(f"status is ✅ {status} 💡")
                self.mystery_state =  verify_table[status]
            elif verify_table[status] == Light.UNKN:
                logging.info("status is ❓")
                self.mystery_state =  Light.UNKN
            elif verify_table[status] != self.state:
                logging.info("status is 🚫 toggling 💡")
                self.toggle()
                self.mystery_state =  Light.UNKN
        else:
            logging.info("✅ status correct. quieting log messages")
            set_log_level(logging.WARNING)


if __name__ == "__main__":
    dir_path = os.path.dirname(os.path.realpath(__file__))
    with open (f"{dir_path}/conf.yaml") as f:
        conf = yaml.load(f, Loader=yaml.FullLoader)

    logging.basicConfig(level=logging.INFO,
                        filename=conf['logfile']
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

    # determine if I need to start a scheduler earlier than normal
    now = datetime.now()
    sched_hour,sched_minute = conf['sched_time'].split(':')
    if now < off_time_in_utc(conf['off_time'], conf['local_tz']) or now > now.replace(hour=int(sched_hour), minute=int(sched_minute)):
        logging.info("sched_time < now < off_time gonna add a scheduler 📆 in 2️⃣")
        sched.add_job(lm.scheduler, 'date', run_date=(now+timedelta(minutes=2)), args=[sched])

    logging.info(f"start BlockingScheduler()")
    sched.start()
