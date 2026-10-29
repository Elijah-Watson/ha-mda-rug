"""Build a local install ZIP without captures, APKs, caches, or unrelated devices."""

import hashlib
import json
import zipfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    component = root / "custom_components/mda_rug"
    version = json.loads((component / "manifest.json").read_text())["version"]
    output = root / "dist"
    output.mkdir(exist_ok=True)
    target = output / f"mda_rug-{version}.zip"
    files = [p for p in component.rglob("*") if p.is_file() and p.suffix in (".py", ".json", ".png")]
    files += [root / "README.md", root / "LICENSE", root / "THIRD_PARTY_NOTICES.md", root / "research/PROTOCOL.md"]
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(root).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert "custom_components/mda_rug/manifest.json" in archive.namelist()
        assert not any(
            name.startswith("captures/") or "__pycache__" in name for name in archive.namelist()
        )
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".zip.sha256").write_text(f"{digest}  {target.name}\n", encoding="utf-8")
    print(f"Built {target.name}: {target.stat().st_size:,} bytes; {len(files)} files")
    print(f"SHA256 {digest}")


if __name__ == "__main__":
    main()
