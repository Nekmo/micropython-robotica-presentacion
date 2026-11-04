"""dl shim (ESP-DL in UIFlow CoreS3).

The simulator has no neural network: detection results are empty, so
code using ``dl`` runs but nothing is ever detected. Use the robot for
the face-tracking demo.
"""

from stackchan_sim import bridge as _bridge_mod


class model:
    HUMAN_FACE_DETECT = 0
    PEDESTRIAN_DETECT = 1
    CAT_DETECT = 2


class ObjectDetector:
    def __init__(self, model_id):
        _bridge_mod.get().log(
            "dl: no hay modelos en el simulador, la detección devuelve []", "warn")

    def infer(self, img):
        return []
