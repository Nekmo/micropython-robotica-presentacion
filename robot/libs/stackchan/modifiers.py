"""Port of stackchan/modifiers (behaviour layer on top of the avatar).

Every modifier's ``_update(stackchan)`` runs each loop; a modifier can
schedule its own removal with ``request_destroy()``.
"""

import lvgl as lv

from .pool import Poolable
from .uitk import clamp, Random
from .hal import (get_hal, GESTURE_SWIPE_FORWARD, GESTURE_SWIPE_BACKWARD,
                  GESTURE_RELEASE, IMU_EVENT_SHAKE)
from . import avatar as av
from .animation import Timeline


class Modifier(Poolable):
    def __init__(self):
        Poolable.__init__(self)
        self._hal = get_hal()

    def _update(self, stackchan):
        pass

    def on_destroy(self):
        pass


# ------------------------------------------------------------------- blink

class BlinkModifier(Modifier):
    def __init__(self, destroy_after_ms=0, open_interval_ms=5200,
                 close_interval_ms=200):
        Modifier.__init__(self)
        self._open_interval_ms = open_interval_ms
        self._close_interval_ms = close_interval_ms
        now = self._hal.millis()
        self._has_lifetime = destroy_after_ms > 0
        self._destroy_at = now + destroy_after_ms
        self._is_open = True
        self._next_state_tick = now + open_interval_ms
        self._needs_resync = False
        self._left_eye_weight = 100
        self._right_eye_weight = 100

    def resync_eye_weights(self):
        self._needs_resync = True

    def _update(self, stackchan):
        if not stackchan.has_avatar() or stackchan.avatar().is_modify_locked():
            return

        now = self._hal.millis()

        if self._has_lifetime and now >= self._destroy_at:
            if not self._is_open:
                self._apply(stackchan, self._left_eye_weight,
                            self._right_eye_weight)
            self.request_destroy()
            return

        if self._needs_resync:
            self._needs_resync = False
            self._left_eye_weight = stackchan.avatar().left_eye().get_weight()
            self._right_eye_weight = stackchan.avatar().right_eye().get_weight()

        if now >= self._next_state_tick:
            if self._is_open:
                self._is_open = False
                self._next_state_tick = now + self._close_interval_ms
                self._left_eye_weight = stackchan.avatar().left_eye().get_weight()
                self._right_eye_weight = stackchan.avatar().right_eye().get_weight()
                self._apply(stackchan, 25, 25)
            else:
                self._is_open = True
                jitter = Random.get_instance().get_int(0, 500)
                self._next_state_tick = now + self._open_interval_ms + jitter
                self._apply(stackchan, self._left_eye_weight,
                            self._right_eye_weight)

    @staticmethod
    def _apply(stackchan, left, right):
        stackchan.avatar().left_eye().set_weight(left)
        stackchan.avatar().right_eye().set_weight(right)


# ------------------------------------------------------------------ breath

class BreathModifier(Modifier):
    def __init__(self, destroy_after_ms=0, amplitude=16,
                 breath_cycle_ms=6600, update_interval_ms=600):
        Modifier.__init__(self)
        import math
        self._math = math
        self._amplitude = amplitude
        self._breath_cycle_ms = breath_cycle_ms
        self._update_interval_ms = update_interval_ms
        self._start_tick = self._hal.millis()
        self._has_lifetime = destroy_after_ms > 0
        self._destroy_at = self._start_tick + destroy_after_ms
        self._last_update_tick = 0
        self._last_applied_offset = 0

    def _update(self, stackchan):
        if not stackchan.has_avatar():
            return

        now = self._hal.millis()

        if self._has_lifetime and now >= self._destroy_at:
            self._apply_offset(stackchan.avatar(), 0)
            self.request_destroy()
            return

        if now - self._last_update_tick < self._update_interval_ms:
            return
        self._last_update_tick = now

        phase = ((now - self._start_tick) % self._breath_cycle_ms) \
            / self._breath_cycle_ms
        offset = int(self._math.sin(phase * 2.0 * self._math.pi)
                     * self._amplitude)
        self._apply_offset(stackchan.avatar(), offset)

    def _apply_offset(self, avatar, new_offset):
        delta = new_offset - self._last_applied_offset
        if delta == 0:
            return
        for feature in (avatar.left_eye(), avatar.right_eye(), avatar.mouth()):
            x, y = feature.get_position()
            feature.set_position(x, y + delta)
        self._last_applied_offset = new_offset


