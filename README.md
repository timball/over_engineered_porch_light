# over_engineered_light_switch
##### Sat Sep 19 15:42:49 EDT 2020

This is some code to run a [bluetooth switchmate light
switch](https://www.mysimplysmarthome.com/products/smart-switches/). My
use case is for an annoying front porch light that is not connected to a
breaker so it can't simply be wired to a smart switch.

The code in switchmate.py is based on
https://github.com/brianpeiris/switchmate but I changed the code to be a
python object and not rely on sudo (at least on my raspberrypi). He
licensed his MIT so I'm doing the same.

It uses [pyephem](https://rhodesmill.org/pyephem/) to figure out when to
turn on the light based on local sunrise and sunset. I mostly guess at
the horizon angles that made sense.

It uses [apscheduler](https://github.com/agronholm/apscheduler) to be
schedule run times and
[transitions](https://github.com/pytransitions/transitions) to manage
the state machine that is a light switch. 

Because Bt is annoying, every few minutes there has to be a check to
verify the switch is in the right state. I could have been smarter about
how this check worked but Bt is annoying and unreliable.

## Usage
```
$ virtualenv -p python3 virt 
$ source virt/bin/activate
$ pip install -r requirements.txt
$ cp conf.yaml-example conf.yaml
$ edit conf.yaml 
$ python ./lightmachine.py
```

--timball
