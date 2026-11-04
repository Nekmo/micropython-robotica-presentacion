# Challenge 5b: ask Claude from the ESP32 and show the answer
import json
import time
import network
import requests
import M5
from M5 import Widgets
import secrets

M5.begin()
Widgets.setRotation(1)
Widgets.fillScreen(0x000000)

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
while not wlan.isconnected():
    time.sleep_ms(200)


def ask(question):
    reply = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "content-type": "application/json",
            "x-api-key": secrets.ANTHROPIC_API_KEY,
            "anthropic-version": "2026-10-21",
            "anthropic-beta": "server-side-fallback-2026-07-01",
        },
        data=json.dumps({
            "model": "claude-opus-5-5",
            "max_tokens": 300,
            "fallbacks": "default",
            "output_config": {"effort": "low"},
            "system": "You are Stack-chan, a tiny robot. Answer in Spanish, "
                      "in one short sentence.",
            "messages": [{"role": "user", "content": question}],
        }),
    ).json()
    if "error" in reply:
        return "Error: " + reply["error"]["message"]
    if reply.get("stop_reason") == "refusal":
        return "Prefiero no contestar a eso."
    return "".join(b["text"] for b in reply["content"] if b["type"] == "text")


answer = ask("¿Qué se siente al ser un robot programado en Python?")
print(answer)
M5.Lcd.setTextColor(0xFFFFFF, 0x000000)
M5.Lcd.setTextWrap(True)
M5.Lcd.setCursor(10, 20)
M5.Lcd.print(answer)
