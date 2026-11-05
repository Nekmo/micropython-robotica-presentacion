"""machine module shim — fake ESP32 peripherals."""

import time as _time

from stackchan_sim import bridge as _bridge_mod
from stackchan_sim import compat


def _bridge():
    return _bridge_mod.get()


class Pin:
    IN = 0
    OUT = 1
    OPEN_DRAIN = 2
    PULL_UP = 1
    PULL_DOWN = 2
    IRQ_RISING = 1
    IRQ_FALLING = 2

    def __init__(self, id, mode=-1, pull=-1, value=0, **kwargs):
        self._id = id
        self._value = value

    def value(self, v=None):
        if v is None:
            return self._value
        self._value = 1 if v else 0

    def on(self):
        self._value = 1

    def off(self):
        self._value = 0

    def irq(self, handler=None, trigger=0, **kwargs):
        pass

    def __call__(self, v=None):
        return self.value(v)


_SI12T = 0x68             # head touch controller: 3 zones, 2 bits each
_SI12T_OUTPUT = 0x10


_LTR553 = 0x23            # proximity and light sensor: 11-bit proximity
_LTR553_PS_DATA = 0x8D    # low byte, then 3 high bits at 0x8E


def _register(addr, memaddr):
    """Registers the simulator knows; everything else reads as zero."""
    if addr == _SI12T and memaddr == _SI12T_OUTPUT:
        zones = _bridge().state.head_touch
        return sum(0b11 << (2 * i) for i, down in enumerate(zones) if down)
    if addr == _LTR553 and memaddr in (_LTR553_PS_DATA, _LTR553_PS_DATA + 1):
        prox = max(0, min(2047, int(_bridge().state.prox)))
        return prox & 0xFF if memaddr == _LTR553_PS_DATA else prox >> 8
    return 0


# I/O expander (PY32): the 12 RGB LEDs live in its LED RAM (RGB565, little
# endian, 2 bytes each from 0x30) and are shown when bit 6 of 0x24 is set
_IOE = 0x6F
_IOE_LED_CFG = 0x24
_IOE_LED_RAM = 0x30
_ioe_led_ram = bytearray(64)


def _ioe_write(memaddr, data):
    if _IOE_LED_RAM <= memaddr < _IOE_LED_RAM + len(_ioe_led_ram):
        start = memaddr - _IOE_LED_RAM
        chunk = data[:len(_ioe_led_ram) - start]
        _ioe_led_ram[start:start + len(chunk)] = chunk
    elif memaddr == _IOE_LED_CFG and data and data[0] & 0x40:
        state = _bridge().state
        count = min(data[0] & 0x3F, len(state.leds))
        leds = list(state.leds)
        for i in range(count):
            c = _ioe_led_ram[2 * i] | _ioe_led_ram[2 * i + 1] << 8
            leds[i] = ((c >> 11) << 3, ((c >> 5) & 0x3F) << 2, (c & 0x1F) << 3)
        state.leds = leds


class I2C:
    """Fake I2C bus: reports the Stack-chan device addresses; the head touch
    sensor (Si12T) answers with the zones pressed on the 3D model."""

    _ADDRESSES = [0x18, 0x23, 0x28, 0x41, 0x59, 0x68, 0x6F]

    def __init__(self, id=0, scl=None, sda=None, freq=400000, **kwargs):
        self._id = id

    def scan(self):
        return list(self._ADDRESSES)

    def readfrom(self, addr, nbytes, stop=True):
        return bytes(nbytes)

    def readfrom_into(self, addr, buf, stop=True):
        for i in range(len(buf)):
            buf[i] = 0

    def writeto(self, addr, buf, stop=True):
        return len(buf)

    def readfrom_mem(self, addr, memaddr, nbytes, addrsize=8):
        return bytes(_register(addr, memaddr + i) for i in range(nbytes))

    def readfrom_mem_into(self, addr, memaddr, buf, addrsize=8):
        for i in range(len(buf)):
            buf[i] = _register(addr, memaddr + i)

    def writeto_mem(self, addr, memaddr, buf, addrsize=8):
        if addr == _IOE:
            _ioe_write(memaddr, bytes(buf))
        return len(buf)


SoftI2C = I2C


# Stack-chan's servo bus: Feetech SCS servos on UART1. Raw positions are
# steps of 5/16 degree; the firmware's zero positions (yaw 460, pitch 620)
# map onto the simulator's servo domains (yaw 0..360 centred at 180,
# pitch 0..90).
_SCS_STEP = 5 / 16
_SCS_ZERO = {1: (460, 180.0), 2: (620, 0.0)}


