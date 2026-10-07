import pytest

from compute_metabolism.v0.profiles import (
    APPROVED_N3_FINAL_PUBLIC_BITS,
    APPROVED_V0_PINSET_SHA256,
    APPROVED_V1_SOURCE_BINDING,
    CampaignLimits,
    N3_REFERENCE_PROVENANCE,
    get_profile,
    parse_cpu_list,
    parse_cpu_max,
)


def test_profiles_are_exact():
    from dataclasses import astuple
    assert [astuple(get_profile(key)) for key in ('2c','1c','0p5c')] == [
        ('2c',(0,1),None,None),('1c',(0,),None,None),('0p5c',(0,),50,100)]
    assert get_profile("2c").cpus == (0, 1)
    assert get_profile("1c").cpus == (0,)
    assert get_profile("0p5c").cpus == (0,)
    assert get_profile("0p5c").quota_percent == 50
    assert get_profile("0p5c").quota_period_ms == 100


def test_profile_cpu_set_and_quota_are_distinct():
    profile = get_profile("0p5c")
    assert profile.cpus == (0,)
    assert profile.quota_percent == 50

    unlimited = get_profile("1c")
    assert unlimited.cpus == (0,)
    assert unlimited.quota_percent is None


def test_limits_are_exact():
    limits = CampaignLimits()
    assert limits.per_run_wall_seconds == 180
    assert limits.total_wall_seconds == 4200
    assert limits.writer_bytes == 671088640
    assert limits.retained_run_bytes == 100663296
    assert limits.retained_total_bytes == 3221225472
    assert limits.memory_bytes == 4294967296
    assert limits.memory_swap_bytes == 0
    assert limits.omp_num_threads == 1
    assert limits.openblas_num_threads == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"per_run_wall_seconds": 9999},
        {"writer_bytes": -1},
    ],
)
def test_campaign_limits_refuse_constructor_overrides(overrides):
    with pytest.raises(TypeError):
        CampaignLimits(**overrides)


def test_approved_profile_registry_refuses_mutation():
    from compute_metabolism.v0.profiles import PROFILES

    with pytest.raises(TypeError):
        PROFILES["2c"] = get_profile("1c")


def test_approved_source_and_reference_identity_constants():
    assert APPROVED_V1_SOURCE_BINDING == (
        "f75980706aefbbd68cddce09549695c2f633905e01185f92f96660db81a9e2cd"
    )
    assert APPROVED_V0_PINSET_SHA256 == (
        "c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3"
    )
    assert APPROVED_N3_FINAL_PUBLIC_BITS == (
        "0x3f87fdfd0828277f",
        "0x3f77fdfb883c273f",
        "0x3fcff6ed62825295",
        "0x3fbff6e3e3c24415",
    )
    assert "ordinary-02/harness_output.json" in N3_REFERENCE_PROVENANCE
    assert "positive-03/SUMMARY.json" in N3_REFERENCE_PROVENANCE


def test_parse_cpu_list_returns_canonical_integer_tuple():
    assert parse_cpu_list("0-1,4") == (0, 1, 4)
    assert parse_cpu_list("4,0-1") == (0, 1, 4)
    assert parse_cpu_list("2,0,1") == (0, 1, 2)


@pytest.mark.parametrize(
    "raw",
    ["", "0,,1", "1,1", "-1", "0--1", "2-1", "1-", "a", "0-1,1"],
)
def test_parse_cpu_list_refuses_invalid_or_duplicate_cpus(raw):
    with pytest.raises(ValueError):
        parse_cpu_list(raw)


def test_parse_cpu_max_preserves_quota_and_period_microseconds():
    assert parse_cpu_max("50000 100000") == (50000, 100000)
    assert parse_cpu_max("max 100000") == (None, 100000)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "50000",
        "50000 100000 extra",
        "-1 100000",
        "0 100000",
        "50000 0",
        "50000 -1",
        "max 0",
        "MAX 100000",
        "oops 100000",
    ],
)
def test_parse_cpu_max_refuses_invalid_quota_or_period(raw):
    with pytest.raises(ValueError):
        parse_cpu_max(raw)


def test_unknown_profile_is_refused():
    with pytest.raises(KeyError):
        get_profile("3c")
