import re
from pathlib import Path


POD_SUFFIX_PATTERN = re.compile(r"^(?P<service>.+)-(?P<replicaset>[0-9a-f]{8,10})-(?P<pod>[a-z0-9]{5})$")


def default_dates(source_root: Path) -> list[str]:
    return sorted(path.name for path in source_root.iterdir() if path.is_dir())


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
