"""IOC harvesting tool.

Extracts strings from a binary (ASCII and UTF-16LE runs), mines them for
indicators of compromise — URLs, domains, IPv4 addresses, mutexes, registry
keys, named pipes, e-mail addresses and decodable base64 blobs — and renders
a **defanged** markdown report (``hxxp://``, ``[.]``, ``[at]``) safe to paste
into tickets or chat.

Engine layout mirrors ``ssl_pinning``: pure extraction functions over
bytes/text (:func:`extract_strings`, :func:`extract_iocs`), a defanging
helper (:func:`defang`), a markdown formatter (:func:`format_ioc_report`)
and a thin ``@tool`` entrypoint (:func:`collect_iocs`). Registration happens
elsewhere — this module only defines the tool.
"""

from __future__ import annotations

import base64
import binascii
import re
from typing import Annotated, Any

from ..core.errors import ToolError
from .base import tool

# Upper bound so a multi-hundred-MB dump can never balloon the string list.
MAX_STRINGS = 100_000

# Minimum printable run length for both ASCII and UTF-16LE strings (the {5,}
# quantifiers below must stay in sync with this value).
MIN_RUN = 5

# ---------------------------------------------------------------------------
# String extraction
# ---------------------------------------------------------------------------

# Printable ASCII run of MIN_RUN or more bytes.
_ASCII_RUN_RE = re.compile(rb"[\x20-\x7e]{5,}")

# UTF-16LE run: printable ASCII byte followed by a NUL byte, MIN_RUN times.
_UTF16LE_RUN_RE = re.compile(rb"(?:[\x20-\x7e]\x00){5,}")


def extract_strings(data: bytes) -> list[str]:
    """Extract ASCII (>=5 printable chars) and UTF-16LE strings from *data*.

    Returns strings ordered by their file offset (ASCII and UTF-16LE runs
    interleaved), which keeps the report stable across runs. UTF-16LE runs
    cannot alias ASCII runs: a strict ``<printable>\\x00`` pair sequence never
    contains five consecutive printable bytes.
    """
    hits: list[tuple[int, str]] = []
    for match in _ASCII_RUN_RE.finditer(data):
        hits.append((match.start(), match.group().decode("ascii", "replace")))
    for match in _UTF16LE_RUN_RE.finditer(data):
        hits.append((match.start(), match.group().decode("utf-16-le")))
    hits.sort(key=lambda item: item[0])
    return [value for _off, value in hits[:MAX_STRINGS]]


# ---------------------------------------------------------------------------
# IOC extraction rules
# ---------------------------------------------------------------------------

# URLs: scheme + everything up to whitespace or a quote/bracket.
_URL_RE = re.compile(r"https?://[^\s'\"<>\[\]{}]+")

# E-mail addresses.
_EMAIL_RE = re.compile(r"[0-9A-Za-z._%+-]+@[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)+")

# IPv4 candidates. Lookbehind rejects candidates glued to a word char or dot
# ("v1.2.3.4", "a1.2.3.4", ".1.2.3.4"); lookahead rejects candidates directly
# followed by more dotted numbers ("1.2.3.4.5" — a dotted version/build).
# Octet range is validated separately.
_IPV4_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?!\.\d)")

# A dotted quad preceded by "v", "ver", "version", "rev" or "build" is a
# version string, not an address ("version 1.2.3.4"). Keep-simple heuristic.
_VERSION_PREFIX_RE = re.compile(r"(?:^|\s)(?:v|ver|version|rev|build)\s*$", re.IGNORECASE)

# Domains: at least one dot, ending in a small common-TLD allowlist, and not
# preceded by an alphanumeric (so "abc" of "xabc.example.com" does not match).
_COMMON_TLDS = (
    "com|net|org|io|xyz|info|biz|ru|cn|de|uk|top|online|site|cc|su|in|me|co"
)
_DOMAIN_RE = re.compile(
    r"(?<![0-9A-Za-z-])((?:[0-9A-Za-z][0-9A-Za-z-]{0,61}\.)+(?:" + _COMMON_TLDS + r"))(?![0-9A-Za-z-])",
    re.IGNORECASE,
)

# Windows named mutexes and pipes (case-insensitive — Win32 object namespace).
_MUTEX_RE = re.compile(r"(?:Global|Local)\\[\w.\-]+", re.IGNORECASE)
_PIPE_RE = re.compile(r"\\\\\.\\pipe\\[\w.\-]+", re.IGNORECASE)

# Registry key roots and the path tail that may follow them.
_REGISTRY_RE = re.compile(
    r"(?:HKLM|HKCU|HKCR|HKU|HKEY_(?:LOCAL_MACHINE|CURRENT_USER|CLASSES_ROOT|USERS))"
    r"\\[\\\w.*+?/\-]+",
    re.IGNORECASE,
)

