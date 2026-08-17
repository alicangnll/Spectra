"""Shared pytest configuration for the Spectra test suite.

Puts the repository root on sys.path so test modules can import
``spectra`` and ``tests.*`` helpers without each file repeating the
sys.path.insert boilerplate.

Stub installation (PySide6 stubs, IDA mocks) is intentionally NOT done
here: several test modules verify degradation paths without IDA/Qt
present and must control stub installation themselves. See
``tests/qt_stubs.py`` and ``tests/mocks/ida_mock.py``.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