# ---------------------------------------------------------------- speaking

class SpeakingModifier(Modifier):
    OPEN_MIN_WEIGHT = 40
    OPEN_MAX_WEIGHT = 80
    CLOSE_MIN_WEIGHT = 0
    CLOSE_MAX_WEIGHT = 20

    def __init__(self, destroy_after_ms=0, mouth_interval_ms=180,
                 enable_motion=True):
        Modifier.__init__(self)
        self._mouth_interval_ms = mouth_interval_ms
        self._enable_motion = enable_motion
        now = self._hal.millis()
        self._has_lifetime = destroy_after_ms > 0
        self._destroy_at = now + destroy_after_ms
        self._next_mouth_tick = now + mouth_interval_ms
        self._next_motion_tick = now + Random.get_instance().get_int(1000, 2000)
        self._is_mouth_open = False
        self._need_get_prev_angles = True
        self._prev_angles = (0, 0)

    def _update(self, stackchan):
        if not stackchan.has_avatar():
            return

        now = self._hal.millis()

        if self._has_lifetime and now >= self._destroy_at:
            stackchan.avatar().mouth().set_weight(0)
            self.request_destroy()
            return

        if now >= self._next_mouth_tick:
            self._next_mouth_tick = now + self._mouth_interval_ms
            self._animate_mouth(stackchan.avatar())

        if self._enable_motion and now >= self._next_motion_tick:
            self._next_motion_tick = now + Random.get_instance().get_int(1500, 2500)
            self._perform_motion(stackchan)

    def _animate_mouth(self, avatar):
        self._is_mouth_open = not self._is_mouth_open
        random = Random.get_instance()
        if self._is_mouth_open:
            weight = random.get_int(self.OPEN_MIN_WEIGHT, self.OPEN_MAX_WEIGHT)
        else:
            weight = random.get_int(self.CLOSE_MIN_WEIGHT, self.CLOSE_MAX_WEIGHT)
        avatar.mouth().set_weight(weight)

    def _perform_motion(self, stackchan):
        motion = stackchan.motion()
        if motion is None or motion.is_moving():
            return

        current = motion.get_current_angles()
        if self._need_get_prev_angles:
            self._prev_angles = current
            self._need_get_prev_angles = False
        else:
            # Re-sync baseline after large external movements
            if abs(current[0] - self._prev_angles[0]) > 300 or \
                    abs(current[1] - self._prev_angles[1]) > 300:
                self._prev_angles = current

        random = Random.get_instance()
        target_yaw, target_pitch = self._prev_angles
        speed = random.get_int(100, 200)

        if random.get_int(0, 10) < 5:
            target_pitch += random.get_int(-20, 50)      # nod
        else:
            target_yaw += random.get_int(-40, 40)        # yaw drift
            target_pitch += random.get_int(-20, 20)

        motion.move_with_speed(target_yaw, target_pitch, speed)


# ---------------------------------------------------------- idle expression

