"""Minimal pure-Python PNG decoder (common subset, no PIL).

Used by the MicroPython runtime to decode firmware assets (small icons).
Supports 8-bit RGB / RGBA / palette (+tRNS) / grayscale (+alpha), all
scanline filters, no interlacing. Returns straight RGBA bytes.
"""

import struct

_MAGIC = b"\x89PNG\r\n\x1a\n"


def _inflate(data):
    try:
        import zlib
        return zlib.decompress(data)
    except ImportError:
        import deflate
        import io
        stream = deflate.DeflateIO(io.BytesIO(data), deflate.ZLIB)
        return stream.read()


def _chunks(data):
    pos = 8
    while pos + 8 <= len(data):
        length, ctype = struct.unpack_from(">I4s", data, pos)
        start = pos + 8
        yield ctype, data[start:start + length]
        pos = start + length + 4  # skip CRC


def size(data):
    """(w, h) from the IHDR without decoding, or None."""
    if data[:8] != _MAGIC or len(data) < 24:
        return None
    w, h = struct.unpack_from(">II", data, 16)
    return w, h


def _paeth(a, b, c):
    p = a + b - c
    pa = p - a if p > a else a - p
    pb = p - b if p > b else b - p
    pc = p - c if p > c else c - p
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode(data):
    """PNG bytes -> (w, h, bytearray of RGBA). Raises ValueError."""
    if data[:8] != _MAGIC:
        raise ValueError("not a PNG")
    w = h = None
    bit_depth = color_type = interlace = 0
    palette = b""
    trns = b""
    idat = []
    for ctype, chunk in _chunks(data):
        if ctype == b"IHDR":
            w, h, bit_depth, color_type, _comp, _filt, interlace = \
                struct.unpack(">IIBBBBB", chunk)
        elif ctype == b"PLTE":
            palette = chunk
        elif ctype == b"tRNS":
            trns = chunk
        elif ctype == b"IDAT":
            idat.append(chunk)
        elif ctype == b"IEND":
            break
    if w is None:
        raise ValueError("missing IHDR")
    if bit_depth != 8:
        raise ValueError("only 8-bit PNGs supported (got %d)" % bit_depth)
    if interlace:
        raise ValueError("interlaced PNGs not supported")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise ValueError("bad color type %d" % color_type)

    raw = _inflate(b"".join(idat))
    stride = w * channels
    if len(raw) < (stride + 1) * h:
        raise ValueError("truncated PNG data")

    # unfilter scanlines in place
    out = bytearray(stride * h)
    pos = 0
    for row in range(h):
        ftype = raw[pos]
        pos += 1
        line_start = row * stride
        prev_start = line_start - stride
        for i in range(stride):
            x = raw[pos + i]
            a = out[line_start + i - channels] if i >= channels else 0
            b = out[prev_start + i] if row > 0 else 0
            if ftype == 1:
                x = (x + a) & 0xFF
            elif ftype == 2:
                x = (x + b) & 0xFF
            elif ftype == 3:
                x = (x + ((a + b) >> 1)) & 0xFF
            elif ftype == 4:
                c = out[prev_start + i - channels] \
                    if (row > 0 and i >= channels) else 0
                x = (x + _paeth(a, b, c)) & 0xFF
            out[line_start + i] = x
        pos += stride

    # expand to RGBA
    rgba = bytearray(w * h * 4)
    n = w * h
    if color_type == 6:
        rgba[:] = out
    elif color_type == 2:
        for i in range(n):
            s = i * 3
            d = i * 4
            rgba[d] = out[s]
            rgba[d + 1] = out[s + 1]
            rgba[d + 2] = out[s + 2]
            rgba[d + 3] = 255
    elif color_type == 0:
        for i in range(n):
            g = out[i]
            d = i * 4
            rgba[d] = rgba[d + 1] = rgba[d + 2] = g
            rgba[d + 3] = 255
    elif color_type == 4:
        for i in range(n):
            s = i * 2
            d = i * 4
            g = out[s]
            rgba[d] = rgba[d + 1] = rgba[d + 2] = g
            rgba[d + 3] = out[s + 1]
    else:  # palette
        for i in range(n):
            p = out[i] * 3
            d = i * 4
            rgba[d] = palette[p]
            rgba[d + 1] = palette[p + 1]
            rgba[d + 2] = palette[p + 2]
            rgba[d + 3] = trns[out[i]] if out[i] < len(trns) else 255
    return w, h, rgba
