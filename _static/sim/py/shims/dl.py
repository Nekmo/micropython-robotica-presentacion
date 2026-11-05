"""dl shim (ESP-DL in UIFlow CoreS3).

The simulator has no neural network. Instead, a virtual person walks
slowly from side to side in front of the robot: ``infer()`` draws a
cartoon face where that person would appear in the camera, given where
the head is looking, and reports it as a detection. So a face-tracking
program really closes the loop: if the head does not follow, the face
leaves the picture.
"""

import math

from stackchan_sim import bridge as _bridge_mod
from stackchan_sim.compat import monotonic as _mono

_PX_PER_DEG = 320 / 60          # GC0308: about 60 degrees across 320 px
_SIZE = 70                      # face box, in pixels


class model:
    HUMAN_FACE_DETECT = 0
    PEDESTRIAN_DETECT = 1
    CAT_DETECT = 2


class DetectionResult:
    def __init__(self, x, y, w, h):
        self._box = (int(x), int(y), int(w), int(h))

    def bbox(self):
        return self._box

    def x(self):
        return self._box[0]

    def y(self):
        return self._box[1]

    def w(self):
        return self._box[2]

    def h(self):
        return self._box[3]

    def category(self):
        return 0

    def keypoint(self):
        x, y, w, h = self._box
        return (x + w * 3 // 10, y + h * 4 // 10, x + w * 35 // 100, y + h * 3 // 4,
                x + w // 2, y + h * 6 // 10, x + w * 7 // 10, y + h * 4 // 10,
                x + w * 65 // 100, y + h * 3 // 4)


class ObjectDetector:
    def __init__(self, model_id):
        _bridge_mod.get().log(
            "dl: simulador sin red neuronal, se simula una persona que se mueve", "warn")
        self._t0 = _mono()

    def infer(self, img):
        t = _mono() - self._t0
        person = 35 * math.sin(t * 0.45)                     # degrees, + to the right
        head = 180 - _bridge_mod.get().state.servos[1].current()
        cx = 160 + (person - head) * _PX_PER_DEG
        cy = 110 + 10 * math.sin(t * 0.9)
        if not -_SIZE / 2 < cx < 320 + _SIZE / 2:
            return []
        x, y = cx - _SIZE / 2, cy - _SIZE / 2
        if img is not None:                                  # a cartoon face to look at
            img.draw_circle(cx, cy, _SIZE // 2, 0xFFC44D, fill=True)
            img.draw_circle(cx - 12, cy - 8, 5, 0x1F2A44, fill=True)
            img.draw_circle(cx + 12, cy - 8, 5, 0x1F2A44, fill=True)
            img.draw_line(cx - 12, cy + 14, cx + 12, cy + 14, 0x1F2A44)
        return [DetectionResult(max(0, x), y, _SIZE, _SIZE)]
