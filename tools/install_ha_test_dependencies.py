"""Install Bluetooth/USB dependencies from the HA version under test, for Linux CI."""

import json
import subprocess
import sys
from pathlib import Path

import homeassistant

components = Path(homeassistant.__file__).parent / "components"
requirements = set()
pending = ["bluetooth", "light"]
visited = set()
while pending:
    domain = pending.pop()
    if domain in visited:
        continue
    visited.add(domain)
    manifest = json.loads((components / domain / "manifest.json").read_text())
    requirements.update(manifest.get("requirements", []))
    pending.extend(manifest.get("dependencies", []))
    pending.extend(manifest.get("after_dependencies", []))
subprocess.check_call([sys.executable, "-m", "pip", "install", *sorted(requirements)])
