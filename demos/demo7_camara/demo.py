# Challenge 3b: what Stack-chan sees (GC0308 camera)
import camera
import M5

M5.begin()
camera.init(pixformat=camera.RGB565, framesize=camera.QVGA)

while True:
    M5.update()
    img = camera.snapshot()
    M5.Lcd.show(img, 0, 0, 320, 240)
    if M5.Touch.getCount():
        print("Click!")
