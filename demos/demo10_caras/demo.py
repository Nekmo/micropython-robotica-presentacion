# Challenge 5a: on-device AI, follow the nearest face (ESP-DL)
import camera
import dl
import M5
from machine import UART
from hardware.stackchan import StackChan

StackChan(i2c=1, uart=1).set_servo_power(True)   # Stack-chan: servo power
uart = UART(1, baudrate=1_000_000, tx=6, rx=7)
camera.init(pixformat=camera.RGB565, framesize=camera.QVGA)
detector = dl.ObjectDetector(dl.model.HUMAN_FACE_DETECT)


def turn(steps, ms):                           # head servo (ID 1), as in the bus demo
    body = bytes([1, 9, 0x03, 42, steps >> 8, steps & 0xFF, ms >> 8, ms & 0xFF, 0, 0])
    uart.write(b"\xff\xff" + body + bytes([~sum(body) & 0xFF]))


yaw, seen = 460, False                         # start looking straight ahead
turn(yaw, 1000)
while True:
    img = camera.snapshot()
    faces = detector.infer(img)
    if faces:
        x, y, w, h = faces[0].bbox()           # the biggest face comes first
        error = (x + w // 2) - 160             # pixels from the centre
        if abs(error) > 12:                    # dead zone: do not jitter
            yaw -= max(-8, min(8, error * 0.1))   # proportional, a few steps a frame
            yaw = max(200, min(720, yaw))
            turn(int(yaw), 100)
        img.draw_rectangle(x, y, w, h, color=0xFF4F9A, thickness=3, fill=False)
    if bool(faces) != seen:                    # say it only when it changes
        seen = bool(faces)
        print("¡te veo!" if seen else "¿dónde estás?")
    M5.Lcd.show(img, 0, 0, 320, 240)
