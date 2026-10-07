"""Shared exact profiles and resource limits for Compute Metabolism V0.

``parse_cpu_max`` returns cgroup v2 ``cpu.max`` values in microseconds as
``(quota_usec, period_usec)``. An unlimited ``max`` quota is represented by
``None``; callers that need raw enforcement evidence must separately retain
the original file text.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class ProfileSpec:
    """Requested guest CPU set and optional cgroup CPU quota."""

    key: str
    cpus: tuple[int, ...]
    quota_percent: int | None
    quota_period_ms: int | None


@dataclass(frozen=True, init=False)
class CampaignLimits:
    """Fixed resource ceilings shared by all V0 campaign attempts."""

    per_run_wall_seconds: int
    total_wall_seconds: int
    writer_bytes: int
    retained_run_bytes: int
    retained_total_bytes: int
    memory_bytes: int
    memory_swap_bytes: int
    omp_num_threads: int
    openblas_num_threads: int

    def __init__(self) -> None:
        object.__setattr__(self, "per_run_wall_seconds", 180)
        object.__setattr__(self, "total_wall_seconds", 4200)
        object.__setattr__(self, "writer_bytes", 671088640)
        object.__setattr__(self, "retained_run_bytes", 100663296)
        object.__setattr__(self, "retained_total_bytes", 3221225472)
        object.__setattr__(self, "memory_bytes", 4294967296)
        object.__setattr__(self, "memory_swap_bytes", 0)
        object.__setattr__(self, "omp_num_threads", 1)
        object.__setattr__(self, "openblas_num_threads", 1)


PROFILES: Mapping[str, ProfileSpec] = MappingProxyType(
    {
        "2c": ProfileSpec("2c", (0, 1), None, None),
        "1c": ProfileSpec("1c", (0,), None, None),
        "0p5c": ProfileSpec("0p5c", (0,), 50, 100),
    }
)

APPROVED_V1_SOURCE_BINDING = (
    "f75980706aefbbd68cddce09549695c2f633905e01185f92f96660db81a9e2cd"
)
APPROVED_V0_PINSET_SHA256 = (
    "c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3"
)
APPROVED_N3_FINAL_PUBLIC_BITS = (
    "0x3f87fdfd0828277f",
    "0x3f77fdfb883c273f",
    "0x3fcff6ed62825295",
    "0x3fbff6e3e3c24415",
)
N3_REFERENCE_PROVENANCE = (
    "Task 8 ordinary-02/harness_output.json and certified "
    "positive-03/SUMMARY.json with the approved source pinset"
)

_DECIMAL = re.compile(r"[0-9]+\Z")


def get_profile(key: str) -> ProfileSpec:
    """Return a known profile, refusing unknown keys."""

    try:
        return PROFILES[key]
    except KeyError:
        raise KeyError(f"unknown CPU profile: {key!r}") from None


def parse_cpu_list(raw: str) -> tuple[int, ...]:
    """Parse a cgroup CPU list into a sorted tuple, rejecting duplicates."""

    if not isinstance(raw, str) or not raw:
        raise ValueError("CPU list must be a non-empty string")

    cpus: list[int] = []
    for item in raw.split(","):
        if not item:
            raise ValueError("CPU list contains an empty item")
        bounds = item.split("-")
        if len(bounds) == 1:
            if not _DECIMAL.fullmatch(bounds[0]):
                raise ValueError(f"invalid CPU number: {bounds[0]!r}")
            cpus.append(int(bounds[0]))
        elif len(bounds) == 2:
            start_text, end_text = bounds
            if not _DECIMAL.fullmatch(start_text) or not _DECIMAL.fullmatch(
                end_text
            ):
                raise ValueError(f"invalid CPU range: {item!r}")
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError(f"descending CPU range: {item!r}")
            cpus.extend(range(start, end + 1))
        else:
            raise ValueError(f"invalid CPU range: {item!r}")

    if len(set(cpus)) != len(cpus):
        raise ValueError("CPU list contains duplicate CPUs")
    return tuple(sorted(cpus))


def parse_cpu_max(raw: str) -> tuple[int | None, int]:
    """Parse cgroup v2 ``cpu.max`` into quota and period microseconds."""

    if not isinstance(raw, str):
        raise ValueError("cpu.max must be a string")
    fields = raw.split()
    if len(fields) != 2:
        raise ValueError("cpu.max must contain exactly quota and period")

    quota_text, period_text = fields
    if not _DECIMAL.fullmatch(period_text):
        raise ValueError(f"invalid cpu.max period: {period_text!r}")
    period_usec = int(period_text)
    if period_usec <= 0:
        raise ValueError("cpu.max period must be positive")

    if quota_text == "max":
        return None, period_usec
    if not _DECIMAL.fullmatch(quota_text):
        raise ValueError(f"invalid cpu.max quota: {quota_text!r}")
    quota_usec = int(quota_text)
    if quota_usec <= 0:
        raise ValueError("cpu.max quota must be positive")
    return quota_usec, period_usec
