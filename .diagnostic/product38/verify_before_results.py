"""Require six native cases, four controls passing and two real assertion failures."""

import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


report_path = Path(sys.argv[1])
log_path = Path(sys.argv[2])
exit_path = Path(sys.argv[3])
root = ET.parse(report_path).getroot()
cases = list(root.iter("testcase"))
expected_failures = {
    "test_public_producer[shared_mapping]",
    "test_public_browser[shared_mapping]",
}
expected_names = {
    f"test_public_{surface}[{mode}]"
    for surface in ("producer", "browser")
    for mode in ("shared_mapping", "distinct_mapping", "keyword_only")
}
actual_names = {case.attrib["name"] for case in cases}
failed = {case.attrib["name"] for case in cases if case.find("failure") is not None}
errors = [case.attrib for case in cases if case.find("error") is not None]
skips = [case.attrib for case in cases if case.find("skipped") is not None]
summary = {
    "state": "native before result verification",
    "cases": len(cases),
    "names": sorted(actual_names),
    "failed": sorted(failed),
    "errors": errors,
    "skips": skips,
    "pytest_exit": exit_path.read_text().strip(),
}
print(json.dumps(summary, indent=2), flush=True)
assert len(cases) == 6 and actual_names == expected_names, summary
assert not errors and not skips and failed == expected_failures, summary
assert exit_path.read_text().strip() == "1", summary
for case in cases:
    failure = case.find("failure")
    if failure is not None:
        assert "AssertionError" in "".join(failure.itertext()), ET.tostring(case)
logs = log_path.read_text()
assert "ACTUAL_PRODUCER shared_mapping" in logs, "Missing actual producer payload"
assert "ACTUAL_BROWSER shared_mapping" in logs, "Missing actual browser payload"
assert "ACTUAL_BROWSER_CAPABILITIES" in logs, "Missing actual Chrome runtime"
print("BEFORE_CONFIRMED: two native shared-mapping assertion failures; four controls pass.")
