import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psutil


def command(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=15)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def collect(scope):
    cpu = platform.processor()
    cpu_source = "platform.processor()"
    if platform.system() == "Linux":
        text = command(["lscpu", "-J"])
        if text:
            fields = {x["field"]: x["data"] for x in json.loads(text)["lscpu"]}
            cpu = fields.get("Model name:", cpu)
            cpu_source = "lscpu -J"
    elif platform.system() == "Darwin":
        cpu = command(["sysctl", "-n", "machdep.cpu.brand_string"]) or cpu
        cpu_source = "sysctl machdep.cpu.brand_string"
    elif platform.system() == "Windows":
        cpu = command(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"]) or cpu
        cpu_source = "Get-CimInstance Win32_Processor"
    memory = psutil.virtual_memory()
    gpu = command(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    x = np.ones(24_000_000, dtype=np.float64)
    float(np.sum(x))
    times = []
    for _ in range(9):
        start = time.perf_counter()
        float(np.sum(x))
        times.append(time.perf_counter() - start)
    bandwidth = x.nbytes / statistics.median(times) / 1e9
    return {
        "scope": scope, "created_at": datetime.now(timezone.utc).isoformat(),
        "os": platform.platform(), "cpu": cpu or "Модель CPU не доступна у цьому середовищі",
        "cpu_source": cpu_source, "logical_cpus": os.cpu_count(),
        "ram_bytes": memory.total, "ram_available_bytes": memory.available,
        "ram_source": "psutil.virtual_memory()",
        "nvidia_gpu": gpu or "nvidia-smi недоступна; NVIDIA GPU не виявлено цим способом",
        "gpu_source": "nvidia-smi --query-gpu=name,memory.total",
        "read_bandwidth_GB_s": round(bandwidth, 3),
        "read_bandwidth_source": "Медіана 9 послідовних numpy.sum масиву 192 MB float64; приблизна ефективна пропускна здатність RAM, не паспортна характеристика",
        "bandwidth_samples_s": times,
        "notes": "Для персонального звіту додайте модель CPU/GPU і паспортну пропускну здатність RAM/VRAM з посиланням на специфікацію. Цей тест не визначає VRAM bandwidth."
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", default="user_computer")
    parser.add_argument("--output", default=str(Path(__file__).resolve().parent / "data/hardware.json"))
    args = parser.parse_args()
    report = collect(args.scope)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
