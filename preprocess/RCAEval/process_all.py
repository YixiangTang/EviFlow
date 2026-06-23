#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS = [
    "process_metric.py",
    "process_label.py",
    "process_trace.py",
    "process_log.py",
]


def main() -> None:
    for script in SCRIPTS:
        subprocess.run([sys.executable, str(SCRIPT_DIR / script)], check=True)


if __name__ == "__main__":
    main()
