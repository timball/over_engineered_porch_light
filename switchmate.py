"""
SwitchMate python class based on https://github.com/brianpeiris/switchmate
tested on python 3.7.3
MIT License
Sun 13 Sep 16:41:07 BST 2020
--timball
"""

import sys, os, logging
#from elevate import elevate
import bluepy.btle as btle
import enum

# firmware == 2.99.15 (or higher?)
SWITCHMATE_SERVICE = 'a22bd383-ebdd-49ac-b2e7-40eb55f5d0ab'
ORIGINAL_STATE_HANDLE = 0x2e
BRIGHT_STATE_HANDLE = 0x30
ORIGINAL_MODEL_STRING_HANDLE = 0x14
SERVICES_AD_TYPE = 0x07
MANUFACTURER_DATA_AD_TYPE = 0xff

SW_STATE = { "TOGGLE": None,
             "OFF": b'\x00',
             "ON": b'\x01'}

class FakeSwitch:
    """ this is a bunk switch """

    def readconf(self, conf):
        self.conf = conf
        self.state = 'off'

    def switchon(self):
        print(f"💡 ON")
        self.state = 'on'


    def switchoff(self):
        print(f"💡 OFF")
        self.state = 'off'

    def batterystatus(self):
        print(f"🔋 battery status")

    def status(self):
        print(f"status: {self.state}")
        return self.state


