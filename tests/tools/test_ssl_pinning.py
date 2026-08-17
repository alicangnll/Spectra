"""Tests for structural SSL pinning detection (spectra/tools/ssl_pinning.py).

The analyzer is a pure function over collected facts (imports, defined
symbols, strings), so the verdict logic is testable without a disassembler.
The IDA collector is exercised through the shared IDA mocks; the Binary
Ninja collector through a minimal fake BinaryView.
"""

from __future__ import annotations

import importlib
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tests.mocks.ida_mock import install_ida_mocks

install_ida_mocks()

from spectra.tools import ssl_pinning
from spectra.tools.ssl_pinning import (
    SSL_PINNING_PATTERNS,
    _classify_string,
    _collect_facts_binja,
    _collect_facts_ida,
    _detect_ssl_pinning_ida,
    _match_verify_import,
    analyze_pinning_facts,
    format_ssl_pinning_report,
    get_bypass_techniques,
)

# A realistic base64-encoded sha256 pin (OkHttp CertificatePinner format).
_OKHTTP_PIN = "sha256/7HIpactkIAq2Y49orFOOQKurWxmmSFZhBCoQwqppTBo="


def setUpModule():
    """Re-bind the module under test to the IDA mocks now live in sys.modules.

    Other test modules also call install_ida_mocks() at import time, and the
    last install wins in sys.modules. Reloading after all imports guarantees
    ssl_pinning.idautils/idaapi/idc reference the same mock objects the tests
    configure — otherwise full-suite runs patch a mock the module never uses.
    """
    importlib.reload(ssl_pinning)


class TestStringClassification(unittest.TestCase):
    def test_okhttp_pin(self):
        result = _classify_string(_OKHTTP_PIN)
        assert result is not None
        assert result["kind"] == "pin_material"
        assert result["framework"] == "okhttp"

    def test_pem_certificate(self):
        pem = "-----BEGIN CERTIFICATE-----\nMIIDdzCCAl+gAwIBAgIEAgAAuTANBg"
        result = _classify_string(pem)
        assert result is not None
        assert result["kind"] == "pin_material"

    def test_hpkp_pin_list(self):
        result = _classify_string('pin-sha256="d6qzRu9zOECb90Uez27xWjNQp3E="; pin-sha256="E9CZ9I="')
        assert result is not None
        assert result["kind"] == "pin_material"

    def test_hex64_possible_pin(self):
        result = _classify_string("a" * 64)
        assert result is not None
        assert result["kind"] == "possible_pin"

    def test_hex40_possible_pin(self):
        result = _classify_string("0123456789abcdef" * 2 + "01234567")
        assert result is not None
        assert result["kind"] == "possible_pin"

    def test_plain_string_not_pin(self):
        assert _classify_string("https://api.example.com/v1") is None

    def test_short_hex_not_pin(self):
        assert _classify_string("deadbeef") is None

    def test_sha256_slash_garbage_not_pin(self):
        assert _classify_string("sha256/not-a-valid-hash!!") is None


class TestVerifyImportMatching(unittest.TestCase):
    def test_exact_match(self):
        assert _match_verify_import("SSL_CTX_set_verify") == "openssl"

    def test_macho_leading_underscore(self):
        assert _match_verify_import("_SSL_CTX_set_custom_verify") == "openssl"

    def test_elf_versioned_symbol(self):
        assert _match_verify_import("SSL_get_verify_result@OPENSSL_1_1_0") == "openssl"

    def test_sectrust(self):
        assert _match_verify_import("_SecTrustSetAnchorCertificates") == "sectrust"

    def test_unrelated_symbol(self):
        assert _match_verify_import("memcpy") is None


