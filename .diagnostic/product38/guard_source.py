"""Verify the checked-out whole source and editable import used by the fixture."""

import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys


PIN = "b5a33c5b9191bef976e352b9feca14eaf93c9b7a"
SOURCE_FILES = (
    "dash/_patch.py",
    "dash/_utils.py",
    "dash/_callback.py",
    "dash/dash-renderer/src/actions/patch.ts",
    "dash/testing/browser.py",
    "dash/testing/plugin.py",
)


def git(*args):
    return subprocess.check_output(["git", *args])


root = Path.cwd().resolve()
head = git("rev-parse", "HEAD").decode().strip()
dirty = git("status", "--porcelain", "--untracked-files=no").decode()
report = {"root": str(root), "head": head, "tracked_status": dirty, "sources": {}}
assert head == PIN, report
assert not dirty, report
for filename in SOURCE_FILES:
    source = root / filename
    actual = source.read_bytes()
    pinned = git("show", f"{PIN}:{filename}")
    entry = {
        "blob": git("rev-parse", f"{PIN}:{filename}").decode().strip(),
        "sha256": hashlib.sha256(actual).hexdigest(),
        "bytes": len(actual),
        "matches_pinned_blob": actual == pinned,
    }
    report["sources"][filename] = entry
    assert actual == pinned, {"filename": filename, **entry}
if os.environ.get("PRODUCT38_GUARD_IMPORTS") == "1":
    import dash
    import dash._utils
    from dash import Patch

    assert Path(sys.prefix).resolve() == root / ".venv", sys.prefix
    imports = {
        "dash": str(Path(dash.__file__).resolve()),
        "Patch": str(Path(inspect.getfile(Patch)).resolve()),
        "to_json": str(Path(inspect.getfile(dash._utils.to_json)).resolve()),
        "python": sys.executable,
        "prefix": sys.prefix,
    }
    assert Path(imports["dash"]) == root / "dash/__init__.py", imports
    assert Path(imports["Patch"]) == root / "dash/_patch.py", imports
    assert Path(imports["to_json"]) == root / "dash/_utils.py", imports
    report["imports"] = imports
print("PINNED_SOURCE_GUARD " + json.dumps(report, sort_keys=True), flush=True)
