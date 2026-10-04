"""Lab V1 data/validation boundary. No executor or arithmetic oracle imports."""
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from pathlib import Path

SPEC_SHA256 = "3217fc38aa798fff3ffea8072cecafaecac9f98be85589e9fa35a9dc6aa8119b"
SCOPE = "ARITHMETIC_ONLY"
J_STATUS = "J_NOT_VERIFIED"
FAST_STATUS = "EXPERIMENTAL / OPT-IN"
ORDER = ("i.x", "i.y", "i.z", "j.x", "j.y", "j.z")
MANIFEST_PATH = Path(__file__).with_name("semantic_manifest_v1.json")
if sha256(MANIFEST_PATH.read_bytes()).hexdigest() != SPEC_SHA256:
    raise RuntimeError("Lab semantic manifest byte hash mismatch")


@dataclass(frozen=True)
class Grid:
    width: int
    frac_bits: int
    kind: str = "signed_fx"
    rounding: str = "nearest_even"
    overflow: str = "refuse"


@dataclass(frozen=True)
class Ratio:
    numerator: int
    denominator: int


@dataclass(frozen=True)
class DriftInput:
    position_grid: Grid
    momentum_grid: Grid
    r_i: tuple
    r_j: tuple
    p_i: tuple
    p_j: tuple
    mass_i: Ratio
    mass_j: Ratio
    dt: Ratio
    spec_sha256: str = SPEC_SHA256


@dataclass(frozen=True)
class KickInput:
    momentum_grid: Grid
    impulse_grid: Grid
    p_i: tuple
    p_j: tuple
    J_raw: tuple
    spec_sha256: str = SPEC_SHA256


@dataclass(frozen=True)
class Failure:
    code: str
    phase: str
    atom: str
    component: str
    message: str
    scope: str = SCOPE
    j_status: str = J_STATUS
    spec_sha256: str = SPEC_SHA256


class LabRefusal(ValueError):
    def __init__(self, failure: Failure):
        self.failure = failure
        super().__init__(failure.message)


def refuse(code, phase="input", atom="", component="", message=""):
    raise LabRefusal(Failure(code, phase, atom, component, message or code))


@dataclass(frozen=True)
class DriftResult:
    displacement: tuple[Fraction | Ratio, ...]
    endpoint: tuple[Fraction | Ratio, ...]
    delta_i: tuple
    delta_j: tuple
    r_i: tuple
    r_j: tuple
    checked_order: tuple = ORDER
    scope: str = SCOPE
    j_status: str = J_STATUS
    spec_sha256: str = SPEC_SHA256


@dataclass(frozen=True)
class KickResult:
    exact_momentum: tuple[Fraction | Ratio, ...]
    p_i: tuple
    p_j: tuple
    checked_order: tuple = ORDER
    scope: str = SCOPE
    j_status: str = J_STATUS
    spec_sha256: str = SPEC_SHA256


@dataclass(frozen=True)
class GeometryResult:
    tau: Fraction
    min_R2: Fraction
    stored_R2: Fraction
    threshold: Fraction
    segment_intrusion: bool
    stored_intrusion: bool
    domain: str = "EXACT_THRESHOLD_ONLY"
    scope: str = SCOPE
    j_status: str = J_STATUS
    spec_sha256: str = SPEC_SHA256


@dataclass(frozen=True)
class GuardedResult:
    drift: DriftResult
    geometry: GeometryResult
    scope: str = SCOPE
    j_status: str = J_STATUS
    spec_sha256: str = SPEC_SHA256


def validate_grid(grid, field):
    if type(grid) is not Grid:
        refuse("INPUT_SCHEMA", message=f"{field}: expected Lab Grid")
    if (type(grid.width) is not int or type(grid.frac_bits) is not int
            or not 2 <= grid.width <= 4096 or not 0 <= grid.frac_bits < grid.width
            or type(grid.kind) is not str or grid.kind != "signed_fx"
            or type(grid.rounding) is not str or grid.rounding != "nearest_even"
            or type(grid.overflow) is not str or grid.overflow != "refuse"):
        refuse("PROFILE_UNSUPPORTED", message=f"{field}: unsupported grid semantics")


def validate_ratio(value, field, positive=False):
    if (type(value) is not Ratio or type(value.numerator) is not int
            or type(value.denominator) is not int or value.denominator <= 0):
        refuse("RATIONAL_INVALID", message=f"{field}: exact integer pair with positive denominator required")
    if positive and value.numerator <= 0:
        refuse("RATIONAL_NONPOSITIVE", message=f"{field}: must be positive")


def _raw_vector(values, grid, field):
    if type(values) is not tuple or len(values) != 3:
        refuse("INPUT_SCHEMA", message=f"{field}: immutable three-lane tuple required")
    lo, hi = -(1 << (grid.width - 1)), (1 << (grid.width - 1)) - 1
    for axis, raw in zip("xyz", values):
        if type(raw) is not int:
            refuse("INPUT_SCHEMA", component=axis, message=f"{field}.{axis}: exact int required")
        if not lo <= raw <= hi:
            refuse("RAW_RANGE", component=axis, message=f"{field}.{axis}: raw outside signed grid")


def _spec(value):
    if type(value) is not str or value != SPEC_SHA256:
        refuse("SPEC_MISMATCH", message="Lab V1 semantic SHA-256 required")


def validate_drift(request):
    if type(request) is not DriftInput:
        refuse("INPUT_SCHEMA", message="expected Lab DriftInput")
    _spec(request.spec_sha256)
    validate_grid(request.position_grid, "position_grid")
    validate_grid(request.momentum_grid, "momentum_grid")
    _raw_vector(request.r_i, request.position_grid, "r_i")
    _raw_vector(request.r_j, request.position_grid, "r_j")
    _raw_vector(request.p_i, request.momentum_grid, "p_i")
    _raw_vector(request.p_j, request.momentum_grid, "p_j")
    validate_ratio(request.mass_i, "mass_i", positive=True)
    validate_ratio(request.mass_j, "mass_j", positive=True)
    validate_ratio(request.dt, "dt")


def validate_kick(request):
    if type(request) is not KickInput:
        refuse("INPUT_SCHEMA", message="expected Lab KickInput")
    _spec(request.spec_sha256)
    validate_grid(request.momentum_grid, "momentum_grid")
    validate_grid(request.impulse_grid, "impulse_grid")
    if request.momentum_grid != request.impulse_grid:
        refuse("GRID_MISMATCH", message="momentum and J grid must be identical")
    _raw_vector(request.p_i, request.momentum_grid, "p_i")
    _raw_vector(request.p_j, request.momentum_grid, "p_j")
    _raw_vector(request.J_raw, request.momentum_grid, "J_raw")
