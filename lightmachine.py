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

from horizons_to_times import horizons_to_times, off_time_in_utc
from utils import set_log_level
from switchmate import SwitchMate, FakeSwitch

Switch = None
# either use FakeSwitch or SwitchMate depending on conf['debug']
with open ('conf.yaml') as f:
    conf = yaml.load(f, Loader=yaml.FullLoader)

if conf['debug'] == True:
    print(f"debug set")
    Switch = FakeSwitch
    logging.basicConfig(level=logging.INFO)
else:
    print(f"debug NOT set")
    Switch = SwitchMate
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                        datefmt='%m-%d %H:%M')

class Light(enum.Enum):
    ON = 1
    OFF = 0
    BAT = 2
    UNKN = 3


class SwitchScheduler(Switch):
    """ this is a switch that controls scheduling of an underlying switch """
    def gen_fake_schedule(self, conf):
        """ we don't use conf ... just self.conf but for consistancy sake """
        import pytz

        timez = dict()

        now = datetime.now()
        local_tz = pytz.timezone(self.conf['local_tz'])

        counter = 0
        for key in self.conf['horizons']:
            rand_time = self.conf['TEST_RAND_PAD'] + secrets.randbelow (self.conf['TEST_MAX_RAND'] - self.conf['TEST_RAND_PAD'])

            timez[key] = dict()
            timez[key]['horizon'] = self.conf['horizons'][key]
            timez[key]['utc'] = now + timedelta(seconds=(rand_time+counter))
            timez[key]['local'] = now.astimezone(local_tz)
            counter += rand_time
            print(f"counter: {counter}")

        timez['off_time'] = dict()
        timez['off_time']['horizon'] = '🌃'
        timez['off_time']['utc'] = now + timedelta(seconds=110)
        timez['off_time']['local'] = now.astimezone(local_tz)

        return timez


    def scheduler(self, sched):
        print(f"scheduler() {self.batterystatus()}")
        if conf['debug'] == True:
            timez = self.gen_fake_schedule(self.conf)
        else:
            timez = horizons_to_times(self.conf)

        now = datetime.now()

        if timez['morn_twil']['utc'] > now:
            sched.add_job(self.switchon,  'date', run_date=timez['morn_twil']['utc'])
            logging.info(f"🌅 morn_twil: {timez['morn_twil']['local']}")
        if timez['post_sunl']['utc'] > now:
            sched.add_job(self.switchoff, 'date', run_date=timez['post_sunl']['utc'])
            logging.info(f"🌇 post_sunl: {timez['post_sunl']['local']}")
        if timez['aft_twil']['utc'] > now:
            sched.add_job(self.switchon,  'date', run_date=timez['aft_twil']['utc'])
            logging.info(f"🌆 aft_twil: {timez['aft_twil']['local']}")
        if timez['off_time']['utc'] > now:
            sched.add_job(self.switchoff, 'date', run_date=timez['off_time']['utc'])
            logging.info(f"🌃 off_time: {timez['off_time']['local']}")

        sched.print_jobs()


class LightMachine(Machine, SwitchScheduler):
    """ test a light switch with a random flipper """

    def __init__(self, conf):
        self.conf = conf
        self.mystery_state = Light.UNKN

        states = [Light.ON, Light.OFF, Light.BAT]

        t = horizons_to_times(self.conf)
        now = datetime.utcnow()
        if (t['morn_twil']['utc'] < now or now < t['post_sunl']['utc']) or (t['aft_twil'] < now or now < t['off_time']['utc']):
            initial_state = Light.ON
        else:
            initial_state = Light.OFF
        Machine.__init__(self, states=states, initial=initial_state)

        self.readconf(self.conf)

        self.add_transition('on', Light.OFF, Light.ON, before='switchon', after='check_status')
        self.add_transition('off', Light.ON, Light.OFF, before='switchoff', after='check_status')


    def check_status(self):
        self.mystery_state = Light.UNKN
        logging.warning(f"status: {self.state}")
        two_mins = datetime.now() + timedelta(minutes=2)
        sched.add_job(lm.verify_state, 'date', run_date=two_mins)
        set_log_level(logging.WARNING)

    def verify_state(self):
        logging.info("verify_state()")
        ret = None
        verify_table = {'on': Light.ON,
                        'off': Light.OFF,
                        False: Light.UNKN}

        if self.mystery_state == Light.UNKN:
            status = self.status()

            if verify_table[status] == self.state:
                logging.info(f"status is ✅ {status} 💡")
                self.mystery_state =  verify_table[status]
                ret = True
            elif verify_table[status] == Light.UNKN:
                logging.info("status is ❓")
                self.mystery_state =  Light.UNKN
                ret = False
            elif verify_table[status] != self.state:
                logging.info("status is 🚫 toggling 💡")
                self.toggle()
                self.mystery_state =  Light.UNKN
                ret = True
        else:
            ret = True
        # send back the ret value either True or False based on the state of the light
        return ret


if __name__ == "__main__":

    logging.info(f"making LightMachine()")
    lm = LightMachine(conf)

    logging.info(f"making BlockingScheduler()")
    sched = BlockingScheduler(daemon=True)

    # if now is after off_time
    logging.info(f"adding scheduler cron 🕙")
    if conf['debug']:
        # fire a little more often bc we're debugging
        sched.add_job(lm.scheduler, 'cron', minute='*/2', args=[sched])
    else:
        hour, minute = conf['sched_time'].split(':')
        sched.add_job(lm.scheduler, 'cron', hour=hour, minute=minute, args=[sched])
        sched.add_job(lm.verify_state, 'cron', minute=conf['verify_cron'])

    now = datetime.now()
    sched_hour,sched_minute = conf['sched_time'].split(':')
    if now < off_time_in_utc(conf['off_time'], conf['local_tz']) or now > now.replace(hour=int(sched_hour), minute=int(sched_minute)):
        logging.info("sched_time < now < off_time gonna schedule 📆 a run ️🏃 in 2️⃣")
        sched.add_job(lm.scheduler, 'date', run_date=(now+timedelta(minutes=2)), args=[sched])

    logging.info(f"start BlockingScheduler()")
    sched.start()
