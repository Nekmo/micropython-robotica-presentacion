"""REMOTE app — JSON remote control over TCP.

Stand-in for the original firmware's BLE / WebSocket avatar services:
same message schema (see json_helper), transported as newline-delimited
JSON over a plain TCP socket on port 8321.

Extra top-level keys accepted next to the original ones:
  {"speech": {"text": "hi", "durationMs": 3000}}
  {"emotion": "happy"}
"""

import socket

import lvgl as lv

from .. import get_stackchan
from ..skin_default import DefaultAvatar
from ..avatar import EMOTION_NAMES
from ..modifiers import (BreathModifier, BlinkModifier, DanceModifier,
                         SpeakingModifier, TimedSpeechModifier,
                         TimedEmotionModifier)
from ..json_helper import _loads, parse_sequence_from_json
from . import App, HomeIndicator, TapTracker, in_home_region

PORT = 8321


class AppRemote(App):
    name = 'REMOTE'
    theme_color = 0x7ACE74

    def __init__(self):
        App.__init__(self)
        self._home = None
        self._server = None
        self._client = None
        self._rx = b''
        self._dance_modifier_id = -1
        self._taps = TapTracker()

    # -- lifecycle ------------------------------------------------------
    def on_open(self):
        self._taps.rearm()
        stackchan = get_stackchan()

        avatar = DefaultAvatar()
        avatar.init(lv.screen_active())
        stackchan.attach_avatar(avatar)

        stackchan.clear_modifiers()
        stackchan.add_modifier(BreathModifier())
        stackchan.add_modifier(BlinkModifier())

        # No jitter while being remote controlled (app_espnow_ctrl.cpp)
        motion = stackchan.motion()
        if motion is not None:
            motion.set_auto_angle_sync_enabled(False)

        address = self._start_server()
        if address:
            stackchan.add_modifier(TimedSpeechModifier(
                '%s:%d' % (address, PORT), 8000))
        else:
            stackchan.add_modifier(TimedSpeechModifier('No network!', 5000))

        self._home = HomeIndicator(0xA0D99C)

    def _start_server(self):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except Exception:
                pass
            server.bind(('0.0.0.0', PORT))
            server.listen(1)
            server.setblocking(False)
            self._server = server
        except Exception as exc:
            print('[remote] server failed:', exc)
            self._server = None
            return None
        try:
            import network
            sta = network.WLAN(network.STA_IF)
            if sta.active() and sta.isconnected():
                return sta.ifconfig()[0]
        except Exception:
            pass
        return '0.0.0.0'

    def on_running(self):
        tap = self._taps.poll()
        if tap is not None and in_home_region(tap[0], tap[1]):
            self.close()
            return
        self._poll_network()
        get_stackchan().update()

    def on_close(self):
        stackchan = get_stackchan()
        stackchan.clear_modifiers()
        stackchan.reset_avatar()
        motion = stackchan.motion()
        if motion is not None:
            motion.set_auto_angle_sync_enabled(True)
            motion.go_home(300)
        if self._home is not None:
            self._home.destroy()
            self._home = None
        for sock in (self._client, self._server):
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
        self._client = None
        self._server = None
        self._rx = b''

    # -- protocol ---------------------------------------------------------
    def _poll_network(self):
        if self._server is None:
            return

        if self._client is None:
            try:
                client, _addr = self._server.accept()
                client.setblocking(False)
                self._client = client
                self._rx = b''
            except OSError:
                return

        try:
            data = self._client.recv(512)
        except OSError:
            return
        if data is None:
            return
        if data == b'':
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
            return

        self._rx += data
        while b'\n' in self._rx:
            line, self._rx = self._rx.split(b'\n', 1)
            line = line.strip()
            if line:
                self._handle_message(line)
        if len(self._rx) > 4096:
            self._rx = b''

    def _handle_message(self, raw):
        doc = _loads(raw.decode() if isinstance(raw, bytes) else raw)
        if doc is None:
            return
        stackchan = get_stackchan()

        # A bare list is a dance keyframe sequence (onWsDanceData)
        if isinstance(doc, list):
            self._start_dance(doc)
            return
        if not isinstance(doc, dict):
            return

        if isinstance(doc.get('avatar'), dict):
            stackchan.update_avatar_from_json(doc['avatar'])
        if isinstance(doc.get('motion'), dict):
            stackchan.update_motion_from_json(doc['motion'])
        if isinstance(doc.get('neon'), dict):
            stackchan.update_neon_light_from_json(doc['neon'])
        if isinstance(doc.get('dance'), list):
            self._start_dance(doc['dance'])
        if isinstance(doc.get('speech'), dict):
            speech = doc['speech']
            text = speech.get('text', '')
            duration = int(speech.get('durationMs', 5000))
            stackchan.add_modifier(TimedSpeechModifier(text, duration))
            stackchan.add_modifier(SpeakingModifier(
                min(duration, 2000), 180, False))
        emotion_name = doc.get('emotion')
        if isinstance(emotion_name, str):
            emotion = EMOTION_NAMES.get(emotion_name.lower())
            if emotion is not None:
                duration = int(doc.get('emotionDurationMs', 0))
                if duration > 0:
                    stackchan.add_modifier(
                        TimedEmotionModifier(emotion, duration))
                elif stackchan.has_avatar():
                    stackchan.avatar().set_emotion(emotion)

        # Flat avatar/motion payloads also accepted (original schema)
        if 'leftEye' in doc or 'rightEye' in doc or 'mouth' in doc:
            stackchan.update_avatar_from_json(doc)
        if 'yawServo' in doc or 'pitchServo' in doc:
            stackchan.update_motion_from_json(doc)
        if 'leftRgbColor' in doc or 'rightRgbColor' in doc:
            stackchan.update_neon_light_from_json(doc)

    def _start_dance(self, keyframes):
        stackchan = get_stackchan()
        sequence = parse_sequence_from_json(keyframes)
        if not sequence:
            return
        stackchan.remove_modifier(self._dance_modifier_id)
        self._dance_modifier_id = stackchan.add_modifier(
            DanceModifier(sequence))