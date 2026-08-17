#!/usr/bin/env python3
"""Version consistency check.

update.json is the single source of truth for the Spectra version.
This script fails (exit 1) when any of the other version carriers
disagree with it, preventing the 1.2.1 / 1.3.8 / 5.0.0 sprawl from
coming back.

Checked locations:
  - update.json            (source of truth)
  - plugin.json            (Binary Ninja plugin metadata)
  - ida-plugin.json        (IDA plugin metadata)
  - spectra/constants.py   (PLUGIN_VERSION fallback literal)
  - Dockerfile             (LABEL version)
  - spectra_jadx.py        (standalone fallback literal)

Usage: python3 scripts/check_versions.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(location: str, found: str, expected: str) -> None:
    print(f"  ✘ {location}: {found!r} != {expected!r}")
    results.append(False)


def ok(location: str, found: str) -> None:
    print(f"  ✔ {location}: {found}")
    results.append(True)


results: list[bool] = []

with open(ROOT / "update.json", encoding="utf-8") as f:
    expected = json.load(f)["version"]
print(f"Source of truth — update.json: {expected}\n")

# plugin.json
plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
if plugin["version"] == expected:
    ok("plugin.json", plugin["version"])
else:
    fail("plugin.json", plugin["version"], expected)

# ida-plugin.json
ida = json.loads((ROOT / "ida-plugin.json").read_text(encoding="utf-8"))
ida_ver = ida["plugin"]["version"]
if ida_ver == expected:
    ok("ida-plugin.json", ida_ver)
else:
    fail("ida-plugin.json", ida_ver, expected)

# spectra/constants.py fallback literal
constants_src = (ROOT / "spectra" / "constants.py").read_text(encoding="utf-8")
m = re.search(r'PLUGIN_VERSION\s*=\s*"([^"]+)"\s*#\s*Fallback', constants_src)
if m:
    if m.group(1) == expected:
        ok("spectra/constants.py (fallback)", m.group(1))
    else:
        fail("spectra/constants.py (fallback)", m.group(1), expected)
else:
    fail("spectra/constants.py (fallback)", "<pattern not found>", expected)

# Dockerfile LABEL version
dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
m = re.search(r'LABEL\s+version="([^"]+)"', dockerfile)
if m:
    if m.group(1) == expected:
        ok("Dockerfile (LABEL)", m.group(1))
    else:
        fail("Dockerfile (LABEL)", m.group(1), expected)
else:
    fail("Dockerfile (LABEL)", "<pattern not found>", expected)

# spectra_jadx.py standalone fallback literal
jadx_src = (ROOT / "spectra_jadx.py").read_text(encoding="utf-8")
m = re.search(r'__version__\s*=\s*"([^"]+)"\s*#\s*standalone', jadx_src)
if m:
    if m.group(1) == expected:
        ok("spectra_jadx.py (standalone fallback)", m.group(1))
    else:
        fail("spectra_jadx.py (standalone fallback)", m.group(1), expected)
else:
    # No standalone fallback is also acceptable (package always present).
    print("  ~ spectra_jadx.py: no standalone fallback literal (ok)")
    results.append(True)

print()
if all(results):
    print(f"ALL VERSIONS CONSISTENT: {expected}")
    sys.exit(0)
print(f"VERSION MISMATCH — expected {expected} everywhere. Fix the ✘ entries above.")
sys.exit(1)