# Base64-looking blobs of >= 20 chars. Kept only when they actually decode to
# mostly-printable bytes (see _decode_base64_blob) — that check is what keeps
# hex strings, identifiers and URL noise out of the report.
_BASE64_RE = re.compile(r"(?<![0-9A-Za-z+/=])[A-Za-z0-9+/]{20,}={0,2}(?![0-9A-Za-z+/=])")

# Fraction of decoded bytes that must be printable (TAB/LF/CR / 0x20-0x7e).
_B64_PRINTABLE_RATIO = 0.9

# Preview length (chars) for decoded base64 blobs in the report.
_B64_PREVIEW_LEN = 60

# Benign allowlist: hosts that appear in practically every binary and say
# nothing about intent. Applied to URL hosts and bare domains (subdomains
# included); e-mails and IPs are never filtered.
_BENIGN_DOMAINS = (
    "example.com",
    "example.org",
    "example.net",
    "w3.org",
    "schemas.microsoft.com",
    "microsoft.com",
    "schemas.openxmlformats.org",
    "purl.org",
    "xml.apache.org",
)

_IOC_SECTIONS: tuple[tuple[str, str], ...] = (
    ("urls", "URLs"),
    ("domains", "Domains"),
    ("ipv4", "IPv4 Addresses"),
    ("mutexes", "Mutexes"),
    ("registry_keys", "Registry Keys"),
    ("pipes", "Named Pipes"),
    ("emails", "E-mail Addresses"),
    ("base64_blobs", "Base64 Blobs"),
)


