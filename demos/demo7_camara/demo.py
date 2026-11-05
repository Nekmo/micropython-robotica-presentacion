# Challenge 3b: what Stack-chan sees (GC0308 camera); tap the screen for a photo
import time
import camera
import M5

camera.init(pixformat=camera.RGB565, framesize=camera.QVGA)
photos, touching = 0, False

while True:
    M5.update()                                # refresh the touch screen
    img = camera.snapshot()
    M5.Lcd.show(img, 0, 0, 320, 240)
    pressed = M5.Touch.getCount() > 0          # a finger on the screen?
    if pressed and not touching:               # only once per tap
        photos += 1
        print("📸 foto %d (320×240)" % photos)
        M5.Speaker.tone(1800, 60)
        time.sleep_ms(2000)                    # freeze the picture
    touching = pressed
