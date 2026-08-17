"""Tests for IOC harvesting (spectra/tools/ioc_collector.py).

Pure regex/stdlib logic over synthetic text and synthetic binary blobs —
no network, no host API. The @tool entrypoint is exercised end-to-end
against a temp file containing planted ASCII and UTF-16LE indicators.
"""

from __future__ import annotations

import base64
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.core.errors import ToolError
from spectra.tools.ioc_collector import (
    collect_iocs,
    defang,
    extract_iocs,
    extract_strings,
    format_ioc_report,
)

_B64_BLOB = base64.b64encode(b"Hidden printable payload for testing").decode()

SAMPLE_TEXT = "\n".join(
    [
        "C2 lives at http://malware.evil.ru/pay?x=1 and https://login.phish.io",
        "Fallback IPs 185.220.101.4 and 8.8.8.8",
        r"Mutex Global\SysinfoMtx_01 protects the install",
        r"Pipe \\.\pipe\cmd_check used for commands",
        r"Run key HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
        r"Also HKEY_CURRENT_USER\Software\Vendor\Startup",
        "Contact admin@evil-crew.ru for the build",
        f"Config blob {_B64_BLOB} decoded at runtime",
        "Also resolves evil-c2.online and updates from cdn.payload.xyz.",
        "Benign noise: see example.com and https://schemas.microsoft.com/xml for docs",
    ]
)


def _extract(text: str, key: str) -> list:
    return extract_iocs(text)[key]


class TestExtractStrings(unittest.TestCase):
    def test_ascii_and_utf16le_runs(self):
        data = (
            b"\x00\x00"
            + b"plain ascii string\x00"
            + b"\xff\xfe\x00\x00"
            + "wide string here".encode("utf-16-le")
            + b"\x00\x00"
        )
        strings = extract_strings(data)
        assert "plain ascii string" in strings
        assert "wide string here" in strings
        # Ordered by file offset: the ASCII run starts before the UTF-16LE run.
        assert strings.index("plain ascii string") < strings.index("wide string here")

    def test_short_runs_dropped(self):
        data = b"abcd\x00" + "ab".encode("utf-16-le") + b"\x00" + b"0123456789"
        strings = extract_strings(data)
        assert "abcd" not in strings
        assert "0123456789" in strings

    def test_empty_input(self):
        assert extract_strings(b"") == []


class TestExtractIocs(unittest.TestCase):
    def test_full_sample_all_categories(self):
        iocs = extract_iocs(SAMPLE_TEXT)
        assert "http://malware.evil.ru/pay?x=1" in iocs["urls"]
        assert "https://login.phish.io" in iocs["urls"]
        assert "185.220.101.4" in iocs["ipv4"]
        assert "8.8.8.8" in iocs["ipv4"]
        assert r"Global\SysinfoMtx_01" in iocs["mutexes"]
        assert r"\\.\pipe\cmd_check" in iocs["pipes"]
        assert r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" in iocs["registry_keys"]
        assert r"HKEY_CURRENT_USER\Software\Vendor\Startup" in iocs["registry_keys"]
        assert "admin@evil-crew.ru" in iocs["emails"]
        assert "evil-c2.online" in iocs["domains"]
        assert "cdn.payload.xyz" in iocs["domains"]
        assert iocs["base64_blobs"] == [
            {"value": _B64_BLOB, "decoded": "Hidden printable payload for testing"}
        ]

    def test_result_contract_keys(self):
        iocs = extract_iocs("")
        for key in ("urls", "domains", "ipv4", "mutexes", "registry_keys", "pipes", "emails"):
            assert key in iocs and iocs[key] == []

    def test_ipv4_octet_validation(self):
        assert _extract("node at 999.9.9.9 ok", "ipv4") == []
        assert _extract("node at 10.0.0.1 ok", "ipv4") == ["10.0.0.1"]

    def test_ipv4_version_number_exclusions(self):
        text = "build v1.2.3.4 from version 2.0.0.1 of 1.2.3.4.5 but 8.8.8.8 stays"
        ipv4 = _extract(text, "ipv4")
        assert ipv4 == ["8.8.8.8"]

    def test_domain_requires_common_tld(self):
        assert _extract("hosts evil.ru and 1.2.3.4.evil.invalid", "domains") == ["evil.ru"]

    def test_benign_allowlist_excluded(self):
        assert _extract("see example.com docs", "domains") == []
        assert _extract("docs at https://schemas.microsoft.com/xml and www.w3.org/x", "urls") == []
        assert _extract("also sub.example.com here", "domains") == []

    def test_url_and_email_hosts_not_relisted_as_domains(self):
        iocs = extract_iocs("Go to http://c2.evil.ru/x or mail ops@evil.ru")
        assert "c2.evil.ru" not in iocs["domains"]
        assert "evil.ru" not in iocs["domains"]
        assert len(iocs["urls"]) == 1 and len(iocs["emails"]) == 1

    def test_mutex_case_insensitive(self):
        assert _extract(r"lock global\mtx_1", "mutexes") == [r"global\mtx_1"]

    def test_base64_blob_requires_printable_decode(self):
        # 'A'*30 decodes to NUL bytes — rejected by the printable-ratio check.
        assert _extract("junk " + "A" * 30 + " end", "base64_blobs") == []
        kept = _extract("keep " + base64.b64encode(b"c2 config payload").decode(), "base64_blobs")
        assert kept and kept[0]["decoded"] == "c2 config payload"

    def test_duplicates_removed_preserving_order(self):
        text = "a http://x.evil.io/1 b http://y.evil.io/2 c http://x.evil.io/1"
        assert _extract(text, "urls") == ["http://x.evil.io/1", "http://y.evil.io/2"]

    def test_trailing_url_punctuation_stripped(self):
        assert _extract("visit http://a.evil.su now.", "urls") == ["http://a.evil.su"]