class _ScsBus:
    """Answers SCS packets (READ / WRITE) like the robot's two servos."""

    def __init__(self):
        self.regs = {1: {}, 2: {}}

    def _servo(self, sid):
        return _bridge().state.servos.get(sid)

    def _raw(self, sid):
        zero, deg0 = _SCS_ZERO[sid]
        return int(round(zero + (self._servo(sid).current() - deg0) / _SCS_STEP))

    def handle(self, packet):
        """Return the status packet for one request (or b"" if no reply)."""
        if len(packet) < 6 or packet[0] != 0xFF or packet[1] != 0xFF:
            return b""
        sid, length, inst = packet[2], packet[3], packet[4]
        params = packet[5:4 + length - 1]
        if (~sum(packet[2:4 + length - 1]) & 0xFF) != packet[3 + length]:
            return b""          # bad checksum: a real servo stays silent
        state = _bridge().state
        if sid not in _SCS_ZERO or not state.servo_power:
            return b""          # no such servo, or unpowered
        data = b""
        if inst == 0x03 and params:                 # WRITE
            addr, values = params[0], params[1:]
            servo = self._servo(sid)
            if addr == 40 and values:               # torque enable
                servo.torque = bool(values[0])
            elif addr == 42 and len(values) >= 2:   # goal position (+ time, speed)
                raw = values[0] << 8 | values[1]
                ms = values[2] << 8 | values[3] if len(values) >= 4 else 0
                zero, deg0 = _SCS_ZERO[sid]
                servo.set_target(deg0 + (raw - zero) * _SCS_STEP, ms)
        elif inst == 0x02 and len(params) >= 2:     # READ
            addr, count = params[0], params[1]
            if addr == 56:                          # present position
                raw = self._raw(sid)
                mem = bytes([(raw >> 8) & 0xFF, raw & 0xFF, 0, 0])
            elif addr == 66:                        # moving
                mem = bytes([1 if self._servo(sid).moving() else 0])
            elif addr == 40:
                mem = bytes([1 if self._servo(sid).torque else 0])
            else:
                mem = b""
            data = (mem + bytes(count))[:count]
        body = bytes([sid, len(data) + 2, 0]) + data
        return b"\xff\xff" + body + bytes([~sum(body) & 0xFF])


_scs_bus = _ScsBus()


class UART:
    def __init__(self, id=1, baudrate=115200, tx=None, rx=None, **kwargs):
        self._id = id
        self._buf = b""
        self._scs = _scs_bus if id == 1 else None

    def write(self, data):
        data = bytes(data)
        if self._scs is not None:
            # a request may be split in several writes: answer whole packets
            self._pending = getattr(self, "_pending", b"") + data
            while len(self._pending) >= 4 and len(self._pending) >= 4 + self._pending[3]:
                size = 4 + self._pending[3]
                self._buf += self._scs.handle(self._pending[:size])
                self._pending = self._pending[size:]
        return len(data)

    def read(self, nbytes=None):
        if not self._buf:
            return None
        if nbytes is None:
            nbytes = len(self._buf)
        data, self._buf = self._buf[:nbytes], self._buf[nbytes:]
        return data

    def readinto(self, buf):
        data = self.read(len(buf))
        if not data:
            return None
        buf[:len(data)] = data
        return len(data)

    def readline(self):
        return self.read()

    def any(self):
        return len(self._buf)

    def flush(self):
        pass

    def deinit(self):
        pass


class PWM:
    def __init__(self, pin, freq=5000, duty=512, duty_u16=None, **kwargs):
        self._freq = freq
        self._duty = duty

    def freq(self, v=None):
        if v is None:
            return self._freq
        self._freq = v

    def duty(self, v=None):
        if v is None:
            return self._duty
        self._duty = v

    def duty_u16(self, v=None):
        if v is None:
            return self._duty * 64
        self._duty = v // 64

    def deinit(self):
        pass


class ADC:
    ATTN_11DB = 3

    def __init__(self, pin, **kwargs):
        pass

    def read(self):
        return 2048

    def read_u16(self):
        return 32768

    def atten(self, v):
        pass


class RTC:
    def __init__(self, id=0):
        pass

    def datetime(self, dt=None):
        if dt is None:
            # localtime tuple order is shared by CPython and MicroPython:
            # (year, month, mday, hour, minute, second, weekday, yearday)
            t = _time.localtime()
            return (t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0)


class Timer:
    ONE_SHOT = 0
    PERIODIC = 1

    def __init__(self, id=-1):
        self._timer = None

    def init(self, mode=PERIODIC, period=-1, callback=None, freq=None):
        self.deinit()
        if callback is None:
            return
        if freq:
            period = int(1000 / freq)
        interval = max(0.001, period / 1000)
        periodic = mode == Timer.PERIODIC

        def run():
            callback(self)
            if periodic and self._timer is not None:
                self._timer = compat.Timer(interval, run)
                self._timer.start()

        self._timer = compat.Timer(interval, run)
        self._timer.start()

    def deinit(self):
        if self._timer is not None:
            t, self._timer = self._timer, None
            t.cancel()


class WDT:
    def __init__(self, id=0, timeout=5000):
        pass

    def feed(self):
        pass


def freq(hz=None):
    """Read/set the emulated CPU frequency, like machine.freq() on ESP32."""
    b = _bridge()
    throttle = getattr(b, "cpu_throttle", None)
    if hz is None:
        mhz = throttle.mhz if throttle is not None else b.state.cpu_mhz
        return int(mhz * 1_000_000) if mhz else 240_000_000
    mhz = max(0.0, float(hz) / 1_000_000)
    with b.state.lock:
        b.state.cpu_mhz = mhz
    if throttle is not None:
        throttle.set_mhz(mhz)
        throttle.apply_in_this_thread()  # machine.freq() runs in main thread
        b.log(f"machine.freq({int(hz)}) -> ~{mhz:g} MHz")
    else:
        b.log(f"machine.freq({int(hz)}): límite de CPU no disponible en "
              "runtime micropython", "warn")
    return None


def reset():
    _bridge().send({"t": "reset_request"})
    raise SystemExit(0)


def soft_reset():
    reset()


def reset_cause():
    return 1  # PWRON_RESET


def unique_id():
    return b"\xde\xad\xbe\xef\x24\x68"


def idle():
    _time.sleep(0.001)


def lightsleep(ms=None):
    _time.sleep((ms or 10) / 1000)


def deepsleep(ms=None):
    _bridge().log(f"machine.deepsleep({ms}) — emulated as reset")
    if ms:
        _time.sleep(min(ms / 1000, 5))
    reset()
