"""Port of stackchan/motion (Servo + Motion).

Angles use the original firmware units: tenths of a degree relative to
the calibrated zero.  Yaw limit is (-1280, 1280), pitch limit (30, 870).
Motion is smoothed by a damped-spring animation updated at <=50 Hz; the
servo implementation maps the spring output onto the UIFlow
``hardware.stackchan`` degree API.
"""

import math

from .uitk import clamp, map_range, AnimateValue
from .hal import get_hal

RAD_TO_DEG = 180.0 / math.pi

# hal_servo.cpp limits
YAW_ANGLE_LIMIT = (-1280, 1280)
PITCH_ANGLE_LIMIT = (30, 870)


class Servo(object):
    """Spring-animated servo base (motion/servo.cpp)."""

    def __init__(self):
        self._hal = get_hal()
        self._angle_limit = (0, 0)
        self._angle_anim = AnimateValue()
        self._last_tick = 0
        self._last_torque_check_tick = 0
        self._snap_to_target_on_rest = False
        self._auto_torque_release_enabled = True
        self._auto_angle_sync_enabled = True

    # -- overridables ---------------------------------------------------
    def set_angle_impl(self, angle):
        raise NotImplementedError

    def is_moving_impl(self):
        return False

    def read_current_angle(self):
        """Physical angle in tenths, or None when not readable."""
        return None

    def set_torque_enabled(self, enabled):
        pass

    def get_torque_enabled(self):
        return False

    def rotate(self, velocity):
        pass

    def set_current_angle_as_zero(self):
        pass

    def reset_zero_calibration(self):
        pass

    # -- lifecycle --------------------------------------------------------
    def init(self):
        self._apply_default_spring()
        current = self.read_current_angle()
        if current is None:
            current = 0
        self._angle_anim.teleport(current)
        self.update()
        self.set_torque_enabled(False)

    def update(self):
        now = self._hal.millis()
        # Keep update in at most 50 Hz
        if now - self._last_tick < 20:
            return
        self._last_tick = now

        anim = self._angle_anim
        if not anim.done():
            anim.update_with_delta(0.02)
            self.set_angle_impl(int(anim.direct_value()))
        elif self._snap_to_target_on_rest:
            self._snap_to_target_on_rest = False
            self.set_angle_impl(int(anim.end))
        elif self._auto_torque_release_enabled and not self.is_moving():
            if now - self._last_torque_check_tick > 200:
                if self.get_torque_enabled():
                    self.set_torque_enabled(False)
                self._last_torque_check_tick = now

    # -- moves --------------------------------------------------------------
    def move(self, angle):
        self._apply_default_spring()
        self._update_target(angle)

    def move_with_spring_params(self, angle, stiffness=170.0, damping=26.0):
        spring = self._angle_anim.spring
        spring.stiffness = stiffness
        spring.damping = damping
        self._update_target(angle)

    def move_with_speed(self, angle, speed):
        stiffness, damping, rest = self._map_speed(speed)
        spring = self._angle_anim.spring
        spring.stiffness = stiffness
        spring.damping = damping
        spring.rest_delta = rest
        spring.rest_speed = rest
        self._update_target(angle)

    # -- queries -------------------------------------------------------------
    def get_current_angle(self):
        return int(self._angle_anim.direct_value())

    def get_angle_limit(self):
        return self._angle_limit

    def is_moving(self):
        return (not self._angle_anim.done()) or self.is_moving_impl()

    def set_auto_torque_release_enabled(self, enabled):
        self._auto_torque_release_enabled = enabled

    def set_auto_angle_sync_enabled(self, enabled):
        self._auto_angle_sync_enabled = enabled

    # -- internals ----------------------------------------------------------
    def _set_angle_limit(self, limit):
        self._angle_limit = limit

    def _apply_default_spring(self):
        spring = self._angle_anim.spring
        spring.stiffness = 170.0
        spring.damping = 26.0
        spring.rest_delta = 0.1
        spring.rest_speed = 0.1

    def _update_target(self, angle):
        angle = clamp(angle, self._angle_limit[0], self._angle_limit[1])
        if self._auto_angle_sync_enabled:
            physical = self.read_current_angle()
            if physical is not None:
                self._angle_anim.teleport(physical)
            else:
                self._angle_anim.teleport(self.get_current_angle())
        self.set_torque_enabled(True)
        self._angle_anim.set_target(angle)
        self._snap_to_target_on_rest = True

    @staticmethod
    def _map_speed(speed):
        """speed 0-1000 -> (stiffness, damping, rest threshold)."""
        speed = clamp(speed, 0, 1000)
        k_min, k_max = 10.0, 650.0
        normalized = speed / 1000.0
        stiffness = k_min + normalized * normalized * (k_max - k_min)
        damping = 2.0 * math.sqrt(stiffness)
        rest = 0.5 if speed > 800 else 0.1
        return stiffness, damping, rest


