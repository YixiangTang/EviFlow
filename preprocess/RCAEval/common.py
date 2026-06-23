import re
from pathlib import Path
from typing import NamedTuple


CASE_NAME_PATTERN = re.compile(r"^(?P<service>.+)_(?P<failure_type>[^_]+)$")
POD_SUFFIX_PATTERN = re.compile(r"^(?P<service>.+)-(?P<replicaset>[0-9a-f]{8,10})-(?P<pod>[a-z0-9]{5})$")
OUTPUT_DATES = ("1", "2")


class RunContext(NamedTuple):
    case_dir: Path
    run_dir: Path


def iter_case_dirs(source_root: Path) -> list[Path]:
    return sorted(path for path in source_root.iterdir() if path.is_dir())


def iter_run_dirs(case_dir: Path) -> list[Path]:
    return sorted(path for path in case_dir.iterdir() if path.is_dir())


def iter_run_contexts(source_root: Path) -> list[RunContext]:
    return [
        RunContext(case_dir=case_dir, run_dir=run_dir)
        for case_dir in iter_case_dirs(source_root)
        for run_dir in iter_run_dirs(case_dir)
    ]


def split_run_contexts_by_date(source_root: Path) -> dict[str, list[RunContext]]:
    groups = {date: [] for date in OUTPUT_DATES}
    for index, context in enumerate(iter_run_contexts(source_root)):
        groups[OUTPUT_DATES[index % len(OUTPUT_DATES)]].append(context)
    return groups


def normalize_service_name(value: object) -> str:
    name = str(value).strip()
    match = POD_SUFFIX_PATTERN.match(name)
    if match:
        name = match.group("service")
    if name.startswith("ts-"):
        name = name[3:]
    if name.endswith("-service"):
        name = name[:-8]
    return name


def parse_case_name(case_dir: Path) -> tuple[str, str]:
    match = CASE_NAME_PATTERN.match(case_dir.name)
    if not match:
        raise ValueError(f"Unexpected RCAEval case directory name: {case_dir}")
    return normalize_service_name(match.group("service")), match.group("failure_type")


def read_inject_time(run_dir: Path) -> int:
    inject_file = run_dir / "inject_time.txt"
    if not inject_file.exists():
        raise FileNotFoundError(f"Injection time file not found: {inject_file}")
    return int(inject_file.read_text(encoding="utf-8").strip())
