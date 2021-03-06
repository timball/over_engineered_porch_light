"""
SwitchMate python class based on https://github.com/brianpeiris/switchmate
tested on python 3.7.3
MIT License
Sun 13 Sep 16:41:07 BST 2020
--timball
"""

import sys, os, logging
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


class SwitchMate:
    """ this is a class to do things w/ the switchmate """
    def __init__(self, conf):
        if os.geteuid() != 0:
            logging.warning(f"Not root! Won't attempt to elevate()")
            #elevate()
        self.mac_addr = conf['mac_addr']
        self.timeout = conf['timeout']


    def __del__(self):
        logging.info(f"disconnecting device")
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
        except btle.BTLEException as ex:
            if 'failed to connect' in ex.message.lower():
                logging.error(f"ERROR: Failed to connect to device: {ex.message}")
                success = False
            else:
                logging.error(f"ERROR: {ex.message}")
                success = False
        except btle.BTLEInternalError as ex:
            logging.error(f"Internal Bt error ... likely need to restart bluetooth")
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
        return self._activate_switch("ON")

    def switchoff(self):
        logging.debug(f"switchon()")
        return self._activate_switch("OFF")

    def _activate_switch(self, state):
        logging.info(f"💡 {state}")
        ret = None
        if self._connect():
            ret = self._switch(SW_STATE[state])
        else:
            ret = False
        return ret


    def __repr__(self):
        return f"SwitchMate: mac_addr: {self.mac_addr} timeout: {self.timeout}"


    def scan(self):
        self.scanner = btle.Scanner()
        try:
            self.scan_entries = self.scanner.scan(self.timeout)
        except btle.BTLEException as ex:
            logging.warn(f"can't scanner.scan()... be sure to sudo: {ex.message}")
            success = False
        except btle.BTLEInternalError as ex:
            logging.error(f"Internal Bt error ... likely need to restart bluetooth")
            success = False

        try:
            self.switchmates = self._get_switchmates(self.scan_entries)
        # maybe the exceptions should be in _get_switchmates()
        except btle.BTLException as ex:
            logging.warn(f"can't get_switchmates()... Bt might be terrible: {ex.message}")
            success = False
        except btle.BTLEInternalError as ex:
            logging.error(f"Internal Bt error ... likely need to restart bluetooth")
            success = False
        except OSError as ex:
            logging.error(f"Error! Can't complete scan: {ex}")
            success = False
        if len(self.switchmates):
            logging.info(f"Found SwitchMate!")
            for switchmate in self.switchmates:
                logging.info(f"{switchmate.addr}")
            success = True
        else:
            logging.warn(f"SwitchMate.scan() found no devices!")
            success = True
        return success


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
    import yaml
    import getopt

    logging.basicConfig(level=logging.INFO)
    conf = dict()
    config = None
    timeout = None
    mac_addr = None

    def _print_help():
        print (f"Usage: {sys.argv[0]} option")
        print (f"{sys.argv[0]} [-t|--timeout=seconds] [-c|--conf=config] [-m|--mac_addr=mac_addr] [-h|--help] <scan|status|battery|toggle|on|off|debug>")

    try:
        opts, args = getopt.getopt(sys.argv[1:], "ht:m:c:", ["timeout=", "mac_addr=", "conf="])
    except getopt.GetoptError:
        _print_help()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            _print_help()
            sys.exit(2)
        elif opt in ('-t', '--timeout'):
            timeout = arg
        elif opt in ('-m', '--mac_addr'):
            mac_addr = arg
        elif opt in ('-c', '--conf'):
            config = arg

    if config:
        with open(config) as f:
            conf = yaml.load(f, Loader=yaml.FullLoader)
    if timeout is not None:
        conf['timeout'] = timeout
    if mac_addr is not None:
        conf['mac_addr'] = mac_addr

    if config is None:
        _print_help()
        sys.exit(2)

    if len(args) != 1:
        _print_help()
        sys.exit(1)
    else:
        sm = SwitchMate()
        sm.readconf(conf)
        logging.debug(sm)

        if   args[0] == "scan":
            logging.debug("scan")
            sm.scan()
        elif args[0] == "status":
            logging.debug("status")
            print(sm.status())
        elif args[0] == "battery":
            logging.debug("battery")
            print(sm.batterystatus())
        elif args[0] == "toggle":
            logging.debug("toggle")
            print(sm.toggle())
        elif args[0] == "on":
            logging.debug("on")
            print(sm.switchon())
        elif args[0] == "off":
            logging.debug("off")
            print(sm.switchoff())
        elif args[0] == "debug":
            logging.debug("debug")
            sm.debug()
        else:
            logging.debug("default help")
            _print_help()
            sys.exit(2)