class UiflowServo(Servo):
    """Servo over UIFlow ``hardware.stackchan.set_servo_angle`` (degrees).

    ``ui_center_deg`` is auto-detected at init so the port works both on
    the emulator (X domain 0..360 centred at 180, Y centred at 45) and on
    a device whose UIFlow angles are already zero-relative.
    """

    def __init__(self, servo_id, angle_limit, ui_scale=1.0, ui_limit=None):
        Servo.__init__(self)
        self._id = servo_id
        self._set_angle_limit(angle_limit)
        self._ui_scale = ui_scale        # UI degrees per firmware degree
        self._ui_center = 0.0
        self._ui_limit = ui_limit
        self._torque = False
        self._last_sent_deg = None

    def init(self):
        sc = self._hal.sc
        if sc is not None:
            try:
                reading = sc.get_servo_angle(self._id)
            except Exception:
                reading = None
            if reading is not None:
                if self._id == 1:   # yaw
                    self._ui_center = 180.0 if reading > 90 else 0.0
                else:               # pitch: keep boot pose as neutral
                    self._ui_center = (reading - 3.0 * self._ui_scale
                                       if reading > 20 else 0.0)
        Servo.init(self)

    # -- unit mapping -----------------------------------------------------
    def _to_ui_deg(self, angle_tenths):
        deg = self._ui_center + (angle_tenths / 10.0) * self._ui_scale
        if self._ui_limit is not None:
            deg = clamp(deg, self._ui_limit[0], self._ui_limit[1])
        return deg

    def _from_ui_deg(self, deg):
        if self._ui_scale == 0:
            return 0
        return int((deg - self._ui_center) * 10.0 / self._ui_scale)

    # -- Servo implementation ------------------------------------------------
    def set_angle_impl(self, angle):
        sc = self._hal.sc
        if sc is None:
            return
        deg = self._to_ui_deg(angle)
        if self._last_sent_deg is not None and abs(deg - self._last_sent_deg) < 0.05:
            return
        self._last_sent_deg = deg
        try:
            sc.set_servo_angle(self._id, deg, 20, 0)
        except Exception:
            pass

    def read_current_angle(self):
        sc = self._hal.sc
        if sc is None:
            return None
        try:
            deg = sc.get_servo_angle(self._id)
        except Exception:
            return None
        if deg is None:
            return None
        angle = self._from_ui_deg(deg)
        return clamp(angle, self._angle_limit[0], self._angle_limit[1])

    def set_torque_enabled(self, enabled):
        if enabled == self._torque:
            return
        self._torque = enabled
        sc = self._hal.sc
        if sc is None:
            return
        try:
            sc.set_servo_torque(self._id, enable=enabled)
        except Exception:
            pass

    def get_torque_enabled(self):
        return self._torque

    def set_current_angle_as_zero(self):
        sc = self._hal.sc
        if sc is None:
            return
        try:
            sc.set_servo_zero()
        except Exception:
            pass

    def reset_zero_calibration(self):
        sc = self._hal.sc
        if sc is None:
            return
        try:
            sc.set_servo_zero(reset=True)
        except Exception:
            pass


