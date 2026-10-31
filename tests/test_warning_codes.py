"""Tests that all warning codes emitted by text_frontend match the README table exactly."""

from __future__ import annotations

import re
from pathlib import Path


def _get_emitted_codes() -> set[str]:
    package_dir = Path(__file__).resolve().parent.parent / "text_frontend"
    emitted = set()
    pattern = re.compile(r'NormalizationWarning\([^)]*code=["\']([A-Z0-9_]+)["\']', re.DOTALL)
    for py_file in package_dir.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            emitted.add(m.group(1))
    return emitted


def _get_readme_codes() -> set[str]:
    readme_path = Path(__file__).resolve().parent.parent / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")
    table_pattern = re.compile(r"^\|\s*`([A-Z0-9_]+)`\s*\|\s*`([a-z]+)`\s*\|", re.MULTILINE)
    codes = set()
    for m in table_pattern.finditer(readme_text):
        code, sev = m.group(1), m.group(2)
        assert sev in ("info", "warning", "error"), f"Invalid severity '{sev}' for code '{code}'"
        codes.add(code)
    return codes


def test_warning_codes_bidirectional_match():
    emitted = _get_emitted_codes()
    documented = _get_readme_codes()

    missing_in_readme = emitted - documented
    extra_in_readme = documented - emitted

    assert not missing_in_readme, f"Warning codes emitted by code but missing in README: {missing_in_readme}"
    assert not extra_in_readme, f"Warning codes in README but never emitted by code: {extra_in_readme}"
    assert emitted == documented
