import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import psutil

from hardware import collect


ROOT = Path(__file__).resolve().parent
VARIANTS = [("before", "Qwen3-1.7B-Q8_0.gguf", "qwen3-1.7b-q8"),
            ("after", "Qwen3-1.7B-Q4_K_M.gguf", "qwen3-1.7b-q4")]


def wait_ready(process, base_url, seconds=120):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("llama-server завершив роботу. Перевірте журнал запуску.")
        try:
            with opener.open(base_url + "/health", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(.25)
    raise TimeoutError("Модель не завантажилася за відведений час.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llama-server", required=True)
    parser.add_argument("--models-dir", default=str(ROOT / "models"))
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--requests", type=int, default=8)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4])
    parser.add_argument("--scope", default="user_computer")
    parser.add_argument("--record-demo", action="store_true")
    parser.add_argument("--only", choices=["before", "after"])
    parser.add_argument("--replace-results", action="store_true")
    args = parser.parse_args()
    data = ROOT / "data"
    data.mkdir(exist_ok=True)
    csv_path = ROOT.parent / "bench_results.csv"
    if csv_path.exists() and not args.only:
        if not args.replace_results:
            raise FileExistsError("bench_results.csv уже існує. Для нового повного запуску передайте --replace-results; попередні результати буде збережено окремо.")
        backup = data / "previous_runs" / datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(csv_path, backup / csv_path.name)
        for item in data.glob("*"):
            if item.is_file() and (item.name.startswith(("manifest_", "quality_", "bench_", "runtime_"))):
                shutil.copy2(item, backup / item.name)
        csv_path.unlink()
    hardware = collect(args.scope)
    (data / f"hardware_{args.scope}.json").write_text(json.dumps(hardware, ensure_ascii=False, indent=2), encoding="utf-8")
    task_environment = dict(os.environ)
    for key in ("NO_PROXY", "no_proxy"):
        task_environment[key] = ",".join(filter(None, [task_environment.get(key), "127.0.0.1", "localhost"]))
    runtime = str(Path(args.llama_server).resolve())
    for label, filename, alias in VARIANTS:
        if args.only and label != args.only:
            continue
        model_path = Path(args.models_dir).resolve() / filename
        if not model_path.is_file():
            raise FileNotFoundError(f"Модель відсутня: {model_path}. Спочатку виконайте download_models.py.")
        command = [runtime, "--model", str(model_path), "--alias", alias,
            "--host", "127.0.0.1", "--port", "8080", "--n-gpu-layers", "0",
            "--threads", str(args.threads), "--threads-batch", str(args.threads),
            "--parallel", str(args.parallel), "--ctx-size", str(4096 * args.parallel),
            "--cache-ram", "0", "--no-cache-prompt", "--jinja", "--reasoning", "off", "--reasoning-budget", "0"]
        version_result = subprocess.run([runtime, "--version"], capture_output=True, text=True)
        manifest = {"label": label, "scope": args.scope, "model": alias, "filename": filename,
            "model_bytes": model_path.stat().st_size,
            "sha256": hashlib.file_digest(model_path.open("rb"), "sha256").hexdigest(),
            "repository": "unsloth/Qwen3-1.7B-GGUF", "revision": "d7f544eead698dbd1f15126ef60b45a1e1933222",
            "created_at": datetime.now(timezone.utc).isoformat(), "command": command,
            "version": (version_result.stdout + version_result.stderr).strip()}
        stop = threading.Event()
        peaks = [0]
        with (data / f"runtime_{label}.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=task_environment)
            def sample_memory():
                tracked = psutil.Process(process.pid)
                while not stop.wait(.2):
                    try:
                        peaks[0] = max(peaks[0], tracked.memory_info().rss)
                    except psutil.Error:
                        return
            monitor = threading.Thread(target=sample_memory, daemon=True)
            monitor.start()
            try:
                wait_ready(process, "http://127.0.0.1:8080")
                print(f"{label}: модель завантажена", flush=True)
                bench = [sys.executable, str(ROOT / "bench.py"), "--base-url", "http://127.0.0.1:8080/v1",
                    "--model", alias, "--label", label, "--requests", str(args.requests),
                    "--max-tokens", str(args.max_tokens), "--timeout", "180", "--reasoning-effort", "none",
                    "--concurrency", *map(str, args.concurrency), "--output", str(ROOT.parent / "bench_results.csv")]
                with (data / f"bench_{label}.log").open("w", encoding="utf-8") as bench_log:
                    subprocess.run(bench, check=True, env=task_environment, stdout=bench_log, stderr=subprocess.STDOUT)
                print(f"{label}: бенчмарк завершено", flush=True)
                subprocess.run([sys.executable, str(ROOT / "quality.py"), "--model", alias,
                    "--label", label], check=True, env=task_environment)
                if label == "after" and args.record_demo:
                    subprocess.run([sys.executable, str(ROOT / "record_demo.py"), "--model", alias,
                        ], check=True, env=task_environment)
            finally:
                stop.set()
                monitor.join(timeout=2)
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                manifest["peak_process_rss_bytes"] = peaks[0]
                (data / f"manifest_{label}.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
