"""WAV helpers in the common subset (MicroPython has no wave module)."""

import struct


def pcm16_to_wav(pcm_bytes, rate, channels=1):
    """Wrap raw PCM int16 data in a canonical 44-byte WAV header."""
    n = len(pcm_bytes)
    byte_rate = rate * channels * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + n, b"WAVE",
        b"fmt ", 16, 1, channels, rate, byte_rate, channels * 2, 16,
        b"data", n)
    return header + pcm_bytes


def wav_duration_s(data):
    """Duration of a WAV clip in seconds (0.0 if unparseable)."""
    try:
        if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            return 0.0
        pos = 12
        rate = 0
        block_align = 1
        while pos + 8 <= len(data):
            cid = data[pos:pos + 4]
            size = struct.unpack_from("<I", data, pos + 4)[0]
            if cid == b"fmt ":
                _fmt, channels, rate = struct.unpack_from("<HHI", data,
                                                          pos + 8)
                block_align = max(1, channels * 2)
            elif cid == b"data" and rate:
                return size / block_align / rate
            pos += 8 + size + (size & 1)
    except (ValueError, IndexError):
        pass
    return 0.0
