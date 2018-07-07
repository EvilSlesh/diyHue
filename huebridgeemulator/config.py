from collections import defaultdict
import copy
from huebridgeemulator.tools import getIpAddress
from uuid import getnode as get_mac
from datetime import datetime
import json
import sys

import yaml

from huebridgeemulator.device.light import LightState
from huebridgeemulator.device.yeelight.light import YeelightLight, YeelightLightAddress
from huebridgeemulator.device.hue.light import HueLight
from huebridgeemulator.scene import Scene

RESOURCE_TYPES = [
  "alarm_config",
  "capabilities",
  "config",
  "deconz",
  "groups",
  "lights",
  "lights_address",
  "linkbutton",
  "resourcelinks",
  "rules",
  "scenes",
  "schedules",
  "sensors"
]


def loadConfig(filename):  #load and configure alarm virtual light
    #load config files
    try:
        with open(filename, 'r') as fp:
            bridge_config = json.load(fp)
            print("Config loaded")
    except Exception as exp:
        print("CRITICAL! Config file was not loaded: %s" % exp)
        sys.exit(1)

    # Move this
    if bridge_config["alarm_config"]["mail_username"] != "":
        print("E-mail account configured")
        if "virtual_light" not in bridge_config["alarm_config"]:
            print("Send test email")
            if sendEmail("dummy test"):
                print("Mail succesfully sent\nCreate alarm virtual light")
                new_light_id = nextFreeId("lights")
                bridge_config["lights"][new_light_id] = {"state": {"on": False, "bri": 200, "hue": 0, "sat": 0, "xy": [0.690456, 0.295907], "ct": 461, "alert": "none", "effect": "none", "colormode": "xy", "reachable": True}, "type": "Extended color light", "name": "Alarm", "uniqueid": "1234567ffffff", "modelid": "LLC012", "swversion": "66009461"}
                bridge_config["alarm_config"]["virtual_light"] = new_light_id
            else:
                print("Mail test failed")
    # end move this

    return bridge_config

def saveConfig(filename, bridge_config):
    with open(filename, 'w') as fp:
        json.dump(bridge_config, fp, sort_keys=True, indent=4, separators=(',', ': '))


class Config(object):
    """Configuration class."""

    def __init__(self, filepath=None):
        self.filepath = filepath
        # TODO: is this useless ?
        self.bridge = defaultdict(lambda:defaultdict(str))
        self._mac = '%012x' % get_mac()
        # lights registry
        self.lights = {}
        # scenes registry
        self.scenes = {}
        # groups registry
        self.groups = {}
        # just added lights
        self._new_lights = {}
        # Load from file
        if filepath is not None:
            self.load()
            self._startup()

    def _startup(self):
        ip_pices = getIpAddress().split(".")
        self.bridge["config"]["ipaddress"] = getIpAddress()
        self.bridge["config"]["gateway"] = ip_pices[0] + "." +  ip_pices[1] + "." + ip_pices[2] + ".1"
        self.bridge["config"]["mac"] = self._mac[0] + self._mac[1] + ":" + self._mac[2] + self._mac[3] + ":" + self._mac[4] + self._mac[5] + ":" + self._mac[6] + self._mac[7] + ":" + self._mac[8] + self._mac[9] + ":" + self._mac[10] + self._mac[11]
        self.bridge["config"]["bridgeid"] = (self._mac[:6] + 'FFFE' + self._mac[6:]).upper()

    def set_filepath(self, filepath):
        self.filepath = filepath
        # Load from file
        if filepath is not None:
            self.load()
            self._startup()

    def load(self):
        """Read configuration from file"""
        # TODO add yaml
        with open(self.filepath, 'r') as cfs:
            self.bridge = json.load(cfs)
            for index, light_address in self.bridge['lights_address'].items():
                light = self.bridge['lights'][index]
                if light_address['protocol'] == 'yeelight':
                    light['state'] = LightState(light['state'])
                    light['address'] = YeelightLightAddress(light_address)
                    new_light = YeelightLight(light)
                    self.lights[index] = new_light
                elif light_address['protocol'] == 'hue':
                    new_light = HueLight(index=index, address=light_address, raw=light)
                    self.lights[index] = new_light
            for index, scene in self.bridge['scenes'].items():
                self.scenes[index] = Scene(scene)

    def save(self):
        """Write configuration to file."""
        output = copy.copy(self.bridge)
        for index in output['lights'].keys():
            if 'address' in output['lights'][index]:
                del(output['lights'][index]['address'])
            output['lights'][index]['state'] = output['lights'][index]['state'].serialize()
        with open(self.filepath, 'w') as cfs:
            json.dump(output, cfs, sort_keys=True, indent=4, separators=(',', ': '))

    def backup(self):
        """Backup configuration."""
        filepath = "{}-backup-{}.json".format(self.filepath,
                                              datetime.now().strftime("%Y-%m-%d"))
        with open(filepath, 'w') as cfs:
            json.dump(self.bridge, cfs, sort_keys=True, indent=4, separators=(',', ': '))

    def nextFreeId(self, element):
        i = 1
        while (str(i)) in self.bridge[element]:
            i += 1
        return str(i)

    def add_new_resource(self, resource):
        resource_type = resource._RESOURCE_TYPE
        if resource_type is None:
            raise
        getattr(self, resource_type)[resource.index] = resource
        if resource_type == "lights":
            self._new_lights.update({resource.index: {"name": resource.name}})
            self._new_lights.update({"lastscan": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")})

    def get_new_lights(self):
        return self._new_lights

    def clear_new_lights(self):
        self._new_lights.clear()

    def get_resource(self, type, index):
        """Get light from index"""
        if type not in ["scenes", "lights"]:
            raise Exception("Bad resources type {}".format(type))
        self.save()
        return getattr(self, type)[index]

    def get_lights(self):
        """Return all lights."""
        ret = {}
        for index, light in self.lights.items():
            ret[index] = light.serialize()
        return ret

    def get_json_lights(self):
        """Return all lights in JSON format."""
        return json.dumps(self.get_lights())


# Improve that
registry = Config()