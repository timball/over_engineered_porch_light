"""
This file combines the twin pains of time zones AND astrological time.
Some of the code is bad in that it's making assumptions, other parts
are bad bc of poor coding practices. But it satisfies my bare minimum
requirements.

"""
from datetime import datetime, timedelta
import pytz
import ephem


def off_time_in_utc(offtime, local_tz):
    """
        utility function to convert clock time to a current utc time
        aka generic "10pm EDT" -> "now 2am the next day"
        input:
            offtime - string of form '22:00:00'
            local_tz - timzone string
        output:
            datetime of coverted offtime to utc
    """
    off_hour,off_minute,off_second = offtime.split(':')

    now = datetime.now()
    local = pytz.timezone(local_tz)
    utc = pytz.timezone("UTC")
    diff = (local.localize(now) - utc.localize(now)).seconds/3600.0

    ten_pm_adj = now.replace(hour=int(off_hour), minute=int(off_minute), second=int(off_second)) + timedelta(hours=diff)

    return ten_pm_adj - timedelta(hour=24)


def ephem_to_local(eph, tz):
    local_tz = pytz.timezone(tz)
    ret = eph.astimezone(local_tz)
    return ret.strftime("%c")


def offtime_local(morn_twil, conf):
    now = datetime.now()
    local = pytz.timezone(conf['local_tz'])
    utc = pytz.timezone("UTC")
    diff = (local.localize(now) - utc.localize(now)).seconds/3600.0

    # datetime timestamps (could have used datetime.replace() )
    ten_pm_utc_str = morn_twil.strftime(f"%Y-%m-%d {conf['off_time']}")
    ten_pm_utc = datetime.strptime(ten_pm_utc_str, "%Y-%m-%d %H:%M:%S")
    ten_pm_local = ten_pm_utc + timedelta(hours=diff)
    return ten_pm_local


def horizons_to_times(conf):
    from datetime import datetime

    timez = dict()
    # make an observer
    obs = ephem.Observer()

    # set the location
    obs.lat = conf['home']['lat']
    obs.lon = conf['home']['lon']
    obs.elev = conf['home']['elev']

    # set the utc time
    now = datetime.utcnow()
    obs.date = now.strftime("%Y-%m-%d 12:00:00")

    obs.horizon = str(conf['horizons']['morn_twil'])
    timez['morn_twil'] = dict()
    timez['morn_twil']['horizon'] = conf['horizons']['morn_twil']
    timez['morn_twil']['utc'] = ephem.localtime(obs.previous_rising(ephem.Sun(), use_center=True))
    timez['morn_twil']['local'] = ephem_to_local(timez['morn_twil']['utc'], conf['local_tz'])

    obs.horizon = str(conf['horizons']['post_sunl'])
    timez['post_sunl'] = dict()
    timez['post_sunl']['horizon'] = conf['horizons']['post_sunl']
    timez['post_sunl']['utc'] = ephem.localtime(obs.previous_rising(ephem.Sun(), use_center=True))
    timez['post_sunl']['local'] = ephem_to_local(timez['post_sunl']['utc'], conf['local_tz'])

    obs.horizon = str(conf['horizons']['aft_twil'])
    timez['aft_twil'] = dict()
    timez['aft_twil']['horizon'] = conf['horizons']['aft_twil']
    timez['aft_twil']['utc'] = ephem.localtime(obs.next_setting(ephem.Sun(), use_center=True))
    timez['aft_twil']['local'] = ephem_to_local(timez['aft_twil']['utc'], conf['local_tz'])

    off_hour,off_minute,off_second = conf['off_time'].split(':')
    ten_pm_adj = now.replace(hour=int(off_hour), minute=int(off_minute), second=int(off_second))

    timez['off_time'] = dict()
    timez['off_time']['horizon'] = '🌒'
    timez['off_time']['utc'] = offtime_local(timez['morn_twil']['utc'], conf)
    timez['off_time']['local'] = ten_pm_adj

    return timez


"""
import yaml
with open('conf.yaml') as f:
    conf = yaml.load(f, Loader=yaml.FullLoader)
#timez = horizons_to_times()
"""
