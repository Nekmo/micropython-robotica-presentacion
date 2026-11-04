# Challenge 5a: on-device AI, follow the nearest face (ESP-DL)
import camera
import dl
import M5
from hardware.stackchan import StackChan

M5.begin()
camera.init(pixformat=camera.RGB565, framesize=camera.QVGA)
detector = dl.ObjectDetector(dl.model.HUMAN_FACE_DETECT)

robot = StackChan(i2c=1, uart=1)
robot.set_servo_power(True)
X, Y = robot.SERVO_ID_X, robot.SERVO_ID_Y
yaw, pitch = robot.get_servo_angle(X), robot.get_servo_angle(Y)

while True:
    img = camera.snapshot()
    faces = detector.infer(img) or []
    if faces:
        x, y, w, h = faces[0].box()             # biggest face first
        err_x = (x + w / 2) - 160               # pixels from the centre
        err_y = (y + h / 2) - 120
        yaw -= err_x * 0.05                     # proportional control
        pitch += err_y * 0.03
        robot.set_servo_angle(X, yaw, 60)
        robot.set_servo_angle(Y, pitch, 60)
        img.draw_rectangle(x, y, w, h, color=0xFF4F9A)
    robot.set_rgb_color(0x39D0D8 if faces else 0)
    M5.Lcd.show(img, 0, 0, 320, 240)
