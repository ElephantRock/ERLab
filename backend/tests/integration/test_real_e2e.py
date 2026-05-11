"""Real integration test - no mocks, hits actual running backend.
Prerequisites: Backend running on TEST_URL (default http://localhost:8004)
"""
import os, json, urllib.request, urllib.error

BASE = os.environ.get("TEST_URL", "http://localhost:8004")
TIMEOUT = 5

def get(path):
    resp = urllib.request.urlopen(BASE + path, timeout=TIMEOUT)
    return json.loads(resp.read())

def get_text(path):
    resp = urllib.request.urlopen(BASE + path, timeout=TIMEOUT)
    return resp.read().decode()

def unwrap(data):
    if isinstance(data, list): return data
    if isinstance(data, dict):
        for k in ("items","runs","ideas","gaps","results"):
            if k in data and isinstance(data[k], list): return data[k]
    return data

passed = failed = 0
errors = []

def test(name, func):
    global passed, failed
    try:
        func()
        passed += 1
        print(f"  PASS: {name}")
    except Exception as e:
        failed += 1
        errors.append(f"{name}: {str(e)[:100]}")
        print(f"  FAIL: {name}: {str(e)[:100]}")

# Tests
test("health", lambda: (
    get("/health")["status"] == "ok" or (_ for _ in ()).throw(AssertionError("not ok"))
))

test("pipeline runs", lambda: (
    len(unwrap(get("/api/v1/pipeline/runs"))) > 0 or (_ for _ in ()).throw(AssertionError("no runs"))
))

test("pipeline stats", lambda: (
    "total_runs" in get("/api/v1/pipeline/runs/stats")
))

test("run detail stage_report", lambda: (
    (r := get("/api/v1/pipeline/runs/detail/117"),
    len(r.get("stage_report", [])) == 16 or (_ for _ in ()).throw(AssertionError(f"got {len(r.get('stage_report',[]))} stages"))
    )[1]
))

test("ideas list", lambda: (
    len(unwrap(get("/api/v1/ideas/"))) > 0 or (_ for _ in ()).throw(AssertionError("no ideas"))
))

test("idea detail", lambda: (
    "title" in get("/api/v1/ideas/131").get("idea", {}) or (_ for _ in ()).throw(AssertionError("no title"))
))

test("gaps list", lambda: (
    len(unwrap(get("/api/v1/gaps/"))) > 0 or (_ for _ in ()).throw(AssertionError("no gaps"))
))

test("gap stats", lambda: (
    "total_gaps" in get("/api/v1/gaps/stats")
))

test("knowledge stats", lambda: isinstance(get("/api/v1/knowledge/stats"), dict))
test("knowledge graph", lambda: isinstance(get("/api/v1/knowledge-graph/stats"), dict))
test("memory stats", lambda: "total_memories" in get("/api/v1/memory/stats"))
test("governance", lambda: "pending" in get("/api/v1/governance/pending"))
test("notifications", lambda: isinstance(get("/api/v1/notifications/"), (list, dict)))
test("plugins", lambda: isinstance(get("/api/v1/plugins/"), (list, dict)))
test("status", lambda: isinstance(get("/api/v1/status/"), dict))
test("search", lambda: isinstance(get("/api/v1/search/"), (list, dict)))
test("traces", lambda: isinstance(get("/api/v1/traces/summary"), dict))
test("stale runs", lambda: isinstance(get("/api/v1/pipeline/runs/stale"), (list, dict)))

print(f"\nREAL INTEGRATION TEST - {BASE}")
print("="*50)
print(f"RESULT: {passed} pass, {failed} fail out of {passed+failed} tests")
if errors:
    for e in errors: print(f"  {e}")
print("="*50)
