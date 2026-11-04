"""HAL for the Stack-chan MicroPython firmware.

Port of ``main/hal`` from the original ESP-IDF firmware onto the UIFlow
MicroPython API (``hardware.stackchan``, ``M5``).  The original runs
head-touch / IMU detection in FreeRTOS tasks; here everything is polled
cooperatively from :meth:`Hal.update` in the main loop.
"""

import time

# ---------------------------------------------------------------- events

# HeadPetGesture (hal_head_touch.cpp)
GESTURE_NONE = 0
GESTURE_PRESS = 1
GESTURE_RELEASE = 2
GESTURE_SWIPE_FORWARD = 3
GESTURE_SWIPE_BACKWARD = 4

# ImuMotionEvent (hal_imu.cpp)
IMU_EVENT_SHAKE = 1


class Signal(object):
    """Minimal port of the firmware's signal/slot helper."""

    def __init__(self):
        self._slots = {}
        self._next_id = 0

    def connect(self, callback):
        sid = self._next_id
        self._next_id += 1
        self._slots[sid] = callback
        return sid

    def disconnect(self, sid):
        self._slots.pop(sid, None)

    def clear(self):
        self._slots.clear()

    def emit(self, *args):
        for callback in list(self._slots.values()):
            callback(*args)


# ------------------------------------------------- head touch recognizer

_TOUCH_IDLE = 0
_TOUCH_TOUCHED = 1
_TOUCH_SWIPING = 2

_SWIPE_THRESHOLD = 40  # percent position delta, same as TouchConfig


class GestureRecognizer(object):
    """Port of hal_head_touch.cpp GestureRecognizer."""

    def __init__(self):
        self._state = _TOUCH_IDLE
        self._initial_position = 0

    @staticmethod
    def _position(zones):
        total = zones[0] + zones[1] + zones[2]
        if total == 0:
            return 0
        return (zones[0] * -100 + zones[2] * 100) // total

    def update(self, zones):
        touched = zones[0] or zones[1] or zones[2]
        gesture = GESTURE_NONE

        if self._state == _TOUCH_IDLE:
            if touched:
                self._state = _TOUCH_TOUCHED
                self._initial_position = self._position(zones)
                gesture = GESTURE_PRESS
        elif self._state == _TOUCH_TOUCHED:
            if not touched:
                self._state = _TOUCH_IDLE
                gesture = GESTURE_RELEASE
            else:
                delta = self._position(zones) - self._initial_position
                if delta > _SWIPE_THRESHOLD:
                    self._state = _TOUCH_SWIPING
                    gesture = GESTURE_SWIPE_FORWARD
                elif delta < -_SWIPE_THRESHOLD:
                    self._state = _TOUCH_SWIPING
                    gesture = GESTURE_SWIPE_BACKWARD
        else:  # SWIPING
            if not touched:
                self._state = _TOUCH_IDLE
                gesture = GESTURE_RELEASE

        return gesture


# ------------------------------------------------------- shake detector

class MotionDetector(object):
    """Port of utils/motion_detector (differential shake detection).

    The original works on BMI270 output in m/s^2 with threshold 16.
    M5.Imu.getAccel() returns g, so the default threshold is scaled.
    """

    def __init__(self, millis_fn, threshold=1.6):
        self._millis = millis_fn
        self._threshold = threshold
        self._prev = (0.0, 0.0, 0.0)
        self._last_peak = 0
        self._count = 0
        self._detected = False

    def update(self, ax, ay, az):
        now = self._millis()
        px, py, pz = self._prev
        diff = abs(ax - px) + abs(ay - py) + abs(az - pz)
        self._prev = (ax, ay, az)

        if diff > self._threshold:
            if now - self._last_peak > 100:      # debounce
                if now - self._last_peak < 1000:  # 1 s window
                    self._count += 1
                else:
                    self._count = 1
                self._last_peak = now
                if self._count >= 3:
                    self._detected = True
                    self._count = 0

    def is_shake_detected(self):
        if self._detected:
            self._detected = False
            return True
        return False


# ----------------------------------------------------------------- HAL

class Hal(object):
    def __init__(self):
        self._t0 = time.ticks_ms()
        self.sc = None                     # hardware.stackchan.StackChan
        self.imu_ok = False
        self.on_head_pet_gesture = Signal()
        self.on_imu_motion_event = Signal()
        self._recognizer = GestureRecognizer()
        self._detector = MotionDetector(self.millis)
        self._next_touch_poll = 0
        self._next_imu_poll = 0
        self._head_touched = False

    # -- time ---------------------------------------------------------
    def millis(self):
        return time.ticks_diff(time.ticks_ms(), self._t0)

    def delay(self, ms):
        time.sleep_ms(ms)

    # -- init ---------------------------------------------------------
    def init(self):
        # Servo bus + power (Si12T head touch shares the power rail and
        # must come up after servo power, as on the original board).
        try:
            from hardware.stackchan import StackChan as HwStackChan
            self.sc = HwStackChan(i2c=1, uart=1)
            self.sc.set_servo_power(True)
        except Exception as exc:
            print('[HAL] hardware.stackchan unavailable:', exc)
            self.sc = None

        try:
            import M5
            self.imu_ok = bool(M5.Imu.isEnabled())
        except Exception:
            self.imu_ok = False

    # -- cooperative polling ------------------------------------------
    def update(self):
        now = self.millis()

        if self.sc is not None and now >= self._next_touch_poll:
            self._next_touch_poll = now + 50
            try:
                zones = self.sc.get_touch()
            except Exception:
                zones = None
            if zones is not None:
                zones = [1 if z else 0 for z in zones]
                self._head_touched = bool(zones[0] or zones[1] or zones[2])
                gesture = self._recognizer.update(zones)
                if gesture != GESTURE_NONE:
                    self.on_head_pet_gesture.emit(gesture)

        if self.imu_ok and now >= self._next_imu_poll:
            self._next_imu_poll = now + 100
            try:
                import M5
                ax, ay, az = M5.Imu.getAccel()
                self._detector.update(ax, ay, az)
                if self._detector.is_shake_detected():
                    self.on_imu_motion_event.emit(IMU_EVENT_SHAKE)
            except Exception:
                pass

    def is_head_touched(self):
        return self._head_touched

    # -- neon light backend --------------------------------------------
    # Left strip = 0, right strip = 1 (6 LEDs each, like the original).
    def set_neon_color(self, strip, index, r, g, b):
        if self.sc is None:
            return
        try:
            self.sc.set_rgb_color(strip, index, (r << 16) | (g << 8) | b)
        except Exception:
            pass


_hal = None


def get_hal():
    global _hal
    if _hal is None:
        _hal = Hal()
    return _hal