class Motion(object):
    """Port of motion/motion.cpp."""

    def __init__(self, yaw_servo, pitch_servo):
        self._yaw = yaw_servo
        self._pitch = pitch_servo
        self._is_modify_locked = False

    def init(self):
        self._yaw.init()
        self._pitch.init()

    def update(self):
        self._yaw.update()
        self._pitch.update()

    def yaw_servo(self):
        return self._yaw

    def pitch_servo(self):
        return self._pitch

    def move_yaw(self, angle):
        self._yaw.move(angle)

    def move_yaw_with_speed(self, angle, speed):
        self._yaw.move_with_speed(angle, speed)

    def move_pitch(self, angle):
        self._pitch.move(angle)

    def move_pitch_with_speed(self, angle, speed):
        self._pitch.move_with_speed(angle, speed)

    def move(self, yaw_angle, pitch_angle):
        self._yaw.move(yaw_angle)
        self._pitch.move(pitch_angle)

    def move_with_speed(self, yaw_angle, pitch_angle, speed):
        self._yaw.move_with_speed(yaw_angle, speed)
        self._pitch.move_with_speed(pitch_angle, speed)

    def go_home(self, speed=500):
        self.move_with_speed(0, 0, speed)

    def stop(self):
        self._yaw.move(self._yaw.get_current_angle())
        self._pitch.move(self._pitch.get_current_angle())

    def look_at_normalized(self, x, y, speed=500):
        yaw_limit = self._yaw.get_angle_limit()
        pitch_limit = self._pitch.get_angle_limit()
        yaw_angle = int(map_range(float(x), -1.0, 1.0,
                                  float(yaw_limit[0]), float(yaw_limit[1])))
        pitch_angle = int(map_range(float(y), -1.0, 1.0,
                                    float(pitch_limit[0]), float(pitch_limit[1])))
        self.move_with_speed(yaw_angle, pitch_angle, speed)

    def look_at_point(self, x, y, z, speed=500):
        yaw_rad = math.atan2(y, x)
        ground_dist = math.sqrt(x * x + y * y)
        pitch_rad = math.atan2(z, ground_dist)
        yaw_angle = int(yaw_rad * RAD_TO_DEG * 10)
        pitch_angle = int(pitch_rad * RAD_TO_DEG * 10)
        self.move_with_speed(yaw_angle, pitch_angle, speed)

    def is_moving(self):
        return self._yaw.is_moving() or self._pitch.is_moving()

    def get_current_angles(self):
        return (self._yaw.get_current_angle(), self._pitch.get_current_angle())

    def get_current_yaw_angle(self):
        return self._yaw.get_current_angle()

    def get_current_pitch_angle(self):
        return self._pitch.get_current_angle()

    def set_torque_enabled(self, enabled):
        self._yaw.set_torque_enabled(enabled)
        self._pitch.set_torque_enabled(enabled)

    def set_auto_torque_release_enabled(self, enabled):
        self._yaw.set_auto_torque_release_enabled(enabled)
        self._pitch.set_auto_torque_release_enabled(enabled)

    def set_auto_angle_sync_enabled(self, enabled):
        self._yaw.set_auto_angle_sync_enabled(enabled)
        self._pitch.set_auto_angle_sync_enabled(enabled)

    def set_modify_lock(self, locked):
        self._is_modify_locked = locked

    def is_modify_locked(self):
        return self._is_modify_locked


def create_default_motion():
    """Build the yaw/pitch pair like Hal::servo_init()."""
    yaw = UiflowServo(1, YAW_ANGLE_LIMIT, ui_scale=1.0)
    pitch = UiflowServo(2, PITCH_ANGLE_LIMIT, ui_scale=0.5, ui_limit=(0, 90))
    motion = Motion(yaw, pitch)
    motion.init()
    return motion