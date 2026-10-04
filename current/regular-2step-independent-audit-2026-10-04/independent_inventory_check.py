import xml.etree.ElementTree as ET
from pathlib import Path
root=Path(r"D:\regular2step-independent-audit-retry-2026-10-04\repo\runtime_trace\regular_2step\artifacts\validation")
def ids(stem):
 r=ET.parse(root/(stem+".xml")).getroot()
 return {(x.attrib.get("classname"),x.attrib.get("name")) for x in r.iter("testcase")}
sets={s:ids(s) for s in ("final-new-63","final-caller-101","final-regular-479","whole-fix1-covering")}
base=sets["final-new-63"]|sets["final-caller-101"]|sets["final-regular-479"]
cover=sets["whole-fix1-covering"]
print("BASE_UNIQUE",len(base))
print("COVER_UNIQUE",len(cover))
print("OVERLAP",len(base&cover))
print("COVER_NEW",len(cover-base))
print("TOTAL_UNIQUE",len(base|cover))
print("NEW_COVER_IDS")
for x in sorted(cover-base): print(x)
