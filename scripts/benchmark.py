from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path

from mailtrace.config import Settings
from mailtrace.parser import parse_evidence

root = Path(__file__).parents[1]
settings = Settings(data_dir=root / ".test-tmp" / "benchmark")
settings.ensure_directories()
fixtures = root / "mailtrace" / "fixtures"
samples = {
    "header_only": b"From: a@example.com\r\nSubject: Benchmark\r\n\r\n",
    "ordinary_eml": (fixtures / "aligned-business.eml").read_bytes(),
    "multipart_attachment": (fixtures / "incomplete-auth.eml").read_bytes(),
    "malformed_mime": (fixtures / "malformed-boundary.eml").read_bytes(),
}
results: dict[str, dict[str, float | int]] = {}
for name, data in samples.items():
    tracemalloc.start()
    started = time.perf_counter()
    parsed = parse_evidence(data, "headers" if name == "header_only" else "eml", settings)
    elapsed = (time.perf_counter() - started) * 1000
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    results[name] = {
        "bytes": len(data),
        "elapsed_ms": round(elapsed, 2),
        "peak_memory_bytes": peak,
        "observations": len(parsed["observations"]),
    }
print(json.dumps(results, indent=2))
