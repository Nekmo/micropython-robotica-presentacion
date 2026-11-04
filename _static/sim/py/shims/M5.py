"""M5 module shim — emulates the M5Unified MicroPython API (UIFlow 2.x).

Implements M5.begin/update, Display/Lcd (M5GFX), Widgets, buttons, Touch,
Imu, Power, Als, Led, Speaker and Mic on top of the emulator bridge.
"""

import math
import random
import time as _time

from stackchan_sim import bridge as _bridge_mod
from stackchan_sim import wavutil
from stackchan_sim.compat import monotonic as _mono
from stackchan_sim.gfx import GFX, FontSpec, rgb

_bridge = _bridge_mod.get()
_board = _bridge.board
_screen_cfg = _board.get("screen", {})

# Native (rotation 0) panel size — portrait for Stack-chan
Display = GFX(_screen_cfg.get("width", 240), _screen_cfg.get("height", 320))
Display._path_mapper = _bridge.map_path
Lcd = Display
_bridge.framebuffer = Display
try:
    # LVGL scene graph (registers bridge.scene)
    from stackchan_sim import lvgl_scene as _scene_mod
    _scene_mod.get_scene().attach(Display)
except ImportError:
    _scene_mod = None

_UPDATE_SLEEP = 0.002  # keep host CPU sane in `while True: M5.update()` loops


class BOARD:
    unknown = 0
    M5Stack = 1
    M5StackCore2 = 2
    M5StickC = 3
    M5StickCPlus = 4
    M5StickCPlus2 = 5
    M5StackCoreS3 = 10
    M5AtomS3 = 11
    M5Dial = 12
    M5Cardputer = 14
    M5StackChan = 27


# ── Buttons ──────────────────────────────────────────────────────────────


class _CB_TYPE:
    WAS_CLICKED = 0
    WAS_DOUBLECLICKED = 1
    WAS_HOLD = 2
    WAS_PRESSED = 3
    WAS_RELEASED = 4
    WAS_SINGLE_CLICKED = 5
    WAS_SINGLECLICKED = 5


class Button:
    CB_TYPE = _CB_TYPE

    def __init__(self, name):
        self._name = name
        self._pressed = False
        self._last_change = _mono()
        self._press_start = 0.0
        self._hold_ms = 500
        self._debounce_ms = 10
        self._click_gap_s = 0.35
        self._clicks = 0
        self._last_release = 0.0
        self._counting = False
        # edge states of the current update cycle (M5Unified semantics:
        # was*() reflects the last M5.update() only, cleared on the next)
        self._flags = {}
        self._callbacks = {}
        self._holding = False
        self._hold_fired = False

    # -- internal, called from M5.update() ---------------------------------
    def _poll(self, now_pressed):
        now = _mono()
        fired = []
        # like real M5Unified, edge states last exactly one update cycle;
        # they are NOT sticky until read (firmware often calls M5.update()
        # a couple of times precisely to discard pending presses)
        self._flags = {}
        if now_pressed != self._pressed:
            self._pressed = now_pressed
            self._last_change = now
            self._flags["change"] = True
            if now_pressed:
                self._press_start = now
                self._hold_fired = False
                self._holding = False
                self._flags["pressed"] = True
                fired.append(_CB_TYPE.WAS_PRESSED)
            else:
                self._flags["released"] = True
                fired.append(_CB_TYPE.WAS_RELEASED)
                if not self._hold_fired:
                    self._flags["clicked"] = True
                    fired.append(_CB_TYPE.WAS_CLICKED)
                    self._clicks += 1
                    self._counting = True
                self._last_release = now
                self._holding = False
        if self._pressed and not self._hold_fired and \
                (now - self._press_start) * 1000 >= self._hold_ms:
            self._hold_fired = True
            self._holding = True
            self._flags["hold"] = True
            fired.append(_CB_TYPE.WAS_HOLD)
        if self._counting and not self._pressed and \
                now - self._last_release >= self._click_gap_s:
            self._counting = False
            self._flags["count_decided"] = self._clicks
            if self._clicks == 1:
                self._flags["single"] = True
                fired.append(_CB_TYPE.WAS_SINGLE_CLICKED)
            elif self._clicks >= 2:
                self._flags["double"] = True
                fired.append(_CB_TYPE.WAS_DOUBLECLICKED)
            self._decided_count = self._clicks
            self._clicks = 0
        for cb_type in fired:
            cb = self._callbacks.get(cb_type)
            if cb:
                try:
                    cb(None)
                except TypeError:
                    cb()

    def _take(self, key):
        # non-destructive: a state can be read many times within a cycle
        return bool(self._flags.get(key, False))

    # -- public API ----------------------------------------------------------
    def isPressed(self):
        return self._pressed

    def isReleased(self):
        return not self._pressed

    def isHolding(self):
        return self._holding

    def wasPressed(self):
        return self._take("pressed")

    def wasReleased(self):
        return self._take("released")

    def wasClicked(self):
        return self._take("clicked")

    def wasSingleClicked(self):
        return self._take("single")

    def wasDoubleClicked(self):
        return self._take("double")

    def wasHold(self):
        return self._take("hold")

    def wasChangePressed(self):
        return self._take("change")

    def wasDeciedClickCount(self):
        return "count_decided" in self._flags and bool(self._flags.pop("count_decided"))

    def getClickCount(self):
        return getattr(self, "_decided_count", 0)

    def lastChange(self):
        return int((_mono() - self._last_change) * 1000)

    def pressedFor(self, ms):
        return self._pressed and \
            (_mono() - self._press_start) * 1000 >= ms

    def releasedFor(self, ms):
        return (not self._pressed) and \
            (_mono() - self._last_change) * 1000 >= ms

    def setDebounceThresh(self, ms):
        self._debounce_ms = ms

    def setHoldThresh(self, ms):
        self._hold_ms = ms

    def setCallback(self, type=None, cb=None):
        if cb is not None:
            self._callbacks[type] = cb

    def removeCallback(self, type=None, cb=None):
        self._callbacks.pop(type, None)


