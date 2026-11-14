"""Deterministic OpenAI-compatible provider for the M4-F1 rehearsal only."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time


class Fixture(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/chat/completions":
            self.send_error(404)
            return
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        model = request["model"]
        messages = request["messages"]
        if not request.get("stream"):
            self.reply(dict(id="fixture-health", object="chat.completion", created=int(time.time()), model=model,
                            choices=[dict(index=0, message=dict(role="assistant", content="pong"), finish_reason="stop")]))
            return

        tool_output = next((row.get("content") for row in reversed(messages) if row["role"] == "tool"), None)
        if tool_output is None:
            arguments = json.dumps({"command": "curl -fsS http://m4f1:5665/debug | tee fixture-evidence.json"})
            delta = {"tool_calls": [dict(index=0, id="call_fixture", type="function",
                                         function=dict(name="bash", arguments=arguments))]}
            reason = "tool_calls"
        else:
            description = f"M4-F1 /debug response saved in fixture-evidence.json: {tool_output}"
            text = json.dumps({"accepted": True, "data": {"fact": {"description": description},
                                                           "complete": {"description": description}}})
            delta, reason = {"content": text}, "stop"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for payload, finish in (({"role": "assistant"}, None), (delta, None), ({}, reason)):
            row = dict(id="fixture-chat", object="chat.completion.chunk", created=int(time.time()), model=model,
                       choices=[dict(index=0, delta=payload, finish_reason=finish)])
            self.wfile.write(b"data: " + json.dumps(row).encode() + b"\n\n")
            self.wfile.flush()
        usage = dict(id="fixture-chat", object="chat.completion.chunk", created=int(time.time()), model=model, choices=[],
                     usage=dict(prompt_tokens=100, completion_tokens=20, total_tokens=120))
        self.wfile.write(b"data: " + json.dumps(usage).encode() + b"\n\ndata: [DONE]\n\n")

    def reply(self, row):
        body = json.dumps(row).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8090), Fixture).serve_forever()
