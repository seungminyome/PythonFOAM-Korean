"""The fixed test's scenario once, with its own environment; prints the quantities its bounds check."""
import json, sys, time
sys.path.insert(0, sys.argv[1])
import test_async as T
h = T.Harness({"LLM_MODE": "describe", "LLM_ASYNC": "1",
               "LLM_ENDPOINT": "http://127.0.0.1:1/v1/chat/completions",
               "LLM_CONNECT_TIMEOUT_S": "30", "LLM_CALLBACK_DEADLINE_S": "30"})
try:
    r = h.run(sleep_after=5, sleep_s=0.1); walls = dict(h.walls)
finally:
    h.close()
print(json.dumps({"status": r["status"], "phase": r.get("transport_phase"), "sent": r.get("request_sent"),
                  "reaped": r.get("worker_reaped"), "inference_wall_s": round(r.get("inference_wall_s") or -1, 4),
                  "max_wall_lt10": round(max(w for s, w in walls.items() if s < 10), 3), "wall10": round(walls[10], 3),
                  "arrived_at_step": r.get("arrived_at_step"), "render_s": round(r.get("image_render_wall_s") or -1, 3),
                  "callback_elapsed_s": round(r.get("callback_elapsed_s") or -1, 3), "load": open("/proc/loadavg").read().split()[0]}))