BtnA = Button("A")
BtnB = Button("B")
BtnC = Button("C")
BtnPWR = Button("PWR")
BtnEXT = Button("EXT")
_BUTTONS = {"A": BtnA, "B": BtnB, "C": BtnC, "PWR": BtnPWR, "EXT": BtnEXT}


# ── Touch ────────────────────────────────────────────────────────────────


class _TouchDetail:
    def __init__(self, x, y, pressed):
        self.x = x
        self.y = y
        self._pressed = pressed

    def isPressed(self):
        return self._pressed

    def isHolding(self):
        return self._pressed

    def wasClicked(self):
        return False


class _Touch:
    def getX(self):
        return _bridge.state.touch_x

    def getY(self):
        return _bridge.state.touch_y

    def getCount(self):
        return 1 if _bridge.state.touch_down else 0

    def getDetail(self, index=0):
        st = _bridge.state
        return _TouchDetail(st.touch_x, st.touch_y, st.touch_down)

    def getTouchPointRaw(self, index=0):
        return (_bridge.state.touch_x, _bridge.state.touch_y)


Touch = _Touch()


# ── IMU ──────────────────────────────────────────────────────────────────


class _IMU_TYPE:
    NULL = 0
    UNKNOWN = 1
    SH200Q = 2
    MPU6050 = 3
    MPU6886 = 4
    MPU9250 = 5
    BMI270 = 6


class _Imu:
    IMU_TYPE = _IMU_TYPE

    def isEnabled(self):
        return True

    def getAccel(self):
        return tuple(_bridge.state.accel)

    def getGyro(self):
        return tuple(_bridge.state.gyro)

    def getMag(self):
        return tuple(_bridge.state.mag)

    def getType(self):
        return _IMU_TYPE.BMI270


Imu = _Imu()


# ── Power ────────────────────────────────────────────────────────────────


class _PORT:
    A = 0
    B1 = 1
    B2 = 2
    C1 = 3
    C2 = 4
    USB = 5
    PWR485 = 6
    PWRCAN = 7
    MAIN = 8


