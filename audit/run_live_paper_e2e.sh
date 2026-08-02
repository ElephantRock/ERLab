#!/usr/bin/env bash
set -u

mkdir -p "$EVIDENCE_DIR"

run_capture() {
  local name="$1"
  shift
  set +e
  "$@" > >(tee "$EVIDENCE_DIR/${name}.log") 2>&1
  local code=$?
  set -e
  printf '%s\n' "$code" > "$EVIDENCE_DIR/${name}.exitcode"
  return 0
}

set -e

if [ "${EROCK_DEFAULT_PROVIDER:-}" = "ollama" ]; then
  run_capture ollama_install bash -lc 'curl -fsSL https://ollama.com/install.sh | sh'
  nohup ollama serve > "$EVIDENCE_DIR/ollama_serve.log" 2>&1 &
  echo $! > "$EVIDENCE_DIR/ollama.pid"
  python - <<'PY'
import time, urllib.request
last = None
for _ in range(120):
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as r:
            if r.status == 200:
                break
    except Exception as exc:
        last = exc
        time.sleep(1)
else:
    raise RuntimeError(f"Ollama did not start: {last}")
PY
  run_capture ollama_pull ollama pull "${EROCK_OLLAMA_MODEL:-qwen2.5:7b}"
  run_capture ollama_inventory curl -fsS http://127.0.0.1:11434/api/tags
  run_capture ollama_smoke bash -lc 'curl -fsS http://127.0.0.1:11434/api/chat -H "Content-Type: application/json" -d "{\"model\":\"${EROCK_OLLAMA_MODEL:-qwen2.5:7b}\",\"stream\":false,\"messages\":[{\"role\":\"user\",\"content\":\"Return exactly: READY\"}]}"'
  run_capture ollama_capability_smoke bash -lc 'curl -fsS http://127.0.0.1:11434/api/chat -H "Content-Type: application/json" -d "{\"model\":\"${EROCK_OLLAMA_MODEL:-qwen2.5:7b}\",\"stream\":false,\"messages\":[{\"role\":\"system\",\"content\":\"You are an academic research writer. Follow structure and length requirements exactly.\"},{\"role\":\"user\",\"content\":\"Write a coherent 350-450 word mini research synthesis with these headings: Background, Methods, Findings, Limitations. Topic: reproducible evaluation for small-data tabular classification. Do not invent citations.\"}]}"'
fi

run_capture pip_upgrade python -m pip install --upgrade pip
run_capture package_install pip install -e ".[dev]"
run_capture package_identity python -c 'from importlib.metadata import version; value=version("elephant-rock"); print(value); assert value == "1.0.1"'
run_capture migration alembic upgrade head

nohup python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000 > "$EVIDENCE_DIR/backend_before_restart.log" 2>&1 &
echo $! > "$EVIDENCE_DIR/backend.pid"
python - <<'PY'
import time, urllib.request
last = None
for _ in range(90):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3) as r:
            if r.status == 200:
                break
    except Exception as exc:
        last = exc
        time.sleep(1)
else:
    raise RuntimeError(f"backend did not start: {last}")
PY

run_capture live_paper_harness python audit/live_paper_product_e2e.py run

kill "$(cat "$EVIDENCE_DIR/backend.pid")" 2>/dev/null || true
sleep 3
nohup python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000 > "$EVIDENCE_DIR/backend_after_restart.log" 2>&1 &
echo $! > "$EVIDENCE_DIR/backend_restart.pid"
python - <<'PY'
import time, urllib.request
last = None
for _ in range(90):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3) as r:
            if r.status == 200:
                break
    except Exception as exc:
        last = exc
        time.sleep(1)
else:
    raise RuntimeError(f"backend did not restart: {last}")
PY
run_capture restart_verification python audit/live_paper_product_e2e.py verify

pushd frontend >/dev/null
run_capture npm_ci npm ci
run_capture frontend_tests npm test
run_capture frontend_typescript npm run ts:budget
run_capture frontend_build npm run build
run_capture playwright_package npm install --no-save --package-lock=false @playwright/test@1.55.0
run_capture playwright_browser npx playwright install --with-deps chromium
nohup npm run dev -- --host 127.0.0.1 --port 5173 > "$EVIDENCE_DIR/vite.log" 2>&1 &
echo $! > "$EVIDENCE_DIR/vite.pid"
popd >/dev/null
python - <<'PY'
import time, urllib.request
last = None
for _ in range(90):
    try:
        with urllib.request.urlopen("http://127.0.0.1:5173/", timeout=3) as r:
            if r.status == 200:
                break
    except Exception as exc:
        last = exc
        time.sleep(1)
else:
    raise RuntimeError(f"frontend did not start: {last}")
PY
pushd frontend >/dev/null
run_capture browser_harness node ../audit/live_paper_browser.mjs
popd >/dev/null

python --version > "$EVIDENCE_DIR/python_version.txt" 2>&1 || true
python -m pip freeze > "$EVIDENCE_DIR/pip_freeze.txt" 2>&1 || true
node --version > "$EVIDENCE_DIR/node_version.txt" 2>&1 || true
npm --version > "$EVIDENCE_DIR/npm_version.txt" 2>&1 || true
git rev-parse HEAD > "$EVIDENCE_DIR/audit_head.txt"
git rev-parse v1.0.1^{commit} > "$EVIDENCE_DIR/product_baseline.txt"
git diff --name-only v1.0.1...HEAD > "$EVIDENCE_DIR/audit_diff_files.txt"
git status --short > "$EVIDENCE_DIR/git_status.txt"
find "$EVIDENCE_DIR" -maxdepth 4 -type f -printf '%P\n' | sort > "$EVIDENCE_DIR/evidence_inventory.txt"

set +e
python audit/consolidate_live_paper_e2e.py > "$EVIDENCE_DIR/consolidation.log" 2>&1
printf '%s\n' "$?" > "$EVIDENCE_DIR/consolidation.exitcode"
set -e

kill "$(cat "$EVIDENCE_DIR/backend_restart.pid")" 2>/dev/null || true
kill "$(cat "$EVIDENCE_DIR/vite.pid")" 2>/dev/null || true
if [ -f "$EVIDENCE_DIR/ollama.pid" ]; then
  kill "$(cat "$EVIDENCE_DIR/ollama.pid")" 2>/dev/null || true
fi
exit 0