def _dedupe(values: list[str]) -> list[str]:
    """Drop duplicates, preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _clean_url(url: str) -> str:
    """Strip trailing sentence punctuation captured by the URL regex."""
    return url.rstrip(".,;:!?'\"")


def _url_host(url: str) -> str:
    """Host portion of a URL (userinfo and port stripped, lowercased)."""
    rest = url.split("://", 1)[-1]
    host = re.match(r"[^/?#\\]+", rest)
    if not host:
        return ""
    candidate = host.group(0)
    if "@" in candidate:
        candidate = candidate.rsplit("@", 1)[1]
    return candidate.split(":", 1)[0].lower()


def _is_benign_host(host: str) -> bool:
    """True when *host* is (a subdomain of) a benign allowlist entry."""
    host = host.lower().strip(".")
    return any(host == base or host.endswith("." + base) for base in _BENIGN_DOMAINS)


def _is_valid_ipv4(candidate: str) -> bool:
    """Each octet must be within 0-255."""
    return all(0 <= int(octet) <= 255 for octet in candidate.split("."))


def _is_version_number(text: str, start: int) -> bool:
    """True when the dotted quad at *start* is preceded by a version word."""
    prefix = text[max(0, start - 12) : start]
    return bool(_VERSION_PREFIX_RE.search(prefix))


def _decode_base64_blob(candidate: str) -> str | None:
    """Decode a base64 candidate; return a printable preview or None.

    A blob is kept only when it base64-decodes cleanly *and* at least 90% of
    the decoded bytes are printable — random alphanumeric runs (hex ids,
    symbols, URL slugs) almost always decode to binary garbage and are
    rejected here.
    """
    padded = candidate + "=" * ((-len(candidate)) % 4)
    try:
        raw = base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError):
        return None
    if not raw:
        return None
    printable = sum(1 for b in raw if b in (0x09, 0x0A, 0x0D) or 0x20 <= b <= 0x7E)
    if printable / len(raw) < _B64_PRINTABLE_RATIO:
        return None
    return raw.decode("latin-1")[:_B64_PREVIEW_LEN]


def _mask_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """Blank out the given [start, end) spans so later scans skip them."""
    chars = list(text)
    for start, end in spans:
        for idx in range(start, min(end, len(chars))):
            chars[idx] = " "
    return "".join(chars)


def extract_iocs(text: str) -> dict[str, list[Any]]:
    """Extract IOCs from *text* (typically the joined string table).

    Returns a dict with the keys ``urls``, ``domains``, ``ipv4``, ``mutexes``,
    ``registry_keys``, ``pipes``, ``emails``, ``base64_blobs`` — each a list,
    deduplicated in first-seen order. ``base64_blobs`` entries are dicts of
    ``{"value": <blob>, "decoded": <preview>}``.

    Rule notes:

    - URL hosts and e-mail domains are *not* re-listed under ``domains``;
      their spans are masked before the domain scan to avoid duplicates.
    - URL hosts and bare domains on the benign allowlist are dropped.
    - IPv4s must pass octet validation and the version-number heuristics
      (see ``_IPV4_RE`` / ``_is_version_number``).
    """
    # URLs and e-mails first — their spans feed the masking pass.
    urls: list[str] = []
    url_spans: list[tuple[int, int]] = []
    for match in _URL_RE.finditer(text):
        url = _clean_url(match.group(0))
        if not url or _is_benign_host(_url_host(url)):
            continue
        if url not in urls:
            urls.append(url)
            url_spans.append(match.span())

    emails: list[str] = []
    email_spans: list[tuple[int, int]] = []
    for match in _EMAIL_RE.finditer(text):
        email = match.group(0)
        if email not in emails:
            emails.append(email)
            email_spans.append(match.span())

    masked = _mask_spans(text, url_spans + email_spans)

    ipv4: list[str] = []
    for match in _IPV4_RE.finditer(text):
        candidate = match.group(1)
        if _is_valid_ipv4(candidate) and not _is_version_number(text, match.start(1)):
            ipv4.append(candidate)

    domains: list[str] = []
    for match in _DOMAIN_RE.finditer(masked):
        domain = match.group(1).lower()
        if not _is_benign_host(domain):
            domains.append(domain)

    base64_blobs: list[dict[str, str]] = []
    seen_blobs: set[str] = set()
    for match in _BASE64_RE.finditer(text):
        blob = match.group(0)
        if blob in seen_blobs:
            continue
        decoded = _decode_base64_blob(blob)
        if decoded is not None:
            seen_blobs.add(blob)
            base64_blobs.append({"value": blob, "decoded": decoded})

    return {
        "urls": urls,
        "domains": _dedupe(domains),
        "ipv4": _dedupe(ipv4),
        "mutexes": _dedupe(m.group(0) for m in _MUTEX_RE.finditer(text)),
        "registry_keys": _dedupe(m.group(0) for m in _REGISTRY_RE.finditer(text)),
        "pipes": _dedupe(m.group(0) for m in _PIPE_RE.finditer(text)),
        "emails": emails,
        "base64_blobs": base64_blobs,
    }


# ---------------------------------------------------------------------------
# Defanging
# ---------------------------------------------------------------------------

_SCHEME_RE = re.compile(r"https?://", re.IGNORECASE)


def defang(text: str) -> str:
    """Defang an indicator: http→hxxp / https→hxxps, '@'→'[at]', '.'→'[.]'.

    Schemes are rewritten first, then '@' and every remaining '.' are
    bracketed — for a URL that also defangs dots in the path, which is the
    standard convention (e.g. unfurl-style reports). Values that contain no
    schemes, dots or '@' pass through unchanged.
    """

    def _scheme(match: re.Match[str]) -> str:
        return "hxxps://" if match.group(0).lower().startswith("https") else "hxxp://"

    out = _SCHEME_RE.sub(_scheme, text)
    out = out.replace("@", "[at]")
    return out.replace(".", "[.]")


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------


def format_ioc_report(iocs: dict[str, Any], source: str = "") -> str:
    """Render extracted IOCs as a defanged markdown report."""
    lines = ["## IOC Report\n"]
    if source:
        lines.append(f"**Source:** `{source}`")

    total = sum(len(iocs.get(key) or []) for key, _title in _IOC_SECTIONS)
    lines.append(f"**Total indicators:** {total}\n")

    if total == 0:
        lines.append("No IOCs found.")
        return "\n".join(lines)

    for key, title in _IOC_SECTIONS:
        values = iocs.get(key) or []
        if not values:
            continue
        lines.append(f"### {title} ({len(values)})\n")
        if key == "base64_blobs":
            for blob in values:
                lines.append(f"- `{defang(blob['value'])}` → decodes to: `{defang(blob['decoded'])}`")
        else:
            for value in values:
                lines.append(f"- `{defang(value)}`")
        lines.append("")

    lines.append("*All values defanged: `hxxp`/`hxxps` schemes, `[.]` dots, `[at]` for '@'.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool entrypoint
# ---------------------------------------------------------------------------


def _current_input_file() -> str:
    """Best-effort path of the binary loaded in the host (IDA / BN / none)."""
    try:
        from ..core.host import get_database_path, is_ida

        if is_ida():
            import idaapi

            p = idaapi.get_input_file_path()
            if p:
                return str(p)
        return get_database_path()
    except Exception:
        return ""


@tool(
    category="analysis",
    description=(
        "Harvest IOCs (URLs, IPs, domains, mutexes, registry keys, pipes, base64 blobs) "
        "from the binary and return a defanged report"
    ),
)
def collect_iocs(
    path: Annotated[str, "Binary path (empty = current input file)"] = "",
    text: Annotated[str, "Analyze this text instead of a file (optional)"] = "",
) -> str:
    """Harvest IOCs from a binary (or raw text) and return a defanged report.

    When ``text`` is given it wins over ``path``; otherwise the binary at
    ``path`` (or the host's current input file) is read and its ASCII +
    UTF-16LE strings are mined for indicators.
    """
    if text:
        return format_ioc_report(extract_iocs(text), source="inline text")

    resolved = (path or "").strip() or _current_input_file()
    if not resolved:
        raise ToolError("No binary path given, no text provided and no input file is open in the host")

    try:
        with open(resolved, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise ToolError(f"Cannot read binary '{resolved}': {exc}") from exc

    strings = extract_strings(data)
    iocs = extract_iocs("\n".join(strings))
    return format_ioc_report(iocs, source=resolved)
