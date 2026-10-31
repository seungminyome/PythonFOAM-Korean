#!/usr/bin/env python3
"""Pinned local llama-server runtime (Gemma 4 E2B Q4_0 + image projector).

The model is loaded once and kept resident; the solver demo only sends HTTP
requests to it. Files live in POD_LLM_RUNTIME (default: ../llm-runtime next
to the PythonFOAM checkout). Run setup_runtime.sh first to download them.

    runtime.py verify       check file hashes and server flags, write manifest
    runtime.py start        start the server, or reuse one already serving ALIAS
    runtime.py health       print /health
    runtime.py standalone   one synthetic text+image request (not solver data)
    runtime.py stop         stop the server recorded in server.pid
"""
import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request

SCRIPT = Path(__file__).resolve()
DEFAULT_ROOT = SCRIPT.parents[4] / "llm-runtime" if SCRIPT.parent.name == "llm_demo" else SCRIPT.parent
ROOT = Path(os.environ.get("POD_LLM_RUNTIME", DEFAULT_ROOT)).resolve()

REVISION = "b4243c156154b6dca9324415f8c7ccc098b4aed1"
MODEL_REPO = "ggml-org/gemma-4-E2B-it-GGUF"
MODEL = ROOT / "gemma-4-E2B-it-Q4_0.gguf"
MODEL_SHA = "8e30dff3ac4c8434c49a7036fa15564bdbb6044e42bf04550bf1a096ad7e6a52"
PROJECTOR = ROOT / "mmproj-gemma-4-E2B-it-Q8_0.gguf"
PROJECTOR_SHA = "9406f99c16d68cda4f1f0552192dcc99021ea1fc6d2fd50b1dc3ccf30d04b292"
LLAMA_TAG = "b11429"
ARCHIVE = ROOT / f"llama-{LLAMA_TAG}-bin-ubuntu-x64.tar.gz"
ARCHIVE_SHA = "f6d25dde8f51133143d1453da4fd5f73b145127177612a283bf7995957af3392"
SERVER = ROOT / f"llama-{LLAMA_TAG}" / "llama-server"
ALIAS = "gemma-4-E2B-it-Q4_0-vision"
PORT = int(os.environ.get("POD_LLM_PORT", "8088"))
BASE_URL = f"http://127.0.0.1:{PORT}"

SERVER_COMMAND = [
    "--alias", ALIAS, "--host", "127.0.0.1", "--port", str(PORT),
    "--ctx-size", "2048", "--parallel", "1",
    "--threads", "4", "--threads-batch", "4", "--batch-size", "128", "--ubatch-size", "128",
    "--n-gpu-layers", "0", "--no-mmproj-offload",
    "--image-max-tokens", "256", "--mtmd-batch-max-tokens", "256",
    "--reasoning", "off", "--reasoning-budget", "0",
    "--chat-template-kwargs", '{"enable_thinking":false}',
    "--no-webui", "--metrics", "--log-timestamps",
]


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while block := source.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def process_memory(pid):
    """RSS/PSS of one process from /proc."""
    result = {"pid": pid, "monotonic_seconds": time.monotonic()}
    for filename, keys in (("status", ("VmRSS", "VmHWM", "VmSwap")),
                           ("smaps_rollup", ("Pss", "Private_Clean", "Private_Dirty"))):
        try:
            for line in Path(f"/proc/{pid}/{filename}").read_text().splitlines():
                key, _, value = line.partition(":")
                if key in keys:
                    result[key + "_KiB"] = int(value.split()[0])
        except OSError as error:
            result[filename + "_error"] = f"{type(error).__name__}: {error}"
    return result


def summarize_memory(samples):
    return {"sample_count": len(samples), "nominal_sampling_interval_seconds": 0.1,
            "sampled_peak_RSS_KiB": max((s["VmRSS_KiB"] for s in samples if "VmRSS_KiB" in s), default=None),
            "sampled_peak_PSS_KiB": max((s["Pss_KiB"] for s in samples if "Pss_KiB" in s), default=None),
            "kernel_peak_RSS_KiB": max((s["VmHWM_KiB"] for s in samples if "VmHWM_KiB" in s), default=None),
            "samples": samples}


