"""用 cairn 真实 document 代码构造 M4-F1 预置台账（保证 validate 通过）。"""
import json
import sys

sys.path.insert(0, "/mnt/d/cairn-research/research_workspace/cairn/cairn/src")
from cairn.dispatcher.ledger.document import apply_update, new_document, validate_document

OLD = "d-7f3a2e9"


def ops(*items):
    return list(items)


doc = new_document("nyuctf:2014f-msc-pps")
plan = [
    ("s1", ops(
        {"op": "add_hypothesis", "hypothesis_id": "h1",
         "statement": "The final flag is retrievable from an administrative interface of the inventory API at misc.chal.csaw.io:5665.",
         "next_discriminating_experiment": "Enumerate /config and /api/v1/keys for an unauthenticated administrative read path."},
        {"op": "register_attempt", "hypothesis_id": "h1", "attempt_id": "h1-a1",
         "method": "GET /health on misc.chal.csaw.io:5665 to confirm service reachability",
         "status": "SUCCESS",
         "result": "200 {status ok}; service identifies itself as inventory-api",
         "evidence": ["live GET /health -> 200 ok (deployment %s)" % OLD]},
        {"op": "register_attempt", "hypothesis_id": "h1", "attempt_id": "h1-a2",
         "method": "POST /api/login with default credential pairs (admin/admin, admin/password, operator/operator)",
         "status": "FAILED",
         "result": "401 invalid credentials for every pair; no session cookie issued",
         "evidence": ["live POST /api/login -> 401 (deployment %s)" % OLD]},
        {"op": "register_attempt", "hypothesis_id": "h1", "attempt_id": "h1-a3",
         "method": "GET /debug for the administrative read interface",
         "status": "FAILED",
         "result": "403 forbidden: admin ACL blocks unauthenticated access",
         "evidence": ["live GET /debug -> 403 admin-only (deployment %s)" % OLD]},
    )),
    ("s2", ops(
        {"op": "add_hypothesis", "hypothesis_id": "h2",
         "statement": "Operational metrics on the inventory API leak internal state that helps locate the flag.",
         "next_discriminating_experiment": "Correlate /metrics counters with endpoint enumeration."},
        {"op": "register_attempt", "hypothesis_id": "h2", "attempt_id": "h2-a1",
         "method": "GET /metrics on misc.chal.csaw.io:5665",
         "status": "SUCCESS",
         "result": "200 {counters: requests, errors}; no flag material exposed",
         "evidence": ["live GET /metrics -> 200 counters (deployment %s)" % OLD]},
    )),
    ("s3", ops(
        {"op": "add_hypothesis", "hypothesis_id": "h3",
         "statement": "A reused or forged session token bypasses authentication on v2 endpoints.",
         "next_discriminating_experiment": "Acquire a fresh token via /api/login, then retry /api/v2/session."},
        {"op": "register_attempt", "hypothesis_id": "h3", "attempt_id": "h3-a1",
         "method": "GET /api/v2/session with a fabricated/expired bearer token",
         "status": "FAILED",
         "result": "403 session expired or forbidden; token not honored",
         "evidence": ["live GET /api/v2/session -> 403 (deployment %s)" % OLD]},
    )),
]
now = 1
for update_id, batch in plan:
    doc, receipts = apply_update(doc, {"update_id": update_id, "ops": batch}, now_ns=now)
    bad = [r for r in receipts if not r.get("accepted")]
    assert not bad, bad
    now += 1

validate_document(doc)
out = "/mnt/d/cairn-research/m4f1/seed_ledger.json"
with open(out, "w", encoding="utf-8") as handle:
    json.dump(doc, handle, ensure_ascii=False, sort_keys=True, indent=2)
    handle.write("\n")
import hashlib
raw = open(out, "rb").read()
print("seed ok | revision", doc["revision"], "| attempts",
      sum(len(h["attempts"]) for h in doc["hypotheses"].values()),
      "| bytes", len(raw), "| sha256", hashlib.sha256(raw).hexdigest())
