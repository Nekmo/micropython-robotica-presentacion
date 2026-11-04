"""Entry point of the in-browser simulator (called by sim-worker.js).

Adapted from esp-emulator's ``runner_mpy.py``: installs the hardware
shims and runs the user's program on the WebAssembly MicroPython VM.
"""

import json
import sys

FILES_DIR = "/flash"


def setup(host):
    for path in ("/sim", FILES_DIR, FILES_DIR + "/libs", "/sim/shims"):
        if path not in sys.path:
            sys.path.insert(0, path)

    from stackchan_sim import bridge as bridge_mod
    with open("/sim/stackchan_sim/board.json") as fh:
        board = json.load(fh)
    bridge = bridge_mod.Bridge(host, board, FILES_DIR)

    from stackchan_sim import simtime
    sys.modules["time"] = simtime
    sys.modules["utime"] = simtime

    from stackchan_sim import os_shim
    os_shim.install()
    import os
    os.chdir(FILES_DIR)

    # Stack-chan's screen is landscape, as left by the firmware at boot
    import M5
    M5.Display.setRotation(1)
    return bridge


def run(host, path):
    bridge = setup(host)
    try:
        with open(path) as fh:
            code = fh.read()
        exec(compile(code, path, "exec"), {"__name__": "__main__", "__file__": path})
        print("[simulador] programa terminado")
    except SystemExit:
        print("[simulador] programa finalizado")
    except KeyboardInterrupt:
        print("[simulador] interrumpido")
    except Exception as exc:
        sys.print_exception(exc)
    bridge.flush(force=True)