class MemorySampler:
    def __init__(self, pid):
        self.pid, self.samples, self.done = pid, [], threading.Event()
        self.thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self):
        while not self.done.is_set():
            self.samples.append(process_memory(self.pid))
            self.done.wait(0.1)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *unused):
        self.done.set()
        self.thread.join(timeout=2)
        self.samples.append(process_memory(self.pid))


def request(path, payload=None, timeout=5):
    data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
    req = urllib.request.Request(BASE_URL + path, data=data,
                                 headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as response:
        return json.load(response)


def save(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def resources():
    return {"time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "platform": platform.platform(), "cpu_count": os.cpu_count(),
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "meminfo": Path("/proc/meminfo").read_text(),
            "disk_usage": dict(zip(("total", "used", "free"), shutil.disk_usage(ROOT))),
            "nvidia_smi": shutil.which("nvidia-smi"),
            "gpu_device_nodes": [str(p) for p in Path("/dev").glob("nvidia*")]}


def recorded_pid():
    pid_file = ROOT / "server.pid"
    if not pid_file.exists():
        return None
    pid = int(pid_file.read_text())
    status = Path(f"/proc/{pid}/status")
    if not status.exists() or "State:\tZ" in status.read_text():
        return None
    return pid


def cmdline(pid):
    return [c.decode() for c in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") if c]


def server_output(flag):
    """The server's output for a flag; if it cannot run, the error says why."""
    try:
        return subprocess.check_output([str(SERVER), flag], text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"{SERVER} {flag} failed: {error.output.strip()}") from None


def verify():
    for path, expected in ((MODEL, MODEL_SHA), (PROJECTOR, PROJECTOR_SHA), (ARCHIVE, ARCHIVE_SHA)):
        if not path.exists():
            raise RuntimeError(f"Missing {path}; run setup_runtime.sh")
        if sha256_file(path) != expected:
            raise RuntimeError(f"SHA-256 mismatch for {path.name}")
    if not SERVER.exists():
        raise RuntimeError(f"Missing {SERVER}; extract {ARCHIVE.name}")
    help_text = server_output("--help")
    for flag in ("--mmproj", "--no-mmproj-offload", "--image-max-tokens", "--reasoning"):
        if flag not in help_text:
            raise RuntimeError(f"Installed llama-server does not support {flag}")
    manifest = {
        "model_repo": MODEL_REPO, "model_revision": REVISION,
        "model_file": MODEL.name, "model_bytes": MODEL.stat().st_size, "model_sha256": MODEL_SHA,
        "model_url": f"https://huggingface.co/{MODEL_REPO}/resolve/{REVISION}/{MODEL.name}",
        "projector_file": PROJECTOR.name, "projector_bytes": PROJECTOR.stat().st_size,
        "projector_sha256": PROJECTOR_SHA,
        "projector_url": f"https://huggingface.co/{MODEL_REPO}/resolve/{REVISION}/{PROJECTOR.name}",
        "llama_cpp_tag": LLAMA_TAG,
        "llama_cpp_version": server_output("--version").strip(),
        "server_archive_sha256": ARCHIVE_SHA,
        "server_archive_url": f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_TAG}/{ARCHIVE.name}",
        "alias": ALIAS, "base_url": BASE_URL,
        "resources": resources(),
    }
    save("runtime_manifest.json", manifest)
    print(json.dumps({k: v for k, v in manifest.items() if k != "resources"}, indent=2))


def healthy_server():
    try:
        if request("/health").get("status") != "ok":
            return False
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
    models = [m["id"] for m in request("/v1/models")["data"]]
    if ALIAS not in models:
        raise RuntimeError(f"Port {PORT} is serving {models}, not {ALIAS}")
    return True


def start():
    if healthy_server():
        pid = recorded_pid()
        if pid is None:
            raise RuntimeError(f"A server answers on port {PORT} but server.pid in {ROOT} does not identify it")
        command = cmdline(pid)
        if "llama-server" not in Path(command[0]).name or "--mmproj" not in command:
            raise RuntimeError("Recorded PID is not an image-capable llama-server; refusing to reuse it")
        print(json.dumps({"reused_existing_server": True, "base_url": BASE_URL, "pid": pid}))
        return
    if recorded_pid() is not None:
        raise RuntimeError("server.pid points at a live process that is not healthy; stop it first")
    if not (ROOT / "runtime_manifest.json").exists():
        raise RuntimeError("Run 'runtime.py verify' before start")
    command = [str(SERVER), "--model", str(MODEL), "--mmproj", str(PROJECTOR), *SERVER_COMMAND]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = ROOT / f"server-{stamp}.log"
    started = time.perf_counter()
    with log_path.open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, start_new_session=True, cwd=ROOT)
    (ROOT / "server.pid").write_text(f"{process.pid}\n")
    with MemorySampler(process.pid) as sampler:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Server exited with {process.returncode}; see {log_path}")
            try:
                if request("/health").get("status") == "ok":
                    break
            except (urllib.error.URLError, TimeoutError, OSError):
                pass
            time.sleep(0.25)
        else:
            raise TimeoutError(f"Server not healthy after 300 s; PID {process.pid}; {log_path}")
    startup = {"pid": process.pid, "server_start_utc": stamp, "base_url": BASE_URL, "alias": ALIAS,
               "command": command, "server_log": str(log_path),
               "startup_to_health_seconds": time.perf_counter() - started,
               "server_memory_during_load": summarize_memory(sampler.samples),
               "resources": resources()}
    save("startup.json", startup)
    print(json.dumps({k: v for k, v in startup.items()
                      if k not in ("server_memory_during_load", "resources")}, indent=2))


def standalone():
    """One request with a synthetic plot, to check the image path before a solver run."""
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "mpl-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(figsize=(4, 3), dpi=100)
    axes.plot([0, 1, 2, 3], [0.8, 0.4, 0.2, 0.1], "o-")
    axes.set(xlabel="synthetic step", ylabel="synthetic residual", title="synthetic data, not a solver run")
    figure.tight_layout()
    image_path = ROOT / "standalone-synthetic.png"
    figure.savefig(image_path)
    plt.close(figure)
    image = image_path.read_bytes()
    payload = {
        "model": ALIAS,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": (
                "Synthetic image test, not solver data. In one short sentence each, describe "
                "the plotted trend, interpret only that trend, and say what information is "
                "missing. Numeric JSON: {\"source\":\"synthetic\",\"residuals\":[0.8,0.4,0.2,0.1]}. "
                "Do not claim physical convergence.")},
            {"type": "image_url", "image_url": {
                "url": "data:image/png;base64," + base64.b64encode(image).decode()}}]}],
        "max_tokens": 128, "temperature": 0, "seed": 42, "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "observation", "strict": True,
            "schema": {"type": "object",
                       "properties": {k: {"type": "string"} for k in
                                      ("observations", "possible_interpretation", "checks")},
                       "required": ["observations", "possible_interpretation", "checks"],
                       "additionalProperties": False}}},
    }
    save("standalone-request.json", payload)
    pid = recorded_pid()
    if pid is None:
        raise RuntimeError("No running server recorded in server.pid")
    started = time.perf_counter()
    with MemorySampler(pid) as sampler:
        response = request("/v1/chat/completions", payload, timeout=180)
    elapsed = time.perf_counter() - started
    content = response["choices"][0]["message"].get("content") or ""
    complete = response["choices"][0].get("finish_reason") == "stop" and bool(content.strip())
    result = {"status": "PASS" if complete else "FAIL",
              "wall_seconds": elapsed, "image_bytes": len(image),
              "image_sha256": hashlib.sha256(image).hexdigest(),
              "server_pid": pid, "response": response,
              "server_memory_during_inference": summarize_memory(sampler.samples)}
    save("standalone.json", result)
    print(json.dumps({"status": result["status"], "wall_seconds": elapsed, "final_text": content,
                      "usage": response.get("usage")}, indent=2, ensure_ascii=False))
    if not complete:
        raise RuntimeError("Standalone request did not return a complete response")


def stop():
    pid = recorded_pid()
    if pid is None:
        print("No running server recorded in server.pid")
        return
    if "llama-server" not in Path(cmdline(pid)[0]).name:
        raise RuntimeError(f"PID {pid} is not llama-server; refusing to signal it")
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if recorded_pid() is None:
            save("stop.json", {"pid": pid, "stopped": True,
                               "time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()})
            print(f"Stopped server PID {pid}")
            return
        time.sleep(0.2)
    raise TimeoutError(f"Server PID {pid} has not stopped after SIGTERM")


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("verify", "start", "health", "standalone", "stop"))
    action = parser.parse_args().action
    if action == "health":
        print(json.dumps(request("/health")))
    else:
        globals()[action]()