class TestAnalyzePinningFacts(unittest.TestCase):
    def test_no_evidence(self):
        result = analyze_pinning_facts(
            imports=[{"address": 0x1000, "symbol": "memcpy", "callers": []}],
            defined_names=[{"address": 0x2000, "name": "main"}],
            strings=[{"address": 0x3000, "value": "hello world"}],
        )
        assert result["detected"] is False
        assert result["confidence"] == "none"
        assert result["frameworks"] == []

    def test_okhttp_pin_string_is_high_confidence(self):
        result = analyze_pinning_facts([], [], [{"address": 0x9000, "value": _OKHTTP_PIN}])
        assert result["detected"] is True
        assert result["confidence"] == "high"
        assert "okhttp" in result["frameworks"]

    def test_embedded_pem_is_high_confidence(self):
        pem = "-----BEGIN CERTIFICATE-----\nMIIDdzCCAl+gAwIBAgIEAgAAuTANBg\n-----END CERTIFICATE-----"
        result = analyze_pinning_facts([], [], [{"address": 0x9000, "value": pem}])
        assert result["confidence"] == "high"
        kinds = [f["kind"] for f in result["findings"]]
        assert "pin_material" in kinds

    def test_native_trust_symbol_is_high_confidence(self):
        result = analyze_pinning_facts(
            imports=[],
            defined_names=[
                {"address": 0x2000, "name": "Java_com_example_net_NetworkUtils_checkServerTrusted"}
            ],
            strings=[],
        )
        assert result["detected"] is True
        assert result["confidence"] == "high"
        assert "trust_manager" in result["frameworks"]
        # The symbol itself must be offered as a hook target.
        assert any(t["address"] == 0x2000 for t in result["hook_targets"])

    def test_jni_j_prefix_symbol_counts(self):
        result = analyze_pinning_facts(
            [], [{"address": 0x2000, "name": "j_checkServerTrusted"}], []
        )
        assert "trust_manager" in result["frameworks"]

    def test_ida_auto_names_ignored(self):
        result = analyze_pinning_facts([], [{"address": 0x2000, "name": "sub_140001200"}], [])
        assert result["frameworks"] == []

    def test_strong_verify_import_with_caller_is_high(self):
        caller = {"address": 0x5000, "name": "init_ssl_context"}
        result = analyze_pinning_facts(
            imports=[{"address": 0x4000, "symbol": "SSL_CTX_set_custom_verify", "callers": [caller]}],
            defined_names=[],
            strings=[],
        )
        assert result["confidence"] == "high"
        assert "openssl" in result["frameworks"]
        # The caller is a concrete hook/patch target.
        assert any(t["address"] == 0x5000 for t in result["hook_targets"])

    def test_weak_verify_import_with_caller_is_medium(self):
        result = analyze_pinning_facts(
            imports=[
                {
                    "address": 0x4000,
                    "symbol": "SecTrustEvaluateWithError",
                    "callers": [{"address": 0x5000, "name": "verify"}],
                }
            ],
            defined_names=[],
            strings=[],
        )
        assert result["confidence"] == "medium"

    def test_pinning_specific_import_without_caller_is_medium(self):
        result = analyze_pinning_facts(
            imports=[{"address": 0x4000, "symbol": "WinHttpSetOption", "callers": []}],
            defined_names=[],
            strings=[],
        )
        assert result["confidence"] == "medium"
        assert "winhttp" in result["frameworks"]

    def test_generic_import_without_callers_is_low(self):
        result = analyze_pinning_facts(
            imports=[{"address": 0x4000, "symbol": "SecTrustEvaluate", "callers": []}],
            defined_names=[],
            strings=[],
        )
        assert result["confidence"] == "low"
        assert result["detected"] is False

    def test_curl_import_alone_is_not_evidence(self):
        result = analyze_pinning_facts(
            imports=[{"address": 0x4000, "symbol": "curl_easy_setopt", "callers": []}],
            defined_names=[],
            strings=[{"address": 0x3000, "value": "application/json"}],
        )
        assert "curl" not in result["frameworks"]
        assert result["detected"] is False

    def test_curl_with_tls_strings_counts(self):
        result = analyze_pinning_facts(
            imports=[{"address": 0x4000, "symbol": "curl_easy_setopt", "callers": []}],
            defined_names=[],
            strings=[{"address": 0x3000, "value": "libcurl SSL certificate verify failed"}],
        )
        assert "curl" in result["frameworks"]

    def test_network_security_config_string(self):
        result = analyze_pinning_facts(
            [], [], [{"address": 0x3000, "value": "res/xml/network_security_config.xml"}]
        )
        assert "network_security_config" in result["frameworks"]

    def test_hex_pin_string_is_medium(self):
        result = analyze_pinning_facts([], [], [{"address": 0x3000, "value": "ab" * 32}])
        assert result["confidence"] == "medium"
        assert result["detected"] is True

    def test_results_contract_keys(self):
        """The IDA/Binja tool wrappers consume these keys."""
        result = analyze_pinning_facts([], [], [])
        for key in (
            "detected",
            "confidence",
            "frameworks",
            "findings",
            "hook_targets",
            "strings",
            "functions",
        ):
            assert key in result, f"missing key: {key}"
        assert isinstance(result["frameworks"], list)