class TestDefang(unittest.TestCase):
    def test_http_scheme(self):
        assert defang("http://evil.com/a") == "hxxp://evil[.]com/a"

    def test_https_scheme(self):
        assert defang("https://x.io") == "hxxps://x[.]io"

    def test_scheme_case_insensitive(self):
        assert defang("HTTP://Evil.COM").startswith("hxxp://Evil[.]COM")

    def test_email_at_and_dots(self):
        assert defang("a@b.ru") == "a[at]b[.]ru"

    def test_plain_value_untouched(self):
        assert defang(r"Global\Mutex_1") == r"Global\Mutex_1"


class TestFormatIocReport(unittest.TestCase):
    def test_report_is_defanged_markdown(self):
        report = format_ioc_report(extract_iocs(SAMPLE_TEXT), source="/samples/mal.bin")
        assert "## IOC Report" in report
        assert "/samples/mal.bin" in report
        assert "hxxp://malware[.]evil[.]ru/pay?x=1" in report
        assert "185[.]220[.]101[.]4" in report
        assert "admin[at]evil-crew[.]ru" in report
        assert "evil-c2[.]online" in report
        assert "http://" not in report  # nothing un-defanged leaks into the report

    def test_empty_report(self):
        report = format_ioc_report(extract_iocs("nothing here"))
        assert "## IOC Report" in report
        assert "No IOCs found." in report


class TestToolEndToEnd(unittest.TestCase):
    BLOB = (
        b"MZ\x90\x00\x03\x00\x00\x00\x00\x00\x00"
        + b"http://c2.evil.xyz/gate.php\x00"
        + b"185.220.101.4\x00"
        + "Global\\UpdateMtx".encode("utf-16-le")
        + b"\x00\x00"
        + rb"HKLM\SOFTWARE\Evil\Run"
        + b"\x00\x00"
        + rb"\\.\pipe\cmd_check"
        + b"\x00\x00"
        + base64.b64encode(b"Exfil payload encoded for tests")
        + b"\x00\x00"
    )

    def test_collect_iocs_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "sample.exe")
            with open(target, "wb") as fh:
                fh.write(self.BLOB)
            report = collect_iocs(path=target)
        assert "## IOC Report" in report
        assert target in report
        # UTF-16LE mutex recovered from the wide-string run
        assert "Global\\UpdateMtx" in report
        assert "hxxp://c2[.]evil[.]xyz/gate[.]php" in report
        assert "185[.]220[.]101[.]4" in report
        assert r"HKLM\SOFTWARE\Evil\Run" in report
        # Pipe name contains dots → defanged in the report like every value.
        assert r"\\[.]\pipe\cmd_check" in report
        assert "Exfil payload encoded for tests" in report  # decoded preview
        assert "http://" not in report

    def test_collect_iocs_from_text_wins_over_file(self):
        report = collect_iocs(text="visit http://inline.evil.cc/x")
        assert "inline text" in report
        assert "hxxp://inline[.]evil[.]cc/x" in report

    def test_missing_file_raises_tool_error(self):
        with self.assertRaises(ToolError):
            collect_iocs(path="/nonexistent/iocs/sample.bin")


if __name__ == "__main__":
    unittest.main()
