#!/usr/bin/env bash
set -euo pipefail
runtime_dir="${POD_LLM_RUNTIME:?set POD_LLM_RUNTIME}"
state="${POD_LLM_STATE:-$runtime_dir}"
[[ -f $state/server.pid ]] || exit 0
pid=$(cat "$state/server.pid")
# only a process that still is a llama-server: a pid of a server that has exited may
# belong to another process by now
if [[ -r /proc/$pid/cmdline && $(basename "$(tr '\0' '\n' < "/proc/$pid/cmdline" | head -n 1)") == llama-server ]]; then
    kill "$pid"; sleep 3; kill -9 "$pid" 2>/dev/null || true
fi
rm -f "$state/server.pid"
