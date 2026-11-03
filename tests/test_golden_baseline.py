"""Refactor guard: every numeric output must match the pre-refactor value.

Floats are compared with a tight relative tolerance (1e-9): the last ulp differs between
platforms (libm / BLAS builds), so bit-exact equality is not reproducible across machines.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from golden_cases import compute_cases

GOLDEN = Path(__file__).with_name("golden_baseline.json")
REL_TOL = 1e-9


def _assert_close(actual, expected, path="root"):
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and actual.keys() == expected.keys(), path
        for k in expected:
            _assert_close(actual[k], expected[k], f"{path}.{k}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), path
        for i, (a, e) in enumerate(zip(actual, expected)):
            _assert_close(a, e, f"{path}[{i}]")
    elif isinstance(expected, float):
        assert actual == pytest.approx(expected, rel=REL_TOL, abs=1e-12), path
    else:
        assert actual == expected, path


def test_outputs_identical_to_pre_refactor_baseline():
    _assert_close(compute_cases(), json.loads(GOLDEN.read_text()))
