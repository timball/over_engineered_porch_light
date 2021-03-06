# over_engineered_porch_light
##### Sat Sep 19 15:42:49 EDT 2020

This is some code to run a [bluetooth switchmate light
switch](https://www.mysimplysmarthome.com/products/smart-switches/). My
use case is for an annoying front porch light that is not connected to a
breaker so it can't simply be wired to a smart switch.

The code in switchmate.py is based on
https://github.com/brianpeiris/switchmate. I refactored the code to be a
python object. Also it no longer relies on sudo (at least on my raspberrypi). He
licensed his MIT so I'm doing the same.

horizons_to_times.py uses [pyephem](https://rhodesmill.org/pyephem/) to figure out when to
turn on the light based on local sunrise and sunset. I mostly guessed at
the horizon angles that made sense and put those values into conf.yaml-example

lightmachine.py uses [apscheduler](https://github.com/agronholm/apscheduler) to
flexibly schedule execution times. 
[transitions](https://github.com/pytransitions/transitions) manages
the state machine that is a light switch. To be clear the states are 
"Light.ON", "Light.OFF", and "Light.UNKN".

Because Bt is annoying, every few minutes there has to be a check to
verify the switch is in the right state. I could have been smarter about
how this check worked but Bt is annoying and unreliable.

Some assumptions: 
- raspberry pi configured with bluetooth
- raspberry pi time synced w/ ntpd or similiar
- raspberry pi timezone set to UTC
- switchmate mac addr set in conf.yaml 
    `python ./switchmate.py` can be used to scan for nearby switchmate switches

## Usage
```
$ virtualenv -p python3 virt 
$ source virt/bin/activate
$ pip install -r requirements.txt
$ cp conf.yaml-example conf.yaml
$ edit conf.yaml 
$ python ./lightmachine.py
```

At somepoint would like to put https://www.cleardarksky.com/c/USNOkey.html or 
api.weather.com data into this to turn a light on based on darkness in the sky.

--timball

