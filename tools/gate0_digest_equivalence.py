"""Show that a later Gate 0 report differs from the one the designer reproduced on the home PC
(digest 2d05505d..., commit d0e45c5) ONLY in the label fields changed at closure.

Puts the old label strings back into the current deterministic section and recomputes the digest.

    python tools/gate0_digest_equivalence.py [report.json]
"""
import hashlib
import json
import sys
from pathlib import Path

HOME_PC_DIGEST = "2d05505d3c499f0c3ac94970b35dfd7258f1fc2913c3b9ecbbb871f36158aa98"
OLD_LABELS = {
    "benchmark_3": ("gendot_n50_c1e25_v1: frozen fixture generated once by the published GenDot algorithm "
                    "(Ogita-Rump-Oishi 2005, Alg. 6.1), designer-approved 2026-10-01"),
    "open_items": ["G0-6: designer's home-PC run with matching deterministic_digest",
                   "GenDot generator is the implementer's reconstruction (paper unreachable from the build "
                   "environment); designer to diff against Algorithm 6.1. Affects the fixture's name only, "
                   "not its oracle or verdicts"],
}


def digest(det: dict) -> str:
    return hashlib.sha256(json.dumps(det, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def main(path: str) -> int:
    det = json.loads(Path(path).read_text(encoding="utf-8"))["deterministic"]
    changed = {k for k in OLD_LABELS if det.get(k) != OLD_LABELS[k]}
    restored = dict(det, **OLD_LABELS)
    same = digest(restored) == HOME_PC_DIGEST
    print(f"current digest        {digest(det)}")
    print(f"with old labels       {digest(restored)}")
    print(f"home-PC digest        {HOME_PC_DIGEST}")
    print(f"fields that differ    {sorted(changed)}")
    print("EQUIVALENT: only the closure labels changed" if same else "NOT EQUIVALENT")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "reports/cloud-container-2026-10-01/gate0_report.json"))
