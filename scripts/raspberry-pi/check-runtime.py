"""Check the Pi service's Python imports without opening hardware or app data."""
from __future__ import annotations

import importlib
import sys
from importlib import metadata


MODULES = (
    ("numpy", "numpy"),
    ("cv2", "opencv-python"),
    ("picamera2", "picamera2"),
    ("fastapi", "fastapi"),
    ("pydantic", "pydantic"),
    ("uvicorn", "uvicorn"),
    ("httpx", "httpx"),
)


def main() -> int:
    failures = 0
    print(f"Python {sys.version.split()[0]} ({sys.executable})")
    if sys.version_info < (3, 10):
        print("FAIL: Python 3.10 or newer is required. Use current Raspberry Pi OS Lite 64-bit.")
        failures += 1
    for module_name, distribution in MODULES:
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, "__version__", None)
            if not version:
                try:
                    version = metadata.version(distribution)
                except metadata.PackageNotFoundError:
                    version = "version unavailable"
            print(f"OK: {module_name} {version}")
        except Exception as exc:
            print(f"FAIL: {module_name}: {type(exc).__name__}: {exc}")
            failures += 1
    if failures:
        print("Runtime check failed. Keep NumPy/OpenCV/Picamera2 from apt; use requirements-pi.txt in the system-site-packages venv.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
