import json
import socket

from huebridgeemulator.device.light import Light, LightState, LightAddress
from huebridgeemulator.tools.colors import convert_xy, convert_rgb_xy
# Should we use yeelight python lib ??

class YeelightLight(Light):

    _RESOURCE_TYPE = "lights"
    _MANDATORY_ATTRS = ('address', 'state', 'type', 'name', 'uniqueid',
                        'modelid', 'manufacturername', 'swversion')
    _OPTIONAL_ATTRS = ()

    def update_status(self):
        self.logger.debug(self.serialize())
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.settimeout(5)
        tcp_socket.connect((self.address.ip, int(55443)))
        msg = json.dumps({"id": 1, "method": "get_prop", "params":["power","bright"]}) + "\r\n"
        tcp_socket.send(msg.encode())
        data = tcp_socket.recv(16 * 1024)
        # TODO use  python yeelight lib wuth music mode ti workaround the connection limit
        light_data = json.loads(data[:-2].decode("utf8"))["result"]
        if light_data[0] == "on": #powerstate
            self.state.on = True
        else:
            self.state.on = False
        self.state.bri = int(int(light_data[1]) * 2.54)
        msg_mode=json.dumps({"id": 1, "method": "get_prop", "params":["color_mode"]}) + "\r\n"
        tcp_socket.send(msg_mode.encode())
        data = tcp_socket.recv(16 * 1024)
        if json.loads(data[:-2].decode("utf8"))["result"][0] == "1": #rgb mode
            msg_rgb=json.dumps({"id": 1, "method": "get_prop", "params":["rgb"]}) + "\r\n"
            tcp_socket.send(msg_rgb.encode())
            data = tcp_socket.recv(16 * 1024)
            hue_data = json.loads(data[:-2].decode("utf8"))["result"]
            hex_rgb = "%6x" % int(json.loads(data[:-2].decode("utf8"))["result"][0])
            r = hex_rgb[:2]
            if r == "  ":
                r = "00"
            g = hex_rgb[3:4]
            if g == "  ":
                g = "00"
            b = hex_rgb[-2:]
            if b == "  ":
                b = "00"
#            bridge_config["lights"][light]["state"]["xy"] = convert_rgb_xy(int(r,16), int(g,16), int(b,16))
            self.state.xy = convert_rgb_xy(int(r,16), int(g,16), int(b,16))
#            bridge_config["lights"][light]["state"]["colormode"] = "xy"
            self.state.colormode = "xy"
        elif json.loads(data[:-2].decode("utf8"))["result"][0] == "2": #ct mode
            msg_ct = json.dumps({"id": 1, "method": "get_prop", "params":["ct"]}) + "\r\n"
            tcp_socket.send(msg_ct.encode())
            data = tcp_socket.recv(16 * 1024)
#            bridge_config["lights"][light]["state"]["ct"] =  int(1000000 / int(json.loads(data[:-2].decode("utf8"))["result"][0]))
            self.state.ct =  int(1000000 / int(json.loads(data[:-2].decode("utf8"))["result"][0]))
#            bridge_config["lights"][light]["state"]["colormode"] = "ct"
            self.state.colormode = "ct"
        elif json.loads(data[:-2].decode("utf8"))["result"][0] == "3": #ct mode
            msg_hsv=json.dumps({"id": 1, "method": "get_prop", "params":["hue","sat"]}) + "\r\n"
            tcp_socket.send(msg_hsv.encode())
            data = tcp_socket.recv(16 * 1024)
            hue_data = json.loads(data[:-2].decode("utf8"))["result"]
            #bridge_config["lights"][light]["state"]["hue"] = int(hue_data[0] * 182)
            self.state.hue = int(hue_data[0] * 182)
            #bridge_config["lights"][light]["state"]["sat"] = int(int(hue_data[1]) * 2.54)
            self.state.sat = int(int(hue_data[1]) * 2.54)
            #bridge_config["lights"][light]["state"]["colormode"] = "hs"
            self.state.colormode = "hs"
        tcp_socket.close()
        self.logger.debug(self.serialize())
        return

    def send_request(self, data):
        payload = {}
        transitiontime = 400
        if "transitiontime" in data:
            transitiontime = data["transitiontime"] * 100
        for key, value in data.items():
            if key == "on":
                if value:
                    payload["set_power"] = ["on", "smooth", transitiontime]
                else:
                    payload["set_power"] = ["off", "smooth", transitiontime]
            elif key == "bri":
                payload["set_bright"] = [int(value / 2.55) + 1, "smooth", transitiontime]
            elif key == "ct":
                payload["set_ct_abx"] = [int(1000000 / value), "smooth", transitiontime]
            elif key == "hue":
                payload["set_hsv"] = [int(value / 182), int(self.state.sat / 2.54), "smooth", transitiontime]
            elif key == "sat":
                payload["set_hsv"] = [int(value / 2.54), int(self.state.hue / 2.54), "smooth", transitiontime]
            elif key == "xy":
                color = convert_xy(value[0], value[1], self.state.bri)
                payload["set_rgb"] = [(color[0] * 65536) + (color[1] * 256) + color[2], "smooth", transitiontime] #according to docs, yeelight needs this to set rgb. its r * 65536 + g * 256 + b
            elif key == "alert" and value != "none":
                payload["start_cf"] = [ 4, 0, "1000, 2, 5500, 100, 1000, 2, 5500, 1, 1000, 2, 5500, 100, 1000, 2, 5500, 1"]

        # yeelight uses different functions for each action, so it has to check for each function
        # see page 9 http://www.yeelight.com/download/Yeelight_Inter-Operation_Spec.pdf
        # check if hue wants to change brightness
        for api_method, param in payload.items():
            try:
                tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_socket.settimeout(5)
                tcp_socket.connect((self.address.ip, int(55443)))
                msg = json.dumps({"id": 1, "method": api_method, "params": param}) + "\r\n"
                tcp_socket.send(msg.encode())
                tcp_socket.close()
            except Exception as e:
                raise e
                print ("Unexpected error:", e)


class YeelightLightAddress(LightAddress):
    protocol = "yeelight"
    _MANDATORY_ATTRS = ('id', 'ip')