"""Smoke tests for the terminated 瞬在 branch.

These do not assert that the branch works -- it does not. They pin the observed
failure so a future attempt cannot silently regress into "looks like it runs".

API (established by inspection, not assumed):
    TransientUnit(F: complex, B: complex, U: complex)
        the three complex slots correspond to the theory's
        forward pass (F) / backward pass (B) / update operator (U)
    TransientMatrix(dt: float = 0.01)   -- an nn.Module expecting psi of shape
        (batch, 3); exposes evolve, interference_strength, interference_matrix,
        phase_coupling_matrix, eigenvalues

Root cause of exp1's failure (proved in docs/NEGATIVE-RESULT-TRANSIENT.md):
    interference_strength = sum_{i!=j} |I_ij|^2 with I_ij = psi_i conj(psi_j),
    and |I_ij|^2 = |psi_i|^2 |psi_j|^2. The modulus squared cancels the phase, so
    the metric cannot depend on phase by construction.
"""

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from transient import TransientMatrix, TransientUnit  # noqa: E402
from transient.dynamics import su3_generators  # noqa: E402

MODEL = TransientMatrix()
MODEL.eval()


def _psi(phases):
    return torch.tensor(
        [[complex(np.cos(p), np.sin(p)) for p in phases]], dtype=torch.complex64
    )


def test_transient_unit_holds_the_three_stages():
    """The unit's three complex slots map onto the theory's three stages."""
    u = TransientUnit(F=1 + 0j, B=2 + 0.5j, U=3 - 0.25j)
    assert isinstance(u.to_complex(), complex)


def test_transient_unit_rotate_changes_phase():
    """Phase is representable at unit level."""
    u1 = TransientUnit(F=1 + 0j, B=1 + 0j, U=1 + 0j)
    u2 = TransientUnit(F=1 + 0j, B=1 + 0j, U=1 + 0j)
    u1.rotate(np.pi / 2)
    assert u1.to_complex() != u2.to_complex(), "rotate() had no effect"


def test_su3_generators_are_eight_and_hermitian():
    """exp3 [1][2]: these two properties DID hold."""
    gens = su3_generators()
    assert len(gens) == 8, "SU(3) has eight generators"
    for g in gens:
        arr = g.detach().numpy() if hasattr(g, "detach") else np.asarray(g)
        assert np.allclose(arr, arr.conj().T, atol=1e-6), "generator not Hermitian"


def test_su3_decomposition_error_is_too_large():
    """exp3 [3]: the decomposition step failed with error 1.87e-02.

    Pinned as a known failure. If a rewrite brings the error below 1e-3, this test
    fails and the negative result should be revisited.
    """
    from transient.dynamics import decompose_into_su3
    rng = np.random.default_rng(0)
    a = rng.normal(size=(3, 3)) + 1j * rng.normal(size=(3, 3))
    h = (a + a.conj().T) / 2                      # an arbitrary Hermitian matrix
    out = decompose_into_su3(torch.tensor(h, dtype=torch.complex64))
    coeffs = out[0] if isinstance(out, (tuple, list)) else out
    coeffs = np.asarray(coeffs if not hasattr(coeffs, "detach")
                        else coeffs.detach().numpy(), dtype=complex).ravel()
    gens = [np.asarray(g.detach().numpy() if hasattr(g, "detach") else g,
                       dtype=complex) for g in su3_generators()]
    recon = sum(c * g for c, g in zip(coeffs, gens))
    err = float(np.linalg.norm(recon - h))
    assert err > 1e-3, (
        f"SU(3) decomposition error dropped to {err:.3e}; revisit "
        "docs/NEGATIVE-RESULT-TRANSIENT.md"
    )


def test_phase_coupling_matrix_is_zero_for_aligned_phases():
    """exp1: aligned phases gave an all-zero coupling matrix."""
    arr = MODEL.phase_coupling_matrix(_psi([0.0, 0.0, 0.0])).detach().numpy()
    assert arr.shape == (1, 3, 3), f"unexpected shape {arr.shape}"
    assert np.allclose(arr, 0.0, atol=1e-6)


def test_phase_coupling_does_vary_with_phase():
    """The phase information DOES exist -- just not in the strength metric.

    This is the contrast that makes the failure precise: angle(I) carries phase,
    interference_strength discards it.
    """
    aligned = MODEL.phase_coupling_matrix(_psi([0.0, 0.0, 0.0])).detach().numpy()
    mixed = MODEL.phase_coupling_matrix(_psi([0.0, np.pi / 2, np.pi])).detach().numpy()
    assert not np.allclose(aligned, mixed, atol=1e-6), (
        "phase coupling no longer responds to phase; the analysis in "
        "docs/NEGATIVE-RESULT-TRANSIENT.md assumes it does"
    )


def test_interference_strength_is_phase_insensitive():
    """exp1's core observation, now PROVEN and therefore hard-asserted.

    Four configurations including random per-unit phases; the original run
    reported an identical value for all of them. The spread must be exactly zero
    up to float32 rounding.
    """
    vals = []
    for phases in ([0.0, 0.0, 0.0],
                   [0.0, np.pi / 2, np.pi],
                   [0.3, 1.1, 2.7],
                   [1.9, 0.05, 3.0]):
        vals.append(float(MODEL.interference_strength(_psi(phases)).flatten()[0].real))
    spread = max(vals) - min(vals)
    assert spread < 1e-6, (
        f"phase now affects interference_strength (spread={spread:.2e}); the "
        "negative result may need revision -- see docs/NEGATIVE-RESULT-TRANSIENT.md"
    )