class TestBypassTechniques(unittest.TestCase):
    def test_openssl_hooks(self):
        techniques = get_bypass_techniques(["openssl"])
        assert any("SSL_CTX_set_verify" in t["technique"] for t in techniques["hook"])

    def test_sectrust_frida(self):
        techniques = get_bypass_techniques(["sectrust"])
        assert techniques["frida"]

    def test_frameworks_map_to_pattern_catalog(self):
        """Every framework name the analyzer can emit must have a bypass entry."""
        analyzable = {
            "okhttp",
            "network_security_config",
            "trust_manager",
            "sectrust",
            "curl",
            "openssl",
            "winhttp",
            "schannel",
        }
        missing = analyzable - set(SSL_PINNING_PATTERNS)
        assert not missing, f"frameworks without bypass info: {missing}"


class TestReportFormatting(unittest.TestCase):
    def test_report_contains_verdict_and_confidence(self):
        result = analyze_pinning_facts(
            imports=[
                {
                    "address": 0x4000,
                    "symbol": "SSL_CTX_set_verify",
                    "callers": [{"address": 0x5000, "name": "setup_tls"}],
                }
            ],
            defined_names=[],
            strings=[],
        )
        report = format_ssl_pinning_report(result)
        assert "SSL Pinning Detection Report" in report
        assert "Verdict" in report
        assert "high" in report
        assert "SSL_CTX_set_verify" in report
        assert "setup_tls" in report
        assert "Hook" in report
        assert "Bypass" in report

    def test_report_for_clean_binary(self):
        report = format_ssl_pinning_report(analyze_pinning_facts([], [], []))
        assert "No pinning evidence" in report


class _FakeIdaStr:
    """idautils.Strings() element shape: .ea plus str() conversion."""

    def __init__(self, ea: int, value: str):
        self.ea = ea
        self._value = value

    def __str__(self) -> str:
        return self._value


class TestIdaCollector(unittest.TestCase):
    """Exercises _collect_facts_ida against the shared IDA mocks.

    setUpModule installed the IDA mocks BEFORE spectra.tools.ssl_pinning was
    imported, so the module under test sees IDA_AVAILABLE = True.
    """

    def setUp(self):
        # Configure the mock objects the module itself holds, not whatever
        # sys.modules contains now (see setUpModule).
        self._idautils = ssl_pinning.idautils
        self._idaapi = ssl_pinning.idaapi
        self._idc = ssl_pinning.idc
        # Save the attributes we are about to reconfigure.
        self._saved = (
            self._idautils.Names.return_value,
            self._idautils.Strings.return_value,
            self._idautils.XrefsTo.side_effect,
            self._idautils.XrefsTo.return_value,
            self._idaapi.get_func.return_value,
            self._idc.get_func_name.return_value,
        )

    def tearDown(self):
        (
            self._idautils.Names.return_value,
            self._idautils.Strings.return_value,
            self._idautils.XrefsTo.side_effect,
            self._idautils.XrefsTo.return_value,
            self._idaapi.get_func.return_value,
            self._idc.get_func_name.return_value,
        ) = self._saved

    def test_module_sees_ida_under_mocks(self):
        # setUpModule reloaded the module with mocks live in sys.modules.
        self.assertTrue(ssl_pinning.IDA_AVAILABLE)

    def test_collects_imports_names_strings(self):
        self._idautils.Names.return_value = [
            (0x4000, "SSL_CTX_set_custom_verify"),
            (0x2000, "Java_com_example_net_Utils_checkServerTrusted"),
            (0x1000, "main"),
        ]
        self._idautils.XrefsTo.return_value = [types.SimpleNamespace(frm=0x5000)]
        self._idautils.Strings.return_value = [_FakeIdaStr(0x9000, _OKHTTP_PIN)]
        self._idaapi.get_func.return_value = types.SimpleNamespace(start_ea=0x5000)
        self._idc.get_func_name.return_value = "init_network"

        facts = _collect_facts_ida()

        # Import recognized with its caller resolved to the containing function
        imports = [e for e in facts["imports"] if e["symbol"] == "SSL_CTX_set_custom_verify"]
        assert imports and imports[0]["callers"] == [{"address": 0x5000, "name": "init_network"}]

        # JNI trust manager lands in defined names, pin string in strings
        assert any(
            e["name"] == "Java_com_example_net_Utils_checkServerTrusted" for e in facts["defined_names"]
        )
        assert facts["strings"] and facts["strings"][0]["value"] == _OKHTTP_PIN

        result = _detect_ssl_pinning_ida()
        assert result["detected"] is True
        assert result["confidence"] == "high"
        assert "openssl" in result["frameworks"]
        assert "trust_manager" in result["frameworks"]
        assert "okhttp" in result["frameworks"]

    def test_collector_survives_xref_errors(self):
        self._idautils.Names.return_value = [(0x4000, "SSL_get_verify_result")]
        self._idautils.XrefsTo.side_effect = RuntimeError("no xrefs in flat dumps")
        self._idautils.Strings.return_value = []

        facts = _collect_facts_ida()
        entry = facts["imports"][0]
        assert entry["symbol"] == "SSL_get_verify_result"
        assert entry["callers"] == []