class SwitchMate:
    """ this is a class to do things w/ the switchmate """
    def readconf(self, conf):
        """ this isn't an __init__() bc of weirdo problems I had w/ inheritance """
        if os.geteuid() != 0:
            logging.warning(f"WARN: not root. Won't attempt to elevate()")
            #elevate()
        self.mac_addr = conf['mac_addr']
        self.timeout = conf['timeout']


    def __del__(self):
        self._disconnect()


    def batterystatus(self):
        ret = self._battery_level()
        if ret:
            logging.info(ret)
        else:
            ret = False
        return ret


    def _battery_level(self):
        battery_level = btle.AssignedNumbers.batteryLevel
        try:
            self._connect()
            level = self.device.getCharacteristics(uuid=battery_level)[0].read()
        except btle.BTLEException as ex:
            logging.error(f"ERROR: _battery_level: {ex.message}")
            return False
        except:
            e = sys.exc_info()[0]
            logging.error(f"ERROR: _battery_level: {e}")
            return False
        return ('🔋 Battery level: {}%'.format(ord(level)))


    def _connect(self):
        """ XXX maybe you don't have to reconnect if you already have a device ? should test this also maybe we should make a _disconnect() ... nope fucking Bt is garbage """
        logging.debug(f"connect")

        success = None
        self.device = None
        logging.info(f"mac: {self.mac_addr}")
        try:
            self.device = btle.Peripheral(self.mac_addr, btle.ADDR_TYPE_RANDOM)
        except btle.BTLEInternalError as ex:
            logging.error(f"Internal Bt error ... likely need to restart bluetooth")
            success = False
        except btle.BTLEException as ex:
            if 'failed to connect' in ex.message.lower():
                logging.error(f"ERROR: Failed to connect to device: {ex.message}")
                success = False
            else:
                logging.error(f"ERROR: {ex.message}")
                success = False
        except OSError as ex:
            logging.error(f"ERROR: OS Failure {ex}")
            success = False
        if self.device:
            logging.info(f"connect success")
            success = True
        else:
            logging.error(f"ERROR: bad things happend in SwitchMate.connect() probably need to restart the bluetooth device")
            success = False
        return success


    def debug(self):
        """ This is unchanged from brian's code """
        from tabulate import tabulate
        logging.debug("start debug() 🕷🕷")

        self._connect()
        output = [['uuid', 'common name', 'handle', 'properties', 'value']]
        for char in self.device.getCharacteristics():
            if char.supportsRead():
                val = char.read()
                binary = False
                for c in val:
                    if get_byte(c) < 32 or get_byte(c) > 126:
                        binary = True
                if binary:
                    val = hexlify(val)
            output.append([
                str(char.uuid),
                UUID(char.uuid).getCommonName(),
                '{0:x}'.format(char.getHandle()),
                char.propertiesToString(),
                str(val)
            ])
        print(tabulate(output, headers='firstrow'))

    def _disconnect(self):
        if hasattr(self, 'device') and self.device is not None:
            self.device.disconnect()

    def get_byte(self, x):
        return x

    def _get_state_handle(self, device):
        if self.is_original_device(device):
            return ORIGINAL_STATE_HANDLE
        else:
            return BRIGHT_STATE_HANDLE

    def _get_switchmates(self, scan_entries):
        switchmates = []
        for scan_entry in scan_entries:
            service_uuid = scan_entry.getValueText(SERVICES_AD_TYPE)
            is_switchmate = service_uuid == SWITCHMATE_SERVICE
            if not is_switchmate:
                continue
            if scan_entry not in switchmates:
                switchmates.append(scan_entry)
        switchmates.sort(key=lambda sw: sw.addr)
        logging.info(f"switchmates: {switchmates[0]}")
        return switchmates


    def is_original_device(self, device):
        # The handle for reading the model string on Bright devices is actually
        # different from Original devices, but using getCharacteristics to read
        # the model is much slower.
        model = device.readCharacteristic(ORIGINAL_MODEL_STRING_HANDLE)
        return model == b'Original'


    def switchon(self):
        logging.debug(f"switchon()")
        logging.info(f"💡 ON")
        ret = None
        if self._connect():
            ret = self._switch(SW_STATE['ON'])
        else:
            ret = False
        return ret


    def switchoff(self):
        logging.debug(f"switchoff()")
        logging.info(f"💡 OFF")
        ret = None
        if self._connect():
            ret = self._switch(SW_STATE['OFF'])
        else:
            ret = False
        return ret


    def __repr__(self):
        return f"conf: {self.mac_addr} {self.status()}"


    def scan(self):
        self.scanner = btle.Scanner()
        try:
            self.scan_entries = self.scanner.scan(self.timeout)
        except btle.BTLEException as ex:
            logging.warn(f"can't scanner.scan()... be sure to sudo: {ex.message}")
            return

        try:
            self.switchmates = self._get_switchmates(self.scan_entries)
        except btle.BTLException as ex:
            logging.warn(f"can't get_switchmates()... be sure to sudo: {ex.message}")
            return
        except OSError as ex:
            logging.error(f"Error! Can't complete scan: {ex}")
            return
        if len(self.switchmates):
            logging.info(f"Found SwitchMate!")
            for switchmate in self.switchmates:
                logging.info(f"{switchmate.addr}")
        else:
            logging.warn(f"SwitchMate.scan() found no devices!")


    def status(self):
        if self._connect():
            state_handle = self._get_state_handle(self.device)
            try:
                curr_val = self.device.readCharacteristic(state_handle)
            except btle.BTLEInternalError as ex:
                logging.error(f"Internal Bt error ... likely need to restart bluetooth")
                success = False
            if curr_val == SW_STATE['OFF']:
                return "off"
            elif curr_val == SW_STATE['ON']:
                return "on"
            else:
                logging.error("could connnect but didn't get readCharacteristics")
                return False
        else:
            return False


    def _switch(self, state):
        success = None
        state_handle = self._get_state_handle(self.device)
        try:
            curr_val = self.device.readCharacteristic(state_handle)
        except btle.BTLEInternalError as ex:
            logging.error(f"Internal Bt error ... likely need to restart bluetooth")
            success = False
        if state is SW_STATE['TOGGLE']:
            state = SW_STATE['ON'] if curr_val == SW_STATE['OFF'] else SW_STATE['OFF']
        val_num = self.get_byte(state[0])
        val_text = ('off', 'on')[val_num]
        if curr_val != state:
            self.device.writeCharacteristic(state_handle, state, True)
            logging.info('Switched {}!'.format(val_text))
            success = True
        else:
            logging.info('Already {}!'.format(val_text))
            success = False
        return success


    def toggle(self):
        logging.debug(f"toggle")
        ret = None
        if self._connect():
            ret = self._switch(SW_STATE['TOGGLE'])
        else:
            ret = False
        return ret


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    import yaml

    conf = "conf.yaml"
    with open(conf) as f:
        conf = yaml.load(f, Loader=yaml.FullLoader)

    sm = SwitchMate()
    sm.readconf(conf)
    print(f"sw: {sm}")
    #sm.scan()
    sm.status()
    #sm.batterystatus()
    #sm.toggle()
    #sm.switchon()
    #sm.switchoff()
    #sm.debug()
