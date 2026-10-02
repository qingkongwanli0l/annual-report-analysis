"""Build portable plugin and standalone skill ZIPs without local caches."""

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/annual-report-analysis"
EXCLUDED = {"node_modules", "__pycache__", ".venv", ".cache"}


def build():
    version = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))["version"]
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    files = sorted(p for p in SKILL.rglob("*") if p.is_file() and not EXCLUDED.intersection(p.relative_to(SKILL).parts) and p.suffix != ".pyc")
    for kind in ("plugin", "skill"):
        target = destination / f"annual-report-analysis-{version}-{kind}.zip"
        with ZipFile(target, "w", ZIP_DEFLATED) as archive:
            for path in files:
                relative = path.relative_to(ROOT) if kind == "plugin" else Path("annual-report-analysis") / path.relative_to(SKILL)
                archive.write(path, relative.as_posix())
            archive.write(ROOT / "LICENSE", "LICENSE" if kind == "plugin" else "annual-report-analysis/LICENSE")
            if kind == "plugin":
                for name in ("plugin.json", ".claude-plugin/plugin.json"):
                    archive.write(ROOT / name, name)
        print(target)


if __name__ == "__main__":
    build()
