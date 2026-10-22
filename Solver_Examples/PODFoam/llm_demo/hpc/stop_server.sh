#!/usr/bin/env bash
set -euo pipefail
runtime_dir="${POD_LLM_RUNTIME:?set POD_LLM_RUNTIME}"
state="${POD_LLM_STATE:-$runtime_dir}"
[[ -f $state/server.pid ]] || exit 0
pid=$(cat "$state/server.pid")
if kill -0 "$pid" 2>/dev/null; then kill "$pid"; sleep 3; kill -9 "$pid" 2>/dev/null || true; fi
rm -f "$state/server.pid"
