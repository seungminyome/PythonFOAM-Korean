#!/usr/bin/env python3
"""Two requests in flight (Slurm 24929296) against one in flight (Slurm 24903264, ../2026-10-27-solver).

Run in this folder:  python3 inflight.py   (standard library only; writes inflight.json)

From the two runs' periodic-summary.json: how many requests were sent while another was still
pending (a request counts as pending from its step until the step its reply arrived), how many
were skipped because the limit was reached, records the callback did not write, the extra wall
time per step against the run without requests and that extra time per request, reply delays and
model times, and the counts within 10 %.
"""
import json
import statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent


def describe(path, steps):
    s = json.loads(path.read_text())
    plan = s["plan"]
    answered = [r for r in s["requests"] if r["status"] == "ok"]
    spans = [(r["step"], r["arrived_at_step"]) for r in answered if r.get("arrived_at_step") is not None]
    overlapped = sum(any(a < r["step"] < b for a, b in spans if a != r["step"]) for r in answered)
    per_step = s["seconds_per_step"]
    extra = per_step["periodic-describe"] - per_step["periodic-no-llm"]
    delays = [r["arrived_at_step"] - r["step"] for r in answered if r["step"] != steps]
    return {
        "every": plan["every"], "max_pending": plan["max_pending"], "steps": plan["steps"],
        "requests_planned": s["requests_planned"], "answered": len(answered),
        "skipped_pending": s["statuses"].get("skipped_pending", 0),
        "records_missing": s.get("records_missing", []),
        "sent_while_another_pending": overlapped,
        "written_files_identical_to_twin": s["written_files_identical_to_twin"],
        "written_files_differing": s["written_files_differing"],
        "seconds_per_step": per_step,
        "extra_wall_percent": round(100 * extra / per_step["periodic-no-llm"], 2),
        "extra_wall_per_request_s": round(extra * plan["steps"] / len(answered), 3),
        "callback_s_max_at_request_steps_except_last": max(r["request_step_wall_s"] or 0 for r in s["requests"] if r["step"] != steps),
        "reply_delay_steps_except_last": [min(delays), max(delays)],
        "model_time_s": [round(min(s["inference_wall_s"]), 2), round(st.median(s["inference_wall_s"]), 2),
                         round(max(s["inference_wall_s"]), 2)],
        "fastest_flow_within_10_percent": [s["fastest_flow_within_10_percent"], s.get("scored", s["ok"])],
        "lowest_pressure_within_10_percent": [s["lowest_pressure_within_10_percent"], s.get("scored", s["ok"])],
        "one_fixed_answer": s["one_fixed_answer_for_all"],
    }


def main():
    result = {"two_in_flight_24929296": describe(HERE / "periodic-summary.json", 6000),
              "one_in_flight_24903264": describe(HERE.parent / "2026-10-27-solver" / "periodic" / "periodic-summary.json", 24000)}
    (HERE / "inflight.json").write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
