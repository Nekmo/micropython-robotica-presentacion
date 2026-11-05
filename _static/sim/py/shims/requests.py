"""requests shim for the simulator: HTTP through the browser (sync XHR).

The browser enforces CORS: only APIs that allow browser access work. The
Anthropic API does when the ``anthropic-dangerous-direct-browser-access``
header is present, which the simulator adds for api.anthropic.com.
"""

import json as _json

from stackchan_sim import bridge as _bridge_mod


class Response:
    def __init__(self, status, text, headers):
        self.status_code = status
        self.text = text
        self.content = text.encode()
        self.headers = headers

    def json(self):
        return _json.loads(self.text)

    def close(self):
        pass


def request(method, url, data=None, json=None, headers=None, **kwargs):
    headers = dict(headers or {})
    if json is not None:
        data = _json.dumps(json)
        headers.setdefault("content-type", "application/json")
    if isinstance(data, (bytes, bytearray)):
        data = data.decode()
    if "api.anthropic.com" in url:
        headers["anthropic-dangerous-direct-browser-access"] = "true"
    reply = _bridge_mod.get().http(method, url, headers, data)
    if reply.get("error"):
        raise OSError(reply["error"])
    return Response(reply["status"], reply["text"], reply.get("headers", {}))


def get(url, **kwargs):
    return request("GET", url, **kwargs)


def post(url, **kwargs):
    return request("POST", url, **kwargs)


def put(url, **kwargs):
    return request("PUT", url, **kwargs)


def delete(url, **kwargs):
    return request("DELETE", url, **kwargs)
