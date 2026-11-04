"""Device-side runtime of the in-browser simulator.

Adapted from esp-emulator's ``bridge.py``: same ``ServoModel`` and
``DeviceState`` written by the hardware shims, but instead of a socket
to a desktop GUI the simulator talks to the presentation through the
``simhost`` JavaScript module registered by the Web Worker:

* inputs (touch, head zones, IMU, light...) are read from shared memory
  with ``simhost.inputs()``;
* frames are written to the in-memory filesystem and announced with
  ``simhost.frame()``; state snapshots go out as JSON;
* ``tick()`` runs on every sleep and ``M5.update()``: it polls inputs,
  fires cooperative timers and streams frames/state (~30 fps).
"""

import array
import json

from . import compat
from .compat import monotonic

_bridge = None

FRAME_PATH = "/tmp/frame.rgb565"
AUDIO_PATH = "/tmp/audio.wav"
MIC_PATH = "/tmp/mic.pcm"
CAMERA_PATH = "/tmp/camera.rgb565"


def get():
    if _bridge is None:
        raise RuntimeError("Bridge not initialised (runner must create it)")
    return _bridge


class ServoModel:
    """Simulated SCS serial servo moving at finite speed toward a target."""

    _HW_TO_DEG_S = 1 / 3.2
    _DEFAULT_DEG_S = 200.0  # speed=0 means "max speed" on SCS servos

    def __init__(self, servo_id, initial=0.0, lo=0.0, hi=360.0):
        self.servo_id = servo_id
        self.lo, self.hi = lo, hi
        self._from = float(initial)
        self._target = float(initial)
        self._t_start = monotonic()
        self._deg_s = self._DEFAULT_DEG_S
        self.torque = False
        self.mode = 0  # 0=position, 1=pwm
        self.pwm = 0

    def set_target(self, angle_deg, time_ms=0, hw_speed=0):
        now = monotonic()
        self._from = self.current(now)
        self._target = max(self.lo, min(self.hi, float(angle_deg)))
        dist = abs(self._target - self._from)
        if hw_speed and hw_speed > 0:
            self._deg_s = max(1.0, hw_speed * self._HW_TO_DEG_S)
        elif time_ms and time_ms > 0 and dist > 0:
            self._deg_s = dist / (time_ms / 1000)
        else:
            self._deg_s = self._DEFAULT_DEG_S
        self._t_start = now

    def current(self, now=None):
        now = now if now is not None else monotonic()
        dist = self._target - self._from
        if dist == 0 or self._deg_s <= 0:
            return self._target
        travelled = (now - self._t_start) * self._deg_s
        if travelled >= abs(dist):
            return self._target
        return self._from + travelled * (1 if dist > 0 else -1)

    def moving(self):
        return abs(self.current() - self._target) > 0.01

    def force(self, angle_deg):
        angle = max(self.lo, min(self.hi, float(angle_deg)))
        self._from = self._target = angle
        self._t_start = monotonic()


class DeviceState:
    """All simulated hardware state, shared by the shims."""

    def __init__(self, board):
        self.lock = compat.RLock()
        self.board = board
        led_count = 12
        for comp in board.get("components", []):
            if comp.get("type") == "rgb_led":
                led_count = comp.get("count", 12)
        # inputs (refreshed from the presentation by Bridge.poll)
        self.buttons = {b: False for b in ("A", "B", "C", "PWR", "EXT")}
        self.touch_down = False
        self.touch_x = 0
        self.touch_y = 0
        self.head_touch = [False, False, False]
        self.accel = [0.0, 0.0, 1.0]
        self.gyro = [0.0, 0.0, 0.0]
        self.mag = [0.0, 0.0, 0.0]
        self.lux = 200.0
        self.prox = 0
        self.battery_level = 80
        self.charging = False
        self.mic_rate = 16000
        self.robot_ip = "192.168.4.1"
        self.wifi_sta = {"active": False, "ssid": None}
        self.wifi_ap = {"active": False, "ssid": "", "password": "",
                        "security": "open", "stations": 0}
        self.cpu_mhz = 0.0
        # outputs (written by shims, streamed to the presentation)
        self.leds = [(0, 0, 0)] * led_count
        self.led_brightness = 50
        self.servo_power = False
        self.servos = {
            1: ServoModel(1, initial=180.0, lo=0.0, hi=360.0),
            2: ServoModel(2, initial=45.0, lo=0.0, hi=90.0),
        }
        self.speaker_volume = 128
        self.speaker_until = 0.0
        self.speaker_freq = 0
        self.vibration = 0
        self.brightness = 200

    def snapshot(self):
        now = monotonic()
        return {
            "servo": {
                "power": self.servo_power,
                "x": round(self.servos[1].current(now), 1),
                "y": round(self.servos[2].current(now), 1),
                "moving": self.servos[1].moving() or self.servos[2].moving(),
            },
            "leds": [list(c) for c in self.leds],
            "led_brightness": self.led_brightness,
            "speaker": {"playing": now < self.speaker_until,
                        "freq": self.speaker_freq},
            "brightness": self.brightness,
        }


