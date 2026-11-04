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


class I2C:
    """Fake I2C bus: reports the Stack-chan device addresses, reads zeros."""

    _ADDRESSES = [0x18, 0x28, 0x41, 0x59, 0x68, 0x6F]

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
        return bytes(nbytes)

    def readfrom_mem_into(self, addr, memaddr, buf, addrsize=8):
        for i in range(len(buf)):
            buf[i] = 0

    def writeto_mem(self, addr, memaddr, buf, addrsize=8):
        return len(buf)


SoftI2C = I2C


class UART:
    def __init__(self, id=1, baudrate=115200, tx=None, rx=None, **kwargs):
        self._id = id
        self._buf = b""

    def write(self, data):
        return len(data)

    def read(self, nbytes=None):
        return None

    def readinto(self, buf):
        return None

    def readline(self):
        return None

    def any(self):
        return 0

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
