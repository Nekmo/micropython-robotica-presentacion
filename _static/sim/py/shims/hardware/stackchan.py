"""hardware.stackchan shim — same public API as the UIFlow 2026 firmware.

Servos are simulated with finite movement speed (see bridge.ServoModel);
RGB LEDs, head touch and the battery monitor map onto the emulator state.
"""

import time

from stackchan_sim import bridge as _bridge_mod
from stackchan_sim.compat import monotonic as _mono

# constants mirrored from the real firmware
SERVO_ID_X = 1
SERVO_ID_Y = 2
SERVO_MODE_POS = 0
SERVO_MODE_PWM = 1
SERVO_SPEED_USER_MAX = 100
SERVO_SPEED_HW_MAX = 1500
RGB_LED_COUNT = 12
RGB_STRIP_LED_COUNT = 6
RGB_STRIP0_PHYS_START = 0
RGB_STRIP1_PHYS_START = 6
X_AXIS_ZERO_POS = 450
Y_AXIS_ZERO_POS = 125
MOVE_TIME_MS = 10


def _split_color(color):
    if isinstance(color, tuple):
        return tuple(int(v) for v in color[:3])
    color = int(color) & 0xFFFFFF
    return ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)


class _NFCStub:
    def is_card_present(self):
        return False

    def read_uid(self):
        return None

    def __getattr__(self, name):
        def _noop(*a, **k):
            return None
        return _noop


class StackChan:
    SERVO_ID_X = SERVO_ID_X
    SERVO_ID_Y = SERVO_ID_Y
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(StackChan, cls).__new__(cls)
        return cls._instance

    def __init__(self, i2c=1, uart=1):
        if StackChan._initialized:
            if i2c != self._i2c_num or uart != self._uart_num:
                raise ValueError(
                    "StackChan already initialized with i2c=%s uart=%s"
                    % (self._i2c_num, self._uart_num))
            return
        self._i2c_num = int(i2c)
        self._uart_num = int(uart)
        self._bridge = _bridge_mod.get()
        self._state = self._bridge.state
        self.servo_power_enabled = False
        self.servo_torque_enabled = {SERVO_ID_X: False, SERVO_ID_Y: False}
        self.nfc = _NFCStub()
        self._bridge.log("StackChan(i2c=%s, uart=%s) initialised" % (i2c, uart))
        StackChan._initialized = True

    # ── RGB LEDs ─────────────────────────────────────────────────────────
    def _phys_index(self, strip, index):
        if index < 0 or index >= RGB_STRIP_LED_COUNT:
            raise ValueError("index must be 0..%u for each strip"
                             % (RGB_STRIP_LED_COUNT - 1))
        if strip == 0:
            return RGB_STRIP0_PHYS_START + index
        if strip == 1:
            return RGB_STRIP1_PHYS_START + (RGB_STRIP_LED_COUNT - 1 - index)
        raise ValueError("strip must be 0 or 1")

    def set_rgb_color(self, *args):
        st = self._state
        n = len(args)
        with st.lock:
            if n == 1:
                st.leds = [_split_color(args[0])] * len(st.leds)
                return True
            if n == 2:
                strip, color = args
                if strip not in (0, 1):
                    raise ValueError("strip must be 0 or 1")
                start = RGB_STRIP0_PHYS_START if strip == 0 else RGB_STRIP1_PHYS_START
                c = _split_color(color)
                for i in range(start, start + RGB_STRIP_LED_COUNT):
                    st.leds[i] = c
                return True
            if n == 3:
                strip, index, color = args
                st.leds[self._phys_index(strip, index)] = _split_color(color)
                return True
        raise TypeError("set_rgb_color takes 1..3 arguments")

    def get_rgb_color(self, strip, index):
        with self._state.lock:
            return tuple(self._state.leds[self._phys_index(strip, index)])

    # ── Servos ───────────────────────────────────────────────────────────
    def set_servo_zero(self, reset=False):
        self._bridge.log("set_servo_zero(reset=%s)" % reset)
        return True

    def set_servo_power(self, enable=True):
        with self._state.lock:
            self._state.servo_power = bool(enable)
        self.servo_power_enabled = bool(enable)
        if enable:
            time.sleep(0.2)

    def set_servo_torque(self, servo_id, enable=True):
        self.servo_torque_enabled[servo_id] = bool(enable)
        servo = self._state.servos.get(servo_id)
        if servo is not None:
            servo.torque = bool(enable)

    def ensure_servo_x_mode(self, mode):
        self._state.servos[SERVO_ID_X].mode = mode

    def set_servo_x_pwm(self, pwm_out):
        servo = self._state.servos[SERVO_ID_X]
        servo.mode = SERVO_MODE_PWM
        servo.pwm = max(-100, min(100, int(pwm_out)))
        # PWM mode: constant rotation speed proportional to pwm
        target = servo.hi if servo.pwm > 0 else servo.lo
        deg_s = abs(servo.pwm) * 3.0
        if servo.pwm == 0:
            servo.set_target(servo.current(), 0, 0)
        else:
            with self._state.lock:
                servo._from = servo.current()
                servo._target = target
                servo._deg_s = deg_s
                servo._t_start = _mono()

    def set_servo_angle(self, servo_id, angle_deg, time_ms=MOVE_TIME_MS,
                        speed=0):
        if servo_id not in (SERVO_ID_X, SERVO_ID_Y):
            raise ValueError("servo_id must be SERVO_ID_X or SERVO_ID_Y")
        if not self._state.servo_power:
            self._bridge.log("set_servo_angle ignored: servo power is off",
                             "warn")
            return
        s = max(0, min(SERVO_SPEED_USER_MAX, int(speed)))
        hw_speed = int(round(s * SERVO_SPEED_HW_MAX / SERVO_SPEED_USER_MAX))
        with self._state.lock:
            self._state.servos[servo_id].set_target(angle_deg, time_ms,
                                                    hw_speed)
        self._bridge.maybe_tick()

    def get_servo_angle(self, servo_id):
        if servo_id not in (SERVO_ID_X, SERVO_ID_Y):
            return None
        return round(self._state.servos[servo_id].current(), 1)

    def get_servo_voltage(self, servo_id):
        return 7.4 if self._state.servo_power else 0.0

    def get_servo_current(self, servo_id):
        servo = self._state.servos.get(servo_id)
        if servo is None:
            return None
        return 180 if servo.moving() else 20

    # ── Head touch (Si12T) ───────────────────────────────────────────────
    def get_touch(self, index=None):
        with self._state.lock:
            zones = list(self._state.head_touch)
        if index is None:
            return [zones[0], zones[1], zones[2]]
        i = int(index)
        if i < 0 or i > 2:
            return None
        return zones[i]

    # ── Power monitor (INA226) ───────────────────────────────────────────
    def get_battery_voltage(self):
        return 6.0 + 2.4 * self._state.battery_level / 100

    def get_battery_current(self):
        base = 0.35 if self._state.servo_power else 0.15
        return base + (0.25 if self._state.servos[1].moving()
                       or self._state.servos[2].moving() else 0.0)

    def get_battery_power(self):
        return self.get_battery_voltage() * self.get_battery_current()
