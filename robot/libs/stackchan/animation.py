"""Port of stackchan/animation (Keyframe + Timeline).

Keyframes drive avatar features, servos and the neon strips; a Timeline
steps through them by duration, optionally looping.
"""

from .hal import get_hal

STATUS_IDLE = 0
STATUS_PLAYING = 1
STATUS_PAUSED = 2
STATUS_FINISHED = 3


class FeatureKeyframe(object):
    def __init__(self, x=0, y=0, rotation=0, weight=0, size=0):
        self.x = x
        self.y = y
        self.rotation = rotation
        self.weight = weight
        self.size = size


class ServoKeyframe(object):
    def __init__(self, angle=0, speed=0):
        self.angle = angle
        self.speed = speed


class Keyframe(object):
    def __init__(self, left_eye=None, right_eye=None, mouth=None,
                 yaw_servo=None, pitch_servo=None, duration_ms=0,
                 left_rgb_color='', right_rgb_color=''):
        self.left_eye = left_eye or FeatureKeyframe()
        self.right_eye = right_eye or FeatureKeyframe()
        self.mouth = mouth or FeatureKeyframe()
        self.yaw_servo = yaw_servo or ServoKeyframe()
        self.pitch_servo = pitch_servo or ServoKeyframe()
        self.left_rgb_color = left_rgb_color
        self.right_rgb_color = right_rgb_color
        self.duration_ms = duration_ms

    def apply(self, stackchan):
        if stackchan.has_avatar():
            avatar = stackchan.avatar()

            def apply_feature(kf, feature):
                feature.set_position(kf.x, kf.y)
                feature.set_rotation(kf.rotation)
                feature.set_weight(kf.weight)
                feature.set_size(kf.size)

            apply_feature(self.left_eye, avatar.left_eye())
            apply_feature(self.right_eye, avatar.right_eye())
            apply_feature(self.mouth, avatar.mouth())

        motion = stackchan.motion()
        if motion is not None:
            motion.yaw_servo().move_with_speed(self.yaw_servo.angle,
                                               self.yaw_servo.speed)
            motion.pitch_servo().move_with_speed(self.pitch_servo.angle,
                                                 self.pitch_servo.speed)

        stackchan.left_neon_light().set_color(self.left_rgb_color)
        stackchan.right_neon_light().set_color(self.right_rgb_color)


def kf(left_eye, right_eye, mouth, yaw, pitch, duration_ms,
       left_rgb='', right_rgb=''):
    """Compact keyframe builder mirroring the C++ initializer lists.

    ``left_eye/right_eye/mouth`` are (x, y, rotation, weight) tuples,
    ``yaw/pitch`` are (angle, speed) tuples.
    """
    return Keyframe(
        FeatureKeyframe(*left_eye),
        FeatureKeyframe(*right_eye),
        FeatureKeyframe(*mouth),
        ServoKeyframe(*yaw),
        ServoKeyframe(*pitch),
        duration_ms,
        left_rgb, right_rgb,
    )


class Timeline(object):
    def __init__(self, keyframe_sequence, loop=False):
        self._sequence = list(keyframe_sequence)
        self._loop = loop
        self._current_index = 0
        self._status = STATUS_IDLE
        self._start_time = 0
        self._elapsed_time = 0
        self._hal = get_hal()
        self._stackchan = None

    def bind(self, stackchan):
        self._stackchan = stackchan

    def start(self):
        if not self._sequence:
            self._status = STATUS_FINISHED
            return
        self._current_index = 0
        self._status = STATUS_PLAYING
        self._start_time = self._hal.millis()
        self._apply_current()

    def stop(self):
        self._status = STATUS_IDLE
        self._current_index = 0

    def pause(self):
        if self._status == STATUS_PLAYING:
            self._status = STATUS_PAUSED
            self._elapsed_time = self._hal.millis() - self._start_time

    def resume(self):
        if self._status == STATUS_PAUSED:
            self._status = STATUS_PLAYING
            self._start_time = self._hal.millis() - self._elapsed_time

    def update(self):
        if self._status != STATUS_PLAYING:
            return
        if not self._sequence:
            self._status = STATUS_FINISHED
            return
        now = self._hal.millis()
        if now - self._start_time >= self._sequence[self._current_index].duration_ms:
            self._current_index += 1
            if self._current_index >= len(self._sequence):
                if self._loop:
                    self._current_index = 0
                else:
                    self._status = STATUS_FINISHED
                    return
            self._start_time = now
            self._apply_current()

    def get_status(self):
        return self._status

    def is_finished(self):
        return self._status == STATUS_FINISHED

    def set_loop(self, loop):
        self._loop = loop

    def _apply_current(self):
        if self._stackchan is None:
            from . import get_stackchan
            self._stackchan = get_stackchan()
        if self._current_index < len(self._sequence):
            self._sequence[self._current_index].apply(self._stackchan)


# ------------------------------------------------------------------ dances
# Built-in sequences from modifiers/dance.h (identical keyframe values).

DANCE_HAPPY = [
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 0), (0, 200), (0, 200), 500),
    kf((-10, 0, 0, 50), (-10, 0, 0, 50), (0, 0, 0, 50), (300, 200), (-100, 200), 800),
    kf((10, 0, 0, 50), (10, 0, 0, 50), (0, 0, 0, 50), (-300, 200), (-100, 200), 800),
    kf((-10, 0, 0, 50), (-10, 0, 0, 50), (0, 0, 0, 50), (300, 200), (-100, 200), 800),
    kf((10, 0, 0, 50), (10, 0, 0, 50), (0, 0, 0, 50), (-300, 200), (-100, 200), 800),
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 0), (0, 200), (0, 200), 500),
]

DANCE_ROBOT = [
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 0), (0, 500), (0, 500), 500),
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 0), (450, 800), (0, 800), 400),
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 0), (450, 800), (200, 800), 400),
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 0), (-450, 800), (200, 800), 600),
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 0), (-450, 800), (0, 800), 400),
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 0), (0, 800), (0, 800), 400),
]

DANCE_PANIC = [
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 100), (0, 1000), (0, 1000), 100),
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 100), (200, 1000), (100, 1000), 100),
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 100), (-200, 1000), (-100, 1000), 100),
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 100), (200, 1000), (100, 1000), 100),
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 100), (-200, 1000), (-100, 1000), 100),
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 100), (200, 1000), (100, 1000), 100),
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 0), (0, 200), (0, 200), 500),
]

DANCE_LOOK_AROUND = [
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 0), (0, 200), (0, 200), 1000),
    kf((-20, 0, 0, 100), (-20, 0, 0, 100), (0, 0, 0, 20), (600, 150), (0, 150), 2000),
    kf((20, 0, 0, 100), (20, 0, 0, 100), (0, 0, 0, 20), (-600, 150), (0, 150), 2000),
    kf((0, -20, 0, 100), (0, -20, 0, 100), (0, 0, 0, 40), (0, 150), (-300, 150), 1500),
    kf((0, 0, 0, 100), (0, 0, 0, 100), (0, 0, 0, 0), (0, 200), (0, 200), 1000),
]