class IdleExpressionModifier(Modifier):
    def __init__(self, interval_min=2000, interval_max=6000):
        Modifier.__init__(self)
        self._interval_min = interval_min
        self._interval_max = interval_max
        self._next_tick = self._hal.millis() + 500

    def _update(self, stackchan):
        if not stackchan.has_avatar() or stackchan.avatar().is_modify_locked():
            return
        now = self._hal.millis()
        if now < self._next_tick:
            return
        self._perform(stackchan.avatar())
        self._next_tick = now + Random.get_instance().get_int(
            self._interval_min, self._interval_max)

    @staticmethod
    def _perform(avatar):
        random = Random.get_instance()
        action = random.get_int(0, 100)

        if action < 70:
            # wandering gaze
            offset_x = random.get_int(-20, 20)
            offset_y = random.get_int(-15, 15)
            avatar.left_eye().set_position(offset_x, offset_y)
            avatar.right_eye().set_position(offset_x, offset_y)
            avatar.mouth().set_position(0, random.get_int(0, 10))
        elif action < 80:
            # mouth tilt
            rotation = random.get_int(-30, 30)
            avatar.mouth().set_rotation(3600 + rotation if rotation < 0 else rotation)
        else:
            # back to neutral
            avatar.left_eye().set_position(0, 0)
            avatar.right_eye().set_position(0, 0)
            avatar.mouth().set_position(0, 0)
            avatar.left_eye().set_size(0)
            avatar.right_eye().set_size(0)
            avatar.mouth().set_rotation(0)
            avatar.mouth().set_weight(0)


# -------------------------------------------------------------- idle motion

class IdleMotionModifier(Modifier):
    def __init__(self, interval_min=4000, interval_max=8000):
        Modifier.__init__(self)
        self._interval_min = interval_min
        self._interval_max = interval_max
        self._next_tick = self._hal.millis() + 1000
        self._paused = False

    def pause(self):
        self._paused = True

    def resume(self):
        if self._paused:
            self._paused = False
            self._next_tick = self._hal.millis() + 500

    def _update(self, stackchan):
        if self._paused or not stackchan.has_avatar():
            return
        now = self._hal.millis()
        if now < self._next_tick:
            return
        motion = stackchan.motion()
        if motion is None:
            return
        if motion.is_moving():
            self._next_tick = now + 500
            return
        self._perform(motion)
        self._next_tick = now + Random.get_instance().get_int(
            self._interval_min, self._interval_max)

    @staticmethod
    def _perform(motion):
        if motion.is_modify_locked():
            return

        random = Random.get_instance()
        action = random.get_int(0, 100)

        if action < 50:
            # look somewhere (normalized)
            target_x = random.get_float(-0.4, 0.4)
            target_y = random.get_float(-0.95, 0.2)
            speed = random.get_int(150, 300)
            motion.look_at_normalized(target_x, target_y, speed)
        elif action < 80:
            # small observation move
            current = motion.get_current_angles()
            target_yaw = clamp(current[0] + random.get_int(-150, 150), -800, 800)
            target_pitch = clamp(current[1] + random.get_int(-80, 80), 0, 600)
            motion.move_with_speed(target_yaw, target_pitch,
                                   random.get_int(100, 250))
        elif action < 90:
            # quick glance
            motion.move_with_speed(random.get_int(-500, 500),
                                   random.get_int(100, 400),
                                   random.get_int(250, 400))
        else:
            # yaw back home
            motion.move_with_speed(0, random.get_int(50, 400),
                                   random.get_int(100, 300))


# ----------------------------------------------------------------- head pet