class _Power:
    PORT = _PORT

    def getBatteryLevel(self):
        return _bridge.state.battery_level

    def getBatteryVoltage(self):
        return 3.2 + 1.0 * _bridge.state.battery_level / 100

    def getBatteryCurrent(self):
        return 120.0 if _bridge.state.charging else -80.0

    def isCharging(self):
        return _bridge.state.charging

    def setBatteryCharge(self, enable):
        pass

    def setChargeCurrent(self, ma):
        pass

    def setChargeVoltage(self, mv):
        pass

    def getVBUSVoltage(self):
        return 5.0 if _bridge.state.charging else 0.0

    def setLed(self, brightness):
        _bridge.log(f"Power LED -> {brightness}")

    def setVibration(self, strength):
        with _bridge.state.lock:
            _bridge.state.vibration = int(strength)

    def powerOff(self):
        _bridge.send({"t": "poweroff"})
        _bridge.log("Power off requested")
        raise SystemExit(0)

    def timerSleep(self, seconds):
        _time.sleep(seconds)

    def deepSleep(self, us=0, wakeup=True):
        _bridge.log(f"deepSleep({us} us) — emulated as reset after sleep")
        _time.sleep(min(us / 1_000_000, 5) if us else 1)
        _bridge.send({"t": "reset_request"})
        raise SystemExit(0)

    def lightSleep(self, us=0, wakeup=True):
        _time.sleep(min(us / 1_000_000, 5) if us else 0.1)

    def setExtOutput(self, enable, port=None):
        pass

    def setUsbOutput(self, enable):
        pass


Power = _Power()


# ── ALS ──────────────────────────────────────────────────────────────────


class _Als:
    def getLightSensorData(self):
        return _bridge.state.lux

    def getProximitySensorData(self):
        return _bridge.state.prox


Als = _Als()


# ── LEDs ─────────────────────────────────────────────────────────────────


class _Led:
    def getCount(self):
        return len(_bridge.state.leds)

    def setBrightness(self, b):
        with _bridge.state.lock:
            _bridge.state.led_brightness = max(0, min(255, int(b)))

    def _norm(self, *args):
        if len(args) == 1:
            return rgb(args[0])
        return tuple(int(v) for v in args[:3])

    def setAllColor(self, *args):
        color = self._norm(*args)
        with _bridge.state.lock:
            _bridge.state.leds = [color] * len(_bridge.state.leds)

    def setColor(self, index, *args):
        color = self._norm(*args)
        with _bridge.state.lock:
            if 0 <= index < len(_bridge.state.leds):
                _bridge.state.leds[index] = color

    def display(self):
        pass  # state is streamed continuously


Led = _Led()


# ── Speaker ──────────────────────────────────────────────────────────────


def _pcm16_to_wav(pcm_bytes, rate, channels=1):
    return wavutil.pcm16_to_wav(pcm_bytes, rate, channels)


def _noise(amplitude=400):
    """Small random int in ±amplitude (getrandbits works on both runtimes)."""
    return (random.getrandbits(10) % (2 * amplitude + 1)) - amplitude


