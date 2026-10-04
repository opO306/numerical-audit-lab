import xml.etree.ElementTree as ET
from pathlib import Path
root=Path(r"D:\regular2step-independent-audit-retry-2026-10-04\repo\runtime_trace\regular_2step\artifacts\validation")
for stem in ("final-new-63","final-caller-101","final-regular-479","whole-fix1-covering"):
 p=root/(stem+".xml")
 tree=ET.parse(p).getroot()
 suites=[tree] if tree.tag=="testsuite" else list(tree.findall(".//testsuite"))
 tests=sum(int(float(x.attrib.get("tests",0))) for x in suites)
 failures=sum(int(float(x.attrib.get("failures",0))) for x in suites)
 errors=sum(int(float(x.attrib.get("errors",0))) for x in suites)
 skipped=sum(int(float(x.attrib.get("skipped",0))) for x in suites)
 exit_text=(root/(stem+".exit")).read_text().strip()
 time_text=(root/(stem+".time")).read_text().strip()
 log=(root/(stem+".log")).read_text(encoding="utf-8",errors="replace")
 print(stem,{"tests":tests,"failures":failures,"errors":errors,"skipped":skipped,"exit":exit_text,"time":time_text,"log_tail":log.splitlines()[-2:]})
