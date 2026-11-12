"""Check the exact candidate tree, source bytes and native imports."""

import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys


def git(*args):
    return subprocess.check_output(["git", *args])


packet = Path(__file__).resolve().parent
manifest = json.loads((packet / "manifest.json").read_text())
pin = manifest["base_pin"]
candidate = os.environ["CANDIDATE_COMMIT"]
phase = sys.argv[1]
assert phase in ("candidate", "red"), phase
root = Path.cwd().resolve()
head = git("rev-parse", "HEAD").decode().strip()
assert head == candidate and len(candidate) == 40, (head, candidate)
assert git("merge-base", pin, head).decode().strip() == pin
changed = set(git("diff", "--name-only", pin, head).decode().splitlines())
expected_changed = {entry["path"] for entry in manifest["sources"]}
assert changed == expected_changed, (changed, expected_changed)
dirty = git("status", "--porcelain", "--untracked-files=no").decode()
expected_dirty = " M dash/_patch.py\n" if phase == "red" else ""
assert dirty == expected_dirty, (phase, dirty)
assert not git("diff", "--cached", "--name-only"), "Unexpected staged files"
report = {"root": str(root), "head": head, "phase": phase, "sources": {}}
for entry in manifest["sources"]:
    filename = entry["path"]
    pinned = git("show", f"{pin}:{filename}")
    original_sha = hashlib.sha256(pinned).hexdigest()
    assert original_sha == entry["original_sha256"], filename
    assert git("rev-parse", f"{pin}:{filename}").decode().strip() == entry["original_git_blob"]
    assert git("rev-parse", f"{head}:{filename}").decode().strip() == entry["after_git_blob"]
    actual = (root / filename).read_bytes()
    expected_sha = entry["after_sha256"]
    if phase == "red" and filename == "dash/_patch.py":
        expected_sha = entry["original_sha256"]
    actual_sha = hashlib.sha256(actual).hexdigest()
    assert actual_sha == expected_sha, (filename, actual_sha, expected_sha)
    report["sources"][filename] = actual_sha
for entry in manifest["unchanged_critical_sources"]:
    filename = entry["path"]
    actual = (root / filename).read_bytes()
    assert git("rev-parse", f"{pin}:{filename}").decode().strip() == entry["git_blob"]
    assert git("show", f"{pin}:{filename}") == actual, filename
    assert hashlib.sha256(actual).hexdigest() == entry["sha256"], filename
    report["sources"][filename] = entry["sha256"]
fixture = manifest["public_fixture"]
assert hashlib.sha256((packet / fixture["path"]).read_bytes()).hexdigest() == fixture["sha256"]
assert Path(sys.prefix).resolve() == root / ".venv", sys.prefix
assert Path(os.environ["VIRTUAL_ENV"]).resolve() == root / ".venv"
if os.environ.get("PRODUCT38_GUARD_IMPORTS") == "1":
    import dash
    import dash._utils
    from dash import Patch

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
print("EXACT_CANDIDATE_SOURCE_GUARD " + json.dumps(report, sort_keys=True), flush=True)
