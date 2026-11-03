"""Run the connection-refused scenario once and print where the time goes."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import test_async as T
t0 = time.monotonic()
h = T.Harness({"LLM_MODE": "describe", "LLM_ASYNC": "1",
               "LLM_ENDPOINT": "http://127.0.0.1:1/v1/chat/completions"})
t1 = time.monotonic()
try:
    r = h.run(sleep_after=5, sleep_s=0.1)
    walls = dict(h.walls)
    resp = json.loads((h.case / "llm_response.json").read_text()) if (h.case / "llm_response.json").exists() else {}
finally:
    h.close()
print(json.dumps({"harness_init_s": round(t1 - t0, 3), "status": r["status"], "error": r.get("error"),
                  "walls": {k: round(v, 3) for k, v in walls.items()},
                  "arrived_at_step": r.get("arrived_at_step"), "solver_stall_s": r.get("solver_stall_s"),
                  "summary_wall_s": r.get("summary_wall_s"), "image_render_wall_s": r.get("image_render_wall_s"),
                  "inference_wall_s": r.get("inference_wall_s"), "callback_elapsed_s": r.get("callback_elapsed_s"),
                  "elapsed_since_request_s": r.get("elapsed_since_request_s"),
                  "worker_wait_elapsed_s": r.get("worker_wait_elapsed_s"), "end_wait_s": r.get("end_wait_s"),
                  "writer_completed": r.get("writer_completed"), "worker_reaped": r.get("worker_reaped"),
                  "callback_started_at": r.get("callback_started_at"), "request_before_at": r.get("request_before_at"),
                  "response_after_at": r.get("response_after_at")}))
