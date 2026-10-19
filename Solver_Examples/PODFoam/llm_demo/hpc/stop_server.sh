#!/usr/bin/env bash
set -euo pipefail
runtime_dir="${POD_LLM_RUNTIME:?set POD_LLM_RUNTIME}"
[[ -f $runtime_dir/server.pid ]] || exit 0
pid=$(cat "$runtime_dir/server.pid")
if kill -0 "$pid" 2>/dev/null; then kill "$pid"; sleep 3; kill -9 "$pid" 2>/dev/null || true; fi
rm -f "$runtime_dir/server.pid"
