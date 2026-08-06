"""JADX integration package for Spectra.

Provides Android APK reverse engineering capabilities using JADX decompiler.
"""

from .api import JadxAnalyzer, create_jadx_tools

__all__ = ['JadxAnalyzer', 'create_jadx_tools']
