"""Port of stackchan/json (remote-control message parsing).

Message shapes are identical to the original firmware so existing
Stack-chan controller payloads work unchanged:

Avatar:  {"leftEye": {"x":0,"y":0,"rotation":0,"weight":100,"size":0},
          "rightEye": {...}, "mouth": {...}}
Motion:  {"yawServo": {"angle":0,"speed":500}|{"rotate":500}|
                       {"angle":0,"spring":{"stiffness":170,"damping":26}},
          "pitchServo": {...}}
Neon:    {"leftRgbColor":"#FF0000","leftRgbDuration":0.5,
          "rightRgbColor":"...","rightRgbDuration":...}
Dance:   [ {keyframe}, ... ]  (see animation.py)
"""

import json

from .animation import Keyframe, FeatureKeyframe, ServoKeyframe


def _loads(content):
    if isinstance(content, (dict, list)):
        return content
    try:
        return json.loads(content)
    except (ValueError, TypeError):
        print('[json] deserialize failed')
        return None


def _update_feature(feature, obj):
    if isinstance(obj.get('x'), int) and isinstance(obj.get('y'), int):
        feature.set_position(obj['x'], obj['y'])
    if isinstance(obj.get('rotation'), int):
        feature.set_rotation(obj['rotation'])
    if isinstance(obj.get('weight'), int):
        feature.set_weight(obj['weight'])
    if isinstance(obj.get('size'), int):
        feature.set_size(obj['size'])


def update_avatar_from_json(avatar, content):
    doc = _loads(content)
    if avatar is None or not isinstance(doc, dict):
        return
    if isinstance(doc.get('leftEye'), dict):
        _update_feature(avatar.left_eye(), doc['leftEye'])
    if isinstance(doc.get('rightEye'), dict):
        _update_feature(avatar.right_eye(), doc['rightEye'])
    if isinstance(doc.get('mouth'), dict):
        _update_feature(avatar.mouth(), doc['mouth'])


def _update_servo(servo, obj):
    if isinstance(obj.get('rotate'), int):
        servo.rotate(obj['rotate'])
        return
    angle = obj.get('angle')
    if not isinstance(angle, int):
        return
    speed = obj.get('speed')
    if isinstance(speed, int):
        servo.move_with_speed(angle, speed)
        return
    spring = obj.get('spring')
    if isinstance(spring, dict):
        stiffness = float(spring.get('stiffness', 170.0))
        damping = float(spring.get('damping', 26.0))
        servo.move_with_spring_params(angle, stiffness, damping)
        return
    servo.move(angle)


def update_motion_from_json(motion, content):
    doc = _loads(content)
    if motion is None or not isinstance(doc, dict):
        return
    if isinstance(doc.get('yawServo'), dict):
        _update_servo(motion.yaw_servo(), doc['yawServo'])
    if isinstance(doc.get('pitchServo'), dict):
        _update_servo(motion.pitch_servo(), doc['pitchServo'])


def update_neon_light_from_json(left, right, content):
    doc = _loads(content)
    if not isinstance(doc, dict):
        return
    if 'leftRgbDuration' in doc:
        left.set_duration(doc['leftRgbDuration'])
    if isinstance(doc.get('leftRgbColor'), str):
        left.set_color(doc['leftRgbColor'])
    if 'rightRgbDuration' in doc:
        right.set_duration(doc['rightRgbDuration'])
    if isinstance(doc.get('rightRgbColor'), str):
        right.set_color(doc['rightRgbColor'])


def _parse_feature(obj):
    return FeatureKeyframe(
        obj.get('x', 0), obj.get('y', 0), obj.get('rotation', 0),
        obj.get('weight', 0), obj.get('size', 0))


def _parse_servo(obj):
    return ServoKeyframe(obj.get('angle', 0), obj.get('speed', 0))


def parse_sequence_from_json(content):
    doc = _loads(content)
    sequence = []
    if not isinstance(doc, list):
        return sequence
    for kf_obj in doc:
        if not isinstance(kf_obj, dict):
            continue
        sequence.append(Keyframe(
            _parse_feature(kf_obj.get('leftEye', {})),
            _parse_feature(kf_obj.get('rightEye', {})),
            _parse_feature(kf_obj.get('mouth', {})),
            _parse_servo(kf_obj.get('yawServo', {})),
            _parse_servo(kf_obj.get('pitchServo', {})),
            kf_obj.get('durationMs', 0),
            kf_obj.get('leftRgbColor', ''),
            kf_obj.get('rightRgbColor', ''),
        ))
    return sequence