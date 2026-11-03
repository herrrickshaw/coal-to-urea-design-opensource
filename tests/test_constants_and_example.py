from __future__ import annotations

import math
import runpy
from pathlib import Path

import pytest

from coal_to_urea import gasifier, shift_reactor
from coal_to_urea.constants import wgs_equilibrium_K
from coal_to_urea.properties import GasMixture

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "full_chain_worked_example.py"


def test_wgs_equilibrium_K_matches_moe_correlation():
    assert wgs_equilibrium_K(1000.0) == math.exp(4577.8 / 1000.0 - 4.33)


def test_private_aliases_point_to_shared_function():
    assert gasifier._wgs_equilibrium_K is wgs_equilibrium_K
    assert shift_reactor._wgs_equilibrium_K is wgs_equilibrium_K


def test_gas_mixture_rejects_bad_fractions():
    with pytest.raises(ValueError, match="sum to 1.0"):
        GasMixture({"Hydrogen": 0.5, "Nitrogen": 0.3})


def test_worked_example_runs_and_reports_benchmark_gap(capsys):
    runpy.run_path(str(EXAMPLE), run_name="__main__")
    out = capsys.readouterr().out
    assert "Urea produced:" in out
    assert "Difference: -13.6%" in out


def test_worked_example_stdout_is_byte_identical_to_golden(capsys):
    runpy.run_path(str(EXAMPLE), run_name="__main__")
    golden = (Path(__file__).parent / "golden_example_stdout.txt").read_text()
    assert capsys.readouterr().out == golden
