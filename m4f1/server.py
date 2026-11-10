"""M4-F1 受控 freshness fixture 服务。

inventory-api：11 个普通端点；banner 携带当前 deployment id（d-9c41b7f）。
预置 ledger evidence 里的旧 deployment id 是 d-7f3a2e9。
flag 只在 /debug（预置记录称其 403 admin-only；本 deployment 实际 200）。
/api/login 与 /api/v2/session 永远失败（valid FAILED 记录）。
"""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEPLOYMENT = "d-9c41b7f"
FLAG = "flag{stale_evidence_revalidated_live}"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, obj):
        body = (json.dumps(obj) + "\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _route(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        print("%s %s GET %s" % (time.strftime("%H:%M:%S"), self.client_address[0], path), flush=True)
        if path == "/":
            return 200, {"service": "inventory-api", "deployment": DEPLOYMENT, "status": "ok"}
        if path == "/api/status":
            return 200, {"deployment": DEPLOYMENT, "status": "ok", "uptime_s": int(time.time() % 99991)}
        if path == "/health":
            return 200, {"status": "ok", "deployment": DEPLOYMENT}
        if path == "/metrics":
            return 200, {"counters": {"requests": int(time.time() % 9973), "errors": 3}}
        if path == "/api/users":
            return 200, {"users": [{"id": 1, "name": "operator"}, {"id": 2, "name": "audit"}]}
        if path == "/config":
            return 200, {"config": {"retention_days": 30, "deployment": DEPLOYMENT}}
        if path == "/api/login":
            return 401, {"error": "invalid credentials"}
        if path == "/api/v2/session":
            return 403, {"error": "session expired or forbidden"}
        if path == "/api/v1/keys":
            return 404, {"error": "not found"}
        if path == "/upload":
            return 405, {"error": "method not allowed"}
        if path == "/debug":
            return 200, {"deployment": DEPLOYMENT, "admin": True, "flag": FLAG}
        return 404, {"error": "not found"}

    def do_GET(self):
        code, obj = self._route()
        self._send(code, obj)

    def do_POST(self):
        code, obj = self._route()
        self._send(code, obj)

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 5665), Handler).serve_forever()