# --- Binary Ninja collector -------------------------------------------------


class _FakeBnFunction:
    def __init__(self, name, start):
        self.name = name
        self.start = start


class _FakeBnSymbol:
    def __init__(self, name, addr):
        self.raw_name = name
        self.short_name = name
        self.address = addr


class _FakeBnRef:
    def __init__(self, function):
        self.function = function


class _FakeBnString:
    def __init__(self, value, start):
        self.value = value
        self.start = start


class _FakeBv:
    def __init__(self, symbols, refs=None, functions=None, strings=None):
        self.symbols = symbols
        self._refs = refs or {}
        self.functions = functions or []
        self._strings = strings or []

    def get_code_refs(self, addr):
        return self._refs.get(addr, [])

    def get_strings(self):
        return self._strings


class TestBinjaCollector(unittest.TestCase):
    def test_imports_and_callers(self):
        caller_fn = _FakeBnFunction("setup_tls", 0x5000)
        bv = _FakeBv(
            # list-valued entry (newer API) and single-symbol entry (older)
            symbols={
                "SSL_CTX_set_verify": [_FakeBnSymbol("SSL_CTX_set_verify", 0x4000)],
                "SecTrustEvaluateWithError": _FakeBnSymbol("SecTrustEvaluateWithError", 0x4100),
            },
            refs={0x4000: [_FakeBnRef(caller_fn)]},
            functions=[caller_fn, _FakeBnFunction("main", 0x6000)],
            strings=[_FakeBnString(_OKHTTP_PIN, 0x9000)],
        )
        facts = _collect_facts_binja(bv)

        symbols = {e["symbol"]: e for e in facts["imports"]}
        assert set(symbols) == {"SSL_CTX_set_verify", "SecTrustEvaluateWithError"}
        assert symbols["SSL_CTX_set_verify"]["callers"] == [{"address": 0x5000, "name": "setup_tls"}]
        assert symbols["SecTrustEvaluateWithError"]["callers"] == []
        assert any(e["name"] == "main" for e in facts["defined_names"])
        assert facts["strings"][0]["value"] == _OKHTTP_PIN

        result = analyze_pinning_facts(facts["imports"], facts["defined_names"], facts["strings"])
        assert result["confidence"] == "high"
        assert "openssl" in result["frameworks"] and "okhttp" in result["frameworks"]

    def test_code_ref_errors_are_swallowed(self):
        class _ExplodingBv(_FakeBv):
            def get_code_refs(self, _addr):
                raise RuntimeError("unanalyzed view")

        bv = _ExplodingBv(
            symbols={"WinHttpSetOption": [_FakeBnSymbol("WinHttpSetOption", 0x4000)]},
        )
        facts = _collect_facts_binja(bv)
        assert facts["imports"][0]["callers"] == []

    def test_symbols_iteration_failure_yields_empty(self):
        class _NoSymbolsBv(_FakeBv):
            # Bypass _FakeBv.__init__ so the raising property is never assigned.
            def __init__(self):
                self._refs = {}
                self.functions = []
                self._strings = []

            @property
            def symbols(self):
                raise RuntimeError("no symbols")

        facts = _collect_facts_binja(_NoSymbolsBv())
        assert facts["imports"] == []


if __name__ == "__main__":
    unittest.main()