class _Speaker:
    _TONE_RATE = 16000
    _MAX_TONE_S = 10.0

    def begin(self):
        pass

    def end(self):
        pass

    def setVolume(self, v):
        with _bridge.state.lock:
            _bridge.state.speaker_volume = max(0, min(255, int(v)))

    def getVolume(self):
        return _bridge.state.speaker_volume

    def setVolumePercentage(self, pct):
        self.setVolume(int(pct * 255 / 100))

    def getVolumePercentage(self):
        return int(_bridge.state.speaker_volume * 100 / 255)

    def isPlaying(self):
        return _mono() < _bridge.state.speaker_until

    def tone(self, freq, ms=0):
        with _bridge.state.lock:
            _bridge.state.speaker_freq = int(freq)
            _bridge.state.speaker_until = _mono() + \
                (ms / 1000 if ms else 3600)
            volume = _bridge.state.speaker_volume
        # the presentation plays it with Web Audio (simulator)
        _bridge.tone(freq, ms if ms else 1000, volume)

    def stop(self):
        with _bridge.state.lock:
            _bridge.state.speaker_until = 0.0
            _bridge.state.speaker_freq = 0

    def playRaw(self, buf, rate=44100, stereo=False, repeat=1, channel=-1):
        data = bytes(buf)
        channels = 2 if stereo else 1
        secs = len(data) / 2 / channels / max(1, rate)
        with _bridge.state.lock:
            _bridge.state.speaker_freq = 0
            _bridge.state.speaker_until = _mono() + secs
        _bridge.log(f"Speaker playRaw {len(data)} bytes @{rate} Hz")
        _bridge.send_audio(_pcm16_to_wav(data, rate, channels))

    def playWav(self, buf, repeat=1, channel=-1):
        data = bytes(buf)
        if data[:4] == b"RIFF":
            secs = wavutil.wav_duration_s(data) or 1.0
            with _bridge.state.lock:
                _bridge.state.speaker_freq = 0
                _bridge.state.speaker_until = _mono() + secs
            _bridge.log(f"Speaker playWav {len(data)} bytes (~{secs:.1f}s)")
            _bridge.send_audio(data)
        else:
            self.playRaw(data, 16000)

    def playWavFile(self, path, repeat=1, channel=-1):
        real = _bridge.map_path(path)
        try:
            with open(real, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            _bridge.log(f"Speaker playWavFile {path}: {exc}", "warn")
            return
        _bridge.log(f"Speaker playWavFile {path}")
        self.playWav(data)


Speaker = _Speaker()


# ── Mic ──────────────────────────────────────────────────────────────────


class _Mic:
    def __init__(self):
        self._rate = 16000
        self._recording_until = 0.0

    def begin(self):
        pass

    def end(self):
        pass

    def setSampleRate(self, rate):
        self._rate = int(rate)

    def isRecording(self):
        return _mono() < self._recording_until

    def record(self, buf, rate=None, stereo=False):
        rate = rate or self._rate
        n = len(buf) // 2               # int16 samples in the buffer
        frames = n // (2 if stereo else 1)
        secs = frames / max(1, rate)
        self._recording_until = _mono() + secs
        pcm = _bridge.take_mic_samples(frames, rate)
        if pcm is None:
            # no queued input: quiet noise so volume meters look alive
            for i in range(n):
                val = _noise()
                buf[2 * i] = val & 0xFF
                buf[2 * i + 1] = (val >> 8) & 0xFF
        else:
            for f in range(frames):
                val = pcm[f] & 0xFFFF
                lo, hi = val & 0xFF, (val >> 8) & 0xFF
                if stereo:
                    buf[4 * f] = lo
                    buf[4 * f + 1] = hi
                    buf[4 * f + 2] = lo
                    buf[4 * f + 3] = hi
                else:
                    buf[2 * f] = lo
                    buf[2 * f + 1] = hi
        _time.sleep(min(secs, 5))
        return True

    def recordWavFile(self, path, seconds=1, rate=16000):
        frames = int(seconds * rate)
        pcm = _bridge.take_mic_samples(frames, rate)
        if pcm is None:
            import array
            pcm = array.array("h", (_noise() for _ in range(frames)))
        real = _bridge.map_path(path)
        try:
            with open(real, "wb") as fh:
                fh.write(_pcm16_to_wav(bytes(pcm), rate))
        except OSError as exc:
            _bridge.log(f"Mic recordWavFile {path}: {exc}", "warn")
            return False
        self._recording_until = _mono() + seconds
        _time.sleep(min(seconds, 5))
        return True


Mic = _Mic()


# ── Widgets (M5GFX-backed widget layer) ──────────────────────────────────


class _FONTS:
    Montserrat12 = FontSpec("Montserrat12", 12)
    Montserrat14 = FontSpec("Montserrat14", 14)
    Montserrat16 = FontSpec("Montserrat16", 16)
    Montserrat18 = FontSpec("Montserrat18", 18)
    Montserrat20 = FontSpec("Montserrat20", 20)
    Montserrat22 = FontSpec("Montserrat22", 22)
    Montserrat24 = FontSpec("Montserrat24", 24)
    Montserrat30 = FontSpec("Montserrat30", 30)
    Montserrat36 = FontSpec("Montserrat36", 36)
    Montserrat40 = FontSpec("Montserrat40", 40)
    Montserrat44 = FontSpec("Montserrat44", 44)
    Montserrat48 = FontSpec("Montserrat48", 48)
    ASCII7 = Montserrat12
    DejaVu9 = FontSpec("DejaVu9", 9)
    DejaVu12 = FontSpec("DejaVu12", 12)
    DejaVu18 = FontSpec("DejaVu18", 18)
    DejaVu24 = FontSpec("DejaVu24", 24)
    DejaVu40 = FontSpec("DejaVu40", 40)
    DejaVu56 = FontSpec("DejaVu56", 56)
    DejaVu72 = FontSpec("DejaVu72", 72)
    EFontCN24 = FontSpec("EFontCN24", 24)
    EFontJA24 = FontSpec("EFontJA24", 24)
    EFontKR24 = FontSpec("EFontKR24", 24)


class _COLOR:
    BLACK = 0x000000
    NAVY = 0x000080
    DARKGREEN = 0x006400
    DARKCYAN = 0x008B8B
    MAROON = 0x800000
    PURPLE = 0x800080
    OLIVE = 0x808000
    LIGHTGREY = 0xD3D3D3
    DARKGREY = 0xA9A9A9
    BLUE = 0x0000FF
    GREEN = 0x00FF00
    CYAN = 0x00FFFF
    RED = 0xFF0000
    MAGENTA = 0xFF00FF
    YELLOW = 0xFFFF00
    WHITE = 0xFFFFFF
    ORANGE = 0xFFA500
    GREENYELLOW = 0xADFF2F
    PINK = 0xFFC0CB


class _WidgetBase:
    """GFX widget: snapshots the covered region and restores it on redraw."""

    def __init__(self):
        self._snap = None
        self._box = None
        self._visible = True

    def _erase(self):
        if self._snap is not None:
            Display.restore_region(self._snap, self._box)
            self._snap = None

    def _capture(self, x, y, w, h):
        self._snap, self._box = Display.snapshot_region(int(x), int(y),
                                                        int(w), int(h))

    def _redraw(self):
        self._erase()
        if self._visible:
            self._paint()

    def _paint(self):  # pragma: no cover - overridden
        raise NotImplementedError

    def setVisible(self, visible):
        self._visible = bool(visible)
        self._redraw()


class Label(_WidgetBase):
    def __init__(self, text, x, y, size=1.0, fg_color=0xFFFFFF,
                 bg_color=0x000000, font=None):
        super().__init__()
        self._text = str(text)
        self._x, self._y = int(x), int(y)
        self._size = float(size)
        self._fg, self._bg = fg_color, bg_color
        self._font = font or _FONTS.DejaVu12
        self._paint()

    def _paint(self):
        px = self._font.px * self._size
        w, asc, desc = Display.measure_text(self._text or " ", px)
        self._capture(self._x, self._y, w + 2, asc + desc)
        Display._draw_text(self._text, self._x, self._y, anchor="la",
                           fg=self._fg, bg=None, px=px)

    def setText(self, text):
        self._text = str(text)
        self._redraw()

    def setColor(self, fg_color, bg_color=None):
        self._fg = fg_color
        if bg_color is not None:
            self._bg = bg_color
        self._redraw()

    def setCursor(self, x, y):
        self._x, self._y = int(x), int(y)
        self._redraw()

    def setSize(self, size):
        self._size = float(size)
        self._redraw()

    def setFont(self, font):
        self._font = font
        self._redraw()


class Title(_WidgetBase):
    HEIGHT = 26

    def __init__(self, text, textX=10, fg_color=0xFFFFFF, bg_color=0x0000FF,
                 font=None):
        super().__init__()
        self._text = str(text)
        self._tx = int(textX)
        self._fg, self._bg = fg_color, bg_color
        self._font = font or _FONTS.DejaVu18
        self._paint()

    def _paint(self):
        self._capture(0, 0, Display.width(), self.HEIGHT)
        Display.fillRect(0, 0, Display.width(), self.HEIGHT, self._bg)
        Display._draw_text(self._text, self._tx, self.HEIGHT // 2,
                           anchor="lm", fg=self._fg, px=self._font.px)

    def setText(self, text):
        self._text = str(text)
        self._redraw()

    def setColor(self, fg, bg=None):
        self._fg = fg
        if bg is not None:
            self._bg = bg
        self._redraw()

    def setSize(self, size):
        self._redraw()

    def setTextCursor(self, x, y=0):
        self._tx = int(x)
        self._redraw()


class Rectangle(_WidgetBase):
    def __init__(self, x, y, w, h, fg_color=0xFFFFFF, bg_color=0xFFFFFF):
        super().__init__()
        self._x, self._y, self._w, self._h = int(x), int(y), int(w), int(h)
        self._fg, self._bg = fg_color, bg_color
        self._paint()

    def _paint(self):
        self._capture(self._x, self._y, self._w, self._h)
        Display.fillRect(self._x, self._y, self._w, self._h, self._bg)
        Display.drawRect(self._x, self._y, self._w, self._h, self._fg)

    def setColor(self, fg_color, bg_color=None):
        self._fg = fg_color
        if bg_color is not None:
            self._bg = bg_color
        self._redraw()

    def setCursor(self, x, y):
        self._x, self._y = int(x), int(y)
        self._redraw()

    def setSize(self, w, h):
        self._w, self._h = int(w), int(h)
        self._redraw()


class Circle(_WidgetBase):
    def __init__(self, x, y, r, fg_color=0xFFFFFF, bg_color=0xFFFFFF):
        super().__init__()
        self._x, self._y, self._r = int(x), int(y), int(r)
        self._fg, self._bg = fg_color, bg_color
        self._paint()

    def _paint(self):
        r = self._r
        self._capture(self._x - r, self._y - r, 2 * r + 1, 2 * r + 1)
        Display.fillCircle(self._x, self._y, r, self._bg)
        Display.drawCircle(self._x, self._y, r, self._fg)

    def setRadius(self, r):
        self._r = int(r)
        self._redraw()

    def setCursor(self, x, y):
        self._x, self._y = int(x), int(y)
        self._redraw()

    def setColor(self, fg_color, bg_color=None):
        self._fg = fg_color
        if bg_color is not None:
            self._bg = bg_color
        self._redraw()


class Line(_WidgetBase):
    def __init__(self, x0, y0, x1, y1, color=0xFFFFFF):
        super().__init__()
        self._pts = [int(x0), int(y0), int(x1), int(y1)]
        self._color = color
        self._paint()

    def _paint(self):
        x0, y0, x1, y1 = self._pts
        self._capture(min(x0, x1), min(y0, y1),
                      abs(x1 - x0) + 1, abs(y1 - y0) + 1)
        Display.drawLine(x0, y0, x1, y1, self._color)

    def setColor(self, color):
        self._color = color
        self._redraw()

    def setPoints(self, x0, y0, x1, y1):
        self._pts = [int(x0), int(y0), int(x1), int(y1)]
        self._redraw()


class Triangle(_WidgetBase):
    def __init__(self, x0, y0, x1, y1, x2, y2, fg_color=0xFFFFFF,
                 bg_color=0xFFFFFF):
        super().__init__()
        self._pts = [int(v) for v in (x0, y0, x1, y1, x2, y2)]
        self._fg, self._bg = fg_color, bg_color
        self._paint()

    def _paint(self):
        xs = self._pts[0::2]
        ys = self._pts[1::2]
        self._capture(min(xs), min(ys), max(xs) - min(xs) + 1,
                      max(ys) - min(ys) + 1)
        Display.fillTriangle(*self._pts, self._bg)
        Display.drawTriangle(*self._pts, self._fg)

    def setColor(self, fg_color, bg_color=None):
        self._fg = fg_color
        if bg_color is not None:
            self._bg = bg_color
        self._redraw()

    def setPoints(self, x0, y0, x1, y1, x2, y2):
        self._pts = [int(v) for v in (x0, y0, x1, y1, x2, y2)]
        self._redraw()


class Image(_WidgetBase):
    def __init__(self, path, x=0, y=0, scale_x=1.0, scale_y=1.0):
        super().__init__()
        self._path = path
        self._x, self._y = int(x), int(y)
        self._scale = (float(scale_x), float(scale_y or scale_x))
        self._paint()

    def _paint(self):
        size = Display.image_size(self._path)
        if size is None:
            self._capture(self._x, self._y, 32, 32)
            Display.drawImage(self._path, self._x, self._y)  # placeholder
            return
        w = max(1, int(size[0] * self._scale[0]))
        h = max(1, int(size[1] * self._scale[1]))
        self._capture(self._x, self._y, w, h)
        Display.drawImage(self._path, self._x, self._y,
                          scaleX=self._scale[0], scaleY=self._scale[1])

    def setImage(self, path):
        self._path = path
        self._redraw()

    def setCursor(self, x, y):
        self._x, self._y = int(x), int(y)
        self._redraw()

    def setScale(self, scale_x, scale_y=None):
        self._scale = (float(scale_x), float(scale_y or scale_x))
        self._redraw()


class QRCode(_WidgetBase):
    def __init__(self, text, x=0, y=0, size=100, version=1):
        super().__init__()
        self._text = str(text)
        self._x, self._y, self._size = int(x), int(y), int(size)
        self._version = version
        self._paint()

    def _paint(self):
        self._capture(self._x, self._y, self._size, self._size)
        Display.drawQR(self._text, self._x, self._y, self._size, self._version)

    def setText(self, text):
        self._text = str(text)
        self._redraw()

    def setVersion(self, v):
        self._version = v
        self._redraw()

    def setSize(self, size):
        self._size = int(size)
        self._redraw()

    def setCursor(self, x, y):
        self._x, self._y = int(x), int(y)
        self._redraw()


class _Widgets:
    FONTS = _FONTS
    COLOR = _COLOR
    Label = Label
    Title = Title
    Rectangle = Rectangle
    Circle = Circle
    Line = Line
    Triangle = Triangle
    Image = Image
    QRCode = QRCode

    @staticmethod
    def fillScreen(color):
        Display.fillScreen(color)

    @staticmethod
    def setRotation(r):
        Display.setRotation(r)

    @staticmethod
    def setBrightness(b):
        Display.setBrightness(b)


Widgets = _Widgets()


# ── top level ────────────────────────────────────────────────────────────

_began = False


def begin():
    global _began
    _began = True
    _bridge.log("M5.begin()")


def update():
    """Poll inputs, run callbacks and flush the LVGL scene. Call every loop."""
    if not _bridge._alive:
        raise SystemExit(0)  # GUI closed the link: device lost power
    throttle = _bridge.cpu_throttle
    if throttle is not None and throttle.pending:
        # CPU-frequency changes from the GUI/MCP land in the main thread here
        throttle.apply_in_this_thread()
    _bridge.poll()
    st = _bridge.state
    with st.lock:
        btn_states = dict(st.buttons)
    for name, btn in _BUTTONS.items():
        btn._poll(btn_states.get(name, False))
    if _bridge.scene is not None:
        _bridge.scene.flush()
    _bridge.tick()


def end():
    _bridge.log("M5.end()")


def getBoard():
    return _board.get("board_id", BOARD.M5StackChan)


def getDisplayCount():
    return 1


def getDisplay(index=0):
    return Display


def Displays(index=0):
    return Display


def addDisplay(*args, **kwargs):
    raise NotImplementedError("external displays not supported in emulator")


def createSpeaker():
    return Speaker


def createMic():
    return Mic


__all__ = [
    "begin", "update", "end", "getBoard", "getDisplay", "getDisplayCount",
    "Display", "Lcd", "Widgets", "Touch", "Imu", "Power", "Als", "Led",
    "Speaker", "Mic", "BtnA", "BtnB", "BtnC", "BtnPWR", "BtnEXT", "BOARD",
]
