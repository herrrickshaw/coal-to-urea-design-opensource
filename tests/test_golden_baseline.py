"""Refactor guard: every numeric output must equal the pre-refactor value exactly."""
from __future__ import annotations

import json
from pathlib import Path

from golden_cases import compute_cases

GOLDEN = Path(__file__).with_name("golden_baseline.json")


def test_outputs_identical_to_pre_refactor_baseline():
    assert compute_cases() == json.loads(GOLDEN.read_text())
