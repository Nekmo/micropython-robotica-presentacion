"""esp32 module shim — NVS backed by a JSON file inside the files dir."""

import json

from stackchan_sim import bridge as _bridge_mod
from stackchan_sim import compat

_lock = compat.Lock()


def _nvs_file():
    return compat.path_join(_bridge_mod.get().files_dir,
                            ".emulator_nvs.json")


def _load():
    try:
        with open(_nvs_file()) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


class NVS:
    def __init__(self, namespace):
        self._ns = str(namespace)
        self._pending = _load().get(self._ns, {})

    def _get(self, key):
        if key not in self._pending:
            raise OSError(-4354, "ESP_ERR_NVS_NOT_FOUND")
        return self._pending[key]

    def get_i32(self, key):
        return int(self._get(key))

    def set_i32(self, key, value):
        self._pending[key] = int(value)

    def get_u32(self, key):
        return int(self._get(key)) & 0xFFFFFFFF

    def set_u32(self, key, value):
        self._pending[key] = int(value) & 0xFFFFFFFF

    def get_str(self, key):
        return str(self._get(key))

    def set_str(self, key, value):
        self._pending[key] = str(value)

    def get_blob(self, key, buf):
        data = self._get(key)
        raw = bytes.fromhex(data) if isinstance(data, str) else bytes(data)
        n = min(len(buf), len(raw))
        buf[:n] = raw[:n]
        return n

    def set_blob(self, key, value):
        self._pending[key] = bytes(value).hex()

    def erase_key(self, key):
        self._get(key)
        del self._pending[key]

    def commit(self):
        with _lock:
            data = _load()
            data[self._ns] = self._pending
            try:
                with open(_nvs_file(), "w") as fh:
                    json.dump(data, fh, indent=1)
            except OSError:
                pass


def raw_temperature():
    return 118


def hall_sensor():
    return 0


def idf_heap_info(capabilities=0):
    return [(0, 0, 0, 0)]


HEAP_DATA = 4
HEAP_EXEC = 8