class HeadPetModifier(Modifier):
    def __init__(self, restore_delay_ms=3000):
        Modifier.__init__(self)
        self._restore_delay_ms = restore_delay_ms
        self._event_swipe = False
        self._event_release = False
        self._in_happy_state = False
        self._is_waiting_restore = False
        self._restore_tick = 0
        self._heart_decorator_id = -1
        self._shy_decorator_id = -1
        self._prev_emotion = av.EMOTION_NEUTRAL
        self._prev_yaw = 0
        self._prev_pitch = 0
        self._signal_connection = self._hal.on_head_pet_gesture.connect(
            self._on_gesture)

    def _on_gesture(self, gesture):
        if gesture in (GESTURE_SWIPE_FORWARD, GESTURE_SWIPE_BACKWARD):
            self._event_swipe = True
        elif gesture == GESTURE_RELEASE:
            self._event_release = True

    def on_destroy(self):
        self._hal.on_head_pet_gesture.disconnect(self._signal_connection)

    def _update(self, stackchan):
        now = self._hal.millis()

        if self._event_swipe:
            self._event_swipe = False
            self._handle_swipe(stackchan)
            self._is_waiting_restore = False

        if self._event_release:
            self._event_release = False
            if self._in_happy_state:
                self._is_waiting_restore = True
                self._restore_tick = now + self._restore_delay_ms

        if self._is_waiting_restore and now >= self._restore_tick:
            self._is_waiting_restore = False
            self._restore(stackchan)

    def _handle_swipe(self, stackchan):
        if not stackchan.has_avatar():
            return
        avatar = stackchan.avatar()

        if not self._in_happy_state:
            self._in_happy_state = True
            self._prev_emotion = avatar.get_emotion()
            motion = stackchan.motion()
            if motion is not None:
                self._prev_yaw, self._prev_pitch = motion.get_current_angles()

        avatar.set_emotion(av.EMOTION_HAPPY)

        from .decorators import HeartDecorator, ShyDecorator
        duration = Random.get_instance().get_int(1500, 2500)
        avatar.remove_decorator(self._heart_decorator_id)
        avatar.remove_decorator(self._shy_decorator_id)
        parent = lv.screen_active()
        self._heart_decorator_id = avatar.add_decorator(
            HeartDecorator(parent, duration, 500))
        self._shy_decorator_id = avatar.add_decorator(
            ShyDecorator(parent, duration))

        self._perform_pet_motion(stackchan)

    def _restore(self, stackchan):
        if not self._in_happy_state:
            return
        if stackchan.has_avatar():
            stackchan.avatar().set_emotion(self._prev_emotion)
        motion = stackchan.motion()
        if motion is not None:
            motion.move_with_speed(self._prev_yaw, self._prev_pitch, 200)
        self._in_happy_state = False

    def _perform_pet_motion(self, stackchan):
        motion = stackchan.motion()
        if motion is None or motion.is_modify_locked() or motion.is_moving():
            return

        random = Random.get_instance()
        action = random.get_int(0, 2)
        speed = random.get_int(300, 500)
        target_yaw = self._prev_yaw
        target_pitch = self._prev_pitch

        if action == 0:      # raise head
            target_pitch += random.get_int(150, 250)
            target_yaw += random.get_int(-50, 50)
        elif action == 1:    # tilt head
            target_pitch -= random.get_int(0, 50)
            target_yaw += 150 if random.get_int(0, 1) == 0 else -150
        else:                # big happy
            target_pitch += random.get_int(250, 400)

        target_pitch = clamp(target_pitch, 0, 540)
        target_yaw = clamp(target_yaw, -512, 512)
        motion.move_with_speed(target_yaw, target_pitch, speed)


# ---------------------------------------------------------------- imu shake

