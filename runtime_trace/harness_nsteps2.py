"""Original gala API; regular initial state; exactly one step; no monkeypatches."""
import hashlib
import importlib.metadata as metadata
import json
import os
import platform
import struct
import time
from pathlib import Path

import numpy as np
import gala.dynamics as gd
import gala.integrate as gi
import gala.potential as gp
import gala.units as gu


def bits(value):
    return f"0x{struct.unpack('<Q', struct.pack('<d', float(value)))[0]:016x}"


def main():
    out = Path(os.environ["RT_OUTPUT"])
    root = Path(__file__).resolve().parents[1]
    wheel = root / "audit/gate2c1/vendor/gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl"
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == "cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0"
    w0 = gd.PhaseSpacePosition(pos=np.array([0., 0.]), vel=np.array([.25, .125]))
    H = gp.Hamiltonian(gp.HenonHeilesPotential(units=gu.dimensionless))
    started = time.perf_counter()
    orbit = H.integrate_orbit(w0, dt=1/64, n_steps=2, Integrator=gi.LeapfrogIntegrator, cython_if_possible=True)
    elapsed = time.perf_counter() - started
    result = {"orbit": "regular", "n_steps": 1, "dt_bits": bits(1/64),
              "output_bits": [bits(x) for x in [*orbit.xyz.value[:, -1], *orbit.v_xyz.value[:, -1]]],
              "python": platform.python_version(), "platform": platform.platform(),
              "packages": {n: metadata.version(n) for n in ["gala", "numpy", "astropy", "scipy"]},
              "integrate_call_wall_seconds": elapsed}
    (out / "harness_output.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
