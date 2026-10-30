"""Install Bluetooth/USB dependencies from the HA version under test, for Linux CI."""

import json
import subprocess
import sys
from pathlib import Path

import homeassistant

components = Path(homeassistant.__file__).parent / "components"
requirements = []
for domain in ("usb", "bluetooth"):
    manifest = json.loads((components / domain / "manifest.json").read_text())
    requirements.extend(manifest.get("requirements", []))
subprocess.check_call([sys.executable, "-m", "pip", "install", *requirements])