class Bridge:
    _FRAME_INTERVAL = 0.033
    _STATE_INTERVAL = 0.05

    def __init__(self, host, board, files_dir):
        global _bridge
        self.host = host
        self.files_dir = files_dir
        self.board = board
        self.state = DeviceState(board)
        self.framebuffer = None   # set by the M5 shim
        self.scene = None         # set by lvgl_scene.attach
        self.cpu_throttle = None
        self._alive = True
        self._timers = []
        self._last_frame_version = -1
        self._last_frame_at = 0.0
        self._last_state = None
        self._last_state_at = 0.0
        self._last_tick_at = 0.0
        _bridge = self

    # ---- outgoing ----
    def send(self, msg):
        self.host.event(json.dumps(msg))

    def log(self, msg, level="info"):
        self.host.log(level, str(msg))

    def send_audio(self, wav_bytes):
        with open(AUDIO_PATH, "wb") as fh:
            fh.write(wav_bytes)
        self.host.audio(AUDIO_PATH)

    def tone(self, freq, ms, volume):
        self.host.tone(int(freq), int(ms), int(volume))

    def take_mic_samples(self, frames, rate):
        """Samples from the presenter's microphone (int16 @ rate) or None."""
        got = self.host.mic(MIC_PATH, int(frames), int(rate))
        if not got:
            return None
        out = array.array("h", bytes(frames * 2))
        with open(MIC_PATH, "rb") as fh:
            fh.readinto(memoryview(out))
        return out

    def camera_frame(self, buf):
        """Fill ``buf`` (QVGA RGB565) with the presenter's webcam."""
        if not self.host.camera(CAMERA_PATH):
            return False
        with open(CAMERA_PATH, "rb") as fh:
            fh.readinto(buf)
        return True

    def http(self, method, url, headers, body):
        reply = json.loads(self.host.http(method, url, json.dumps(headers),
                                          body or ""))
        return reply

    # ---- cooperative loop ----
    def add_timer(self, timer):
        self._timers.append(timer)

    def tick(self):
        self._last_tick_at = monotonic()
        self.poll()
        if self._timers:
            now = monotonic()
            due = [t for t in self._timers if t.due <= now and not t.cancelled]
            self._timers = [t for t in self._timers
                            if not t.cancelled and t not in due]
            for timer in due:
                timer.fire()
        self.flush()

    def maybe_tick(self):
        """Called from busy code paths (drawing, servos, camera) so programs
        that never sleep still stream frames and state."""
        if monotonic() - self._last_tick_at >= self._FRAME_INTERVAL:
            self.tick()

    def poll(self):
        raw = self.host.inputs()
        if not raw:
            return
        data = json.loads(raw)
        st = self.state
        st.touch_down = bool(data["touch"])
        if st.touch_down:
            st.touch_x, st.touch_y = data["tx"], data["ty"]
        st.buttons["PWR"] = bool(data["pwr"])
        st.head_touch = [bool(z) for z in data["head"]]
        st.accel = data["accel"]
        st.gyro = data["gyro"]
        st.lux = data["lux"]
        st.prox = data["prox"]
        st.battery_level = data["battery"]
        hand = data.get("hand")
        if hand:   # the presenter turned the head in the 3D view
            st.servos[1].force(hand[0])
            st.servos[2].force(hand[1])

    def flush(self, force=False):
        now = monotonic()
        fb = self.framebuffer
        if fb is not None and fb.version != self._last_frame_version and \
                (force or now - self._last_frame_at >= self._FRAME_INTERVAL):
            self._last_frame_version = fb.version
            self._last_frame_at = now
            with open(FRAME_PATH, "wb") as fh:
                fh.write(fb._r._buf)
            self.host.frame(FRAME_PATH, fb._r.w, fb._r.h)
        if force or now - self._last_state_at >= self._STATE_INTERVAL:
            self._last_state_at = now
            snap = json.dumps(self.state.snapshot())
            if snap != self._last_state:
                self._last_state = snap
                self.host.state(snap)

    def sleep_ms(self, ms):
        """Sleep in slices so servos animate and inputs stay live."""
        end = monotonic() + ms / 1000
        while True:
            self.tick()
            left = end - monotonic()
            if left <= 0:
                break
            self.host.sleep(int(min(left, 0.03) * 1000) or 1)

    # ---- path mapping ----
    def map_path(self, path):
        if isinstance(path, str):
            if path.startswith("/flash/"):
                return compat.path_join(self.files_dir, path[len("/flash/"):])
            if path == "/flash":
                return self.files_dir
        return path
