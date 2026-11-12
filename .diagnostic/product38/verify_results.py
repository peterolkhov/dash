"""Require the exact finite test census and ordinary assertion outcomes."""

import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


mode, xml_file, exit_file = sys.argv[1:]
cases = list(ET.parse(xml_file).getroot().iter("testcase"))
names = {case.attrib["name"] for case in cases}
public_names = {
    f"test_public_{surface}[{kind}]"
    for surface in ("producer", "browser")
    for kind in ("shared_mapping", "distinct_mapping", "keyword_only")
}
permanent_names = {
    "test_pat022_patch_update_shared_mapping",
    "test_pch008_patch_update_shared_mapping",
}
expected_names = public_names if mode == "public-green" else permanent_names
assert mode in ("public-green", "permanent-red", "permanent-green"), mode
failures = {case.attrib["name"] for case in cases if case.find("failure") is not None}
errors = [case.attrib for case in cases if case.find("error") is not None]
skips = [case.attrib for case in cases if case.find("skipped") is not None]
exit_code = Path(exit_file).read_text().strip()
expected_failures = permanent_names if mode == "permanent-red" else set()
summary = {"mode": mode, "names": sorted(names), "failures": sorted(failures), "errors": errors, "skips": skips, "exit": exit_code}
print(json.dumps(summary, indent=2), flush=True)
assert names == expected_names and len(cases) == len(expected_names), summary
assert failures == expected_failures and not errors and not skips, summary
assert exit_code == ("1" if expected_failures else "0"), summary
for case in cases:
    failure = case.find("failure")
    if failure is not None:
        assert "AssertionError" in "".join(failure.itertext()), ET.tostring(case)
print("FINITE_RESULT_CENSUS_CONFIRMED " + mode, flush=True)