class ImuEventModifier(Modifier):
    def __init__(self, reaction_duration_ms=4000):
        Modifier.__init__(self)
        self._reaction_duration_ms = reaction_duration_ms
        self._event_shake = False
        self._is_reacting = False
        self._toggle_phase = False
        self._restore_at = 0
        self._next_toggle_tick = 0
        self._dizzy_decorator_id = -1
        self._shy_decorator_id = -1
        self._signal_connection = self._hal.on_imu_motion_event.connect(
            self._on_event)

    def _on_event(self, event):
        if event == IMU_EVENT_SHAKE:
            self._event_shake = True

    def on_destroy(self):
        self._hal.on_imu_motion_event.disconnect(self._signal_connection)

    def _update(self, stackchan):
        now = self._hal.millis()

        if self._event_shake:
            self._event_shake = False
            self._handle_shake_start(stackchan, now)

        if self._is_reacting:
            if now >= self._next_toggle_tick:
                self._next_toggle_tick = now + 600
                self._toggle_phase = not self._toggle_phase
                mouth_rotation = -25 if self._toggle_phase else 25
                if stackchan.has_avatar():
                    mouth = stackchan.avatar().mouth()
                    mouth.set_rotation(3600 + mouth_rotation
                                       if mouth_rotation < 0 else mouth_rotation)
                    mouth.set_weight(65)

            motion = stackchan.motion()
            if motion is not None and not motion.is_modify_locked():
                motion.set_modify_lock(True)
                motion.go_home(300)

            if now >= self._restore_at:
                self._restore(stackchan)

    def _handle_shake_start(self, stackchan, now):
        if not stackchan.has_avatar():
            return
        if not self._is_reacting:
            self._is_reacting = True
            avatar = stackchan.avatar()
            avatar.set_modify_lock(True)
            avatar.left_eye().set_visible(False)
            avatar.right_eye().set_visible(False)

            from .decorators import DizzyDecorator, ShyDecorator
            avatar.remove_decorator(self._dizzy_decorator_id)
            avatar.remove_decorator(self._shy_decorator_id)
            parent = lv.screen_active()
            self._dizzy_decorator_id = avatar.add_decorator(
                DizzyDecorator(parent, 0, 300))
            self._shy_decorator_id = avatar.add_decorator(
                ShyDecorator(parent, 0))

        self._restore_at = now + self._reaction_duration_ms
        if self._next_toggle_tick <= now:
            self._next_toggle_tick = now

    def _restore(self, stackchan):
        if not self._is_reacting:
            return
        avatar = stackchan.avatar()
        avatar.set_modify_lock(False)
        avatar.left_eye().set_visible(True)
        avatar.right_eye().set_visible(True)
        avatar.mouth().set_weight(0)
        avatar.mouth().set_rotation(0)

        avatar.remove_decorator(self._dizzy_decorator_id)
        avatar.remove_decorator(self._shy_decorator_id)
        self._dizzy_decorator_id = -1
        self._shy_decorator_id = -1

        motion = stackchan.motion()
        if motion is not None:
            motion.set_modify_lock(False)
        self._is_reacting = False


# -------------------------------------------------------------- timed events

class TimedEventModifier(Modifier):
    def __init__(self, duration_ms):
        Modifier.__init__(self)
        self._duration_ms = duration_ms
        self._start_time = 0
        self._is_started = False

    def _update(self, stackchan):
        now = self._hal.millis()
        if not self._is_started:
            self._is_started = True
            self._start_time = now
            self._on_start(stackchan)
            if self._duration_ms == 0:
                self._on_end(stackchan)
                self.request_destroy()
            return
        if now - self._start_time >= self._duration_ms:
            self._on_end(stackchan)
            self.request_destroy()

    def _on_start(self, stackchan):
        pass

    def _on_end(self, stackchan):
        pass


class TimedEmotionModifier(TimedEventModifier):
    def __init__(self, emotion, duration_ms):
        TimedEventModifier.__init__(self, duration_ms)
        self._target_emotion = emotion
        self._prev_emotion = av.EMOTION_NEUTRAL

    def _on_start(self, stackchan):
        if not stackchan.has_avatar():
            return
        self._prev_emotion = stackchan.avatar().get_emotion()
        stackchan.avatar().set_emotion(self._target_emotion)

    def _on_end(self, stackchan):
        if not stackchan.has_avatar():
            return
        stackchan.avatar().set_emotion(self._prev_emotion)


class TimedSpeechModifier(TimedEventModifier):
    def __init__(self, speech, duration_ms):
        TimedEventModifier.__init__(self, duration_ms)
        self._target_speech = speech

    def _on_start(self, stackchan):
        if not stackchan.has_avatar():
            return
        stackchan.avatar().set_speech(self._target_speech)

    def _on_end(self, stackchan):
        if not stackchan.has_avatar():
            return
        stackchan.avatar().clear_speech()


# -------------------------------------------------------------------- dance

class DanceModifier(Modifier):
    def __init__(self, sequence):
        Modifier.__init__(self)
        self._timeline = Timeline(sequence, False)
        self._started = False

    def _update(self, stackchan):
        if not self._started:
            self._started = True
            self._timeline.bind(stackchan)
            self._timeline.start()
        self._timeline.update()
        if self._timeline.is_finished():
            self.request_destroy()