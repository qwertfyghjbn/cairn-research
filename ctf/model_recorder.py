"""Record OpenAI-compatible chat completions while relaying their body unchanged."""

from contextlib import suppress
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
from uuid import uuid4

from observe import Journal


LOG = logging.getLogger(__name__)
CHAT = "/chat/completions"


class Recorder(ThreadingHTTPServer):
    def __init__(self, address, root, upstream, key, clients):
        self.target = urlsplit(upstream)
        if (self.target.scheme not in {"http", "https"} or not self.target.hostname
                or self.target.username or self.target.query or self.target.fragment):
            raise ValueError("CTF_MODEL_URL must be an HTTP(S) API base URL without credentials or query")
        self.key = key
        self.clients = clients
        self.journal = Journal(root)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        if self.path != CHAT:
            self.send_error(404)
            return
        authorization = self.headers.get("Authorization", "").encode()
        worker = next((name for token, name in self.server.clients.items()
                       if hmac.compare_digest(authorization, ("Bearer " + token).encode())), None)
        if worker is None:
            self.send_error(401)
            return
        try:
            size = int(self.headers.get("Content-Length", ""))
            if size < 0:
                raise ValueError
        except ValueError:
            self.send_error(411)
            return

        body = self.rfile.read(size)
        if len(body) != size:
            return
        call = uuid4().hex
        started = time.monotonic_ns()
        journal = self.server.journal
        directory = journal.root / call
        capture = True
        try:
            directory.mkdir()
            (directory / "request.json").write_bytes(body)
        except OSError:
            capture = False
            LOG.exception("CTF model capture failed call=%s", call)
        journal.emit("model_request", call_id=call, worker=worker, client_ip=self.client_address[0],
                     bytes=size, captured=capture)

        target = self.server.target
        connection_class = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
        upstream = connection_class(target.hostname, target.port, timeout=120)
        headers = {"Content-Type": self.headers.get("Content-Type", "application/json"),
                   "Accept": self.headers.get("Accept", "application/json, text/event-stream"),
                   "Accept-Encoding": "identity"}
        if self.server.key:
            headers["Authorization"] = "Bearer " + self.server.key
        status = None
        received = 0
        complete = False
        error = None
        stream = None
        try:
            upstream.request("POST", target.path.rstrip("/") + CHAT, body=body, headers=headers)
            response = upstream.getresponse()
            status = response.status
            journal.emit("model_response_headers", call_id=call, status=status,
                         content_type=response.getheader("Content-Type"),
                         provider_request_id=response.getheader("x-request-id"),
                         duration_ms=(time.monotonic_ns() - started) // 1_000_000)
            if capture:
                try:
                    stream = (directory / "response.bin").open("wb", buffering=0)
                except OSError:
                    capture = False
                    LOG.exception("CTF model capture failed call=%s", call)
            self.send_response_only(status)
            for name, value in response.getheaders():
                if name.lower() in {"content-type", "content-length", "content-encoding", "retry-after", "x-request-id"}:
                    self.send_header(name, value)
            self.send_header("Connection", "close")
            self.end_headers()
            while chunk := response.read1(65536):
                received += len(chunk)
                if stream is not None:
                    try:
                        if stream.write(chunk) != len(chunk):
                            raise OSError("short evidence write")
                    except OSError:
                        capture = False
                        stream.close()
                        stream = None
                        LOG.exception("CTF model capture failed call=%s", call)
                self.wfile.write(chunk)
            complete = response.length in (None, 0)
            if not complete:
                error = "incomplete_upstream_body"
        except (OSError, http.client.HTTPException) as exc:
            error = type(exc).__name__
            if status is None:
                with suppress(OSError):
                    self.send_error(502, "Model provider unavailable")
        finally:
            upstream.close()
            if stream is not None:
                stream.close()
            journal.emit("model_response_end", call_id=call, status=status, bytes=received,
                         captured=capture, complete=complete, error=error,
                         duration_ms=(time.monotonic_ns() - started) // 1_000_000)


def main():
    logging.basicConfig(level=logging.INFO)
    clients = json.loads(Path("/config/model-clients.json").read_bytes())
    with Recorder(("0.0.0.0", 8080), Path("/evidence"), os.environ["CTF_MODEL_URL"],
                  os.environ.get("CTF_PROVIDER_KEY"), clients) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
