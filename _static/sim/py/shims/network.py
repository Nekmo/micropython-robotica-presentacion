"""network shim for the simulator: WiFi always works instantly.

Real HTTP requests go through the browser (see the ``requests`` shim).
"""

from stackchan_sim import bridge as _bridge_mod

STA_IF = 0
AP_IF = 1
STAT_IDLE = 0
STAT_CONNECTING = 1
STAT_GOT_IP = 1010
STAT_WRONG_PASSWORD = 202
STAT_NO_AP_FOUND = 201
STAT_CONNECT_FAIL = 203
AUTH_OPEN = 0
AUTH_WPA_WPA2_PSK = 4


class WLAN:
    def __init__(self, interface=STA_IF):
        self._if = interface
        self._active = False
        self._ssid = None
        self._config = {"essid": "StackChan", "password": ""}

    def active(self, value=None):
        if value is None:
            return self._active
        self._active = bool(value)
        return self._active

    def connect(self, ssid=None, key=None, *args, **kwargs):
        self._ssid = ssid
        _bridge_mod.get().log("WiFi connected to %r (simulated)" % ssid)

    def disconnect(self):
        self._ssid = None

    def isconnected(self):
        return self._active and (self._if == AP_IF or self._ssid is not None)

    def status(self, *args):
        if args and args[0] == "rssi":
            return -50
        return STAT_GOT_IP if self.isconnected() else STAT_IDLE

    def ifconfig(self, *args):
        return ("192.168.4.1", "255.255.255.0", "192.168.4.1", "8.8.8.8")

    def ipconfig(self, *args, **kwargs):
        return "192.168.4.1"

    def scan(self):
        return [(b"PyConES", b"\x00" * 6, 1, -50, 3, 0)]

    def config(self, *args, **kwargs):
        if kwargs:
            self._config.update(kwargs)
            return None
        if args:
            return self._config.get(args[0])
        return None
