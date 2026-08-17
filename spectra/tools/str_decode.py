"""String deobfuscation tools: classic decoders and stack-string recovery.

Two independent halves, mirroring the ssl_pinning tool layout:

1. Pure classic decoders (``decode_value``) — hex, base32, base64/base64url,
   rot13/rot47, reverse, comma/space byte lists, and single-byte XOR brute
   force. Fully host-independent and unit-testable.
2. Stack-string recovery (``find_stack_strings_in_lines``) — a pure engine
   over ``(address, disasm_text)`` lines that reconstructs strings built
   from consecutive immediate stores/pushes. Host collectors (IDA Pro and
   Binary Ninja) feed it disassembly; every host API call is individually
   guarded so API drift degrades to skipping, never crashing.
"""

from __future__ import annotations

import base64
import itertools
import re
from typing import Annotated, Any

from ..core.host import get_binary_ninja_view
from .base import tool

# Try to import IDA API
try:
    import idautils
    import idc

    IDA_AVAILABLE = True
except ImportError:
    IDA_AVAILABLE = False

# Optional: IDA color-tag stripper (absent in some headless configurations)
try:
    import ida_lines

    _IDA_LINES_AVAILABLE = True
except ImportError:
    _IDA_LINES_AVAILABLE = False

# Try to import Binary Ninja API
try:
    import binaryninja  # noqa: F401 — availability probe

    BINJA_AVAILABLE = True
except ImportError:
    BINJA_AVAILABLE = False


# ---------------------------------------------------------------------------
# Part 1 — pure classic decoders
# ---------------------------------------------------------------------------

_MAX_INPUT_CHARS = 100_000  # refuse absurd inputs rather than churn on them
_MAX_XOR_BYTES = 65_536  # brute force cost is O(256 * n); cap the payload
_XOR_SCORE_THRESHOLD = 0.9
_XOR_TOP_N = 3

_HEX_CHARS_RE = re.compile(r"[0-9a-fA-F]+")
_B64_STD_RE = re.compile(r"[A-Za-z0-9+/]+={0,2}")
_B64_URL_RE = re.compile(r"[A-Za-z0-9_-]+={0,2}")
_DECIMAL_SPLIT_RE = re.compile(r"[,\s]+")

SCHEMES: tuple[str, ...] = (
    "hex",
    "decimal",
    "base32",
    "base64",
    "base64url",
    "rot13",
    "rot47",
    "reverse",
    "xor_brute",
)

_SCHEME_ALIASES = {
    "xor": "xor_brute",
    "b32": "base32",
    "b64": "base64",
    "b64url": "base64url",
    "byte_list": "decimal",
}

# Printable ASCII (0x20-0x7E) membership used for scoring everywhere.
def _is_printable_byte(b: int) -> bool:
    return 0x20 <= b <= 0x7E


def _printable_score_bytes(data: bytes) -> float:
    """Fraction of bytes that are printable ASCII (0.0 for empty input)."""
    if not data:
        return 0.0
    return sum(1 for b in data if _is_printable_byte(b)) / len(data)


def _printable_score_text(text: str) -> float:
    """Fraction of characters that are printable ASCII (0.0 for empty input)."""
    if not text:
        return 0.0
    return sum(1 for ch in text if _is_printable_byte(ord(ch) & 0xFF)) / len(text)


def _bytes_to_text(data: bytes) -> str:
    """Best-effort text rendering of decoded bytes for display."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _try_hex(s: str) -> bytes | None:
    """Decode a hex string (optional 0x prefix, optional internal spaces)."""
    t = s.strip()
    if t[:2].lower() == "0x":
        t = t[2:]
    t = t.replace(" ", "")
    if not t or len(t) % 2 != 0 or not _HEX_CHARS_RE.fullmatch(t):
        return None
    try:
        return bytes.fromhex(t)
    except ValueError:
        return None


def _try_base32(s: str) -> bytes | None:
    """Decode RFC 4648 base32 (case-insensitive, padding required by stdlib)."""
    t = s.strip()
    if not t:
        return None
    try:
        data = base64.b32decode(t, casefold=True)
    except Exception:
        return None
    return data or None


def _try_base64(s: str) -> bytes | None:
    """Decode standard-alphabet base64; malformed input returns None."""
    t = s.strip()
    if not t or not _B64_STD_RE.fullmatch(t):
        return None
    try:
        data = base64.b64decode(t, validate=True)
    except Exception:
        return None
    return data or None


def _try_base64url(s: str) -> bytes | None:
    """Decode URL-safe base64, tolerating stripped padding."""
    t = s.strip()
    if not t or not _B64_URL_RE.fullmatch(t):
        return None
    t += "=" * (-len(t) % 4)
    try:
        data = base64.urlsafe_b64decode(t)
    except Exception:
        return None
    return data or None


def _try_decimal(s: str) -> bytes | None:
    """Decode a comma/space separated decimal byte list (e.g. '72, 101, 108')."""
    t = s.strip()
    if not t:
        return None
    tokens = [tok for tok in _DECIMAL_SPLIT_RE.split(t) if tok]
    if len(tokens) < 2:  # single integers are ambiguous noise, not a byte list
        return None
    out = bytearray()
    for tok in tokens:
        if not tok.isdigit():
            return None
        value = int(tok)
        if value > 0xFF:
            return None
        out.append(value)
    return bytes(out)


def _rot13(text: str) -> str:
    """Rotate ASCII letters by 13; other characters pass through."""
    out = []
    for ch in text:
        if "a" <= ch <= "z":
            out.append(chr((ord(ch) - ord("a") + 13) % 26 + ord("a")))
        elif "A" <= ch <= "Z":
            out.append(chr((ord(ch) - ord("A") + 13) % 26 + ord("A")))
        else:
            out.append(ch)
    return "".join(out)


def _rot47(text: str) -> str:
    """Rotate printable ASCII (0x21-0x7E) by 47; other characters pass through."""
    out = []
    for ch in text:
        o = ord(ch)
        if 0x21 <= o <= 0x7E:
            out.append(chr(0x21 + (o - 0x21 + 47) % 94))
        else:
            out.append(ch)
    return "".join(out)


def _reverse(text: str) -> str:
    """Reverse the string."""
    return text[::-1]


def _xor_source_bytes(value: str) -> bytes:
    """Choose the byte payload XOR brute force operates on.

    Documented choice: if the input is valid even-length hex, brute force the
    *decoded* bytes (the common "hex-encoded XOR blob" case); otherwise brute
    force the literal string bytes.
    """
    hexed = _try_hex(value)
    if hexed is not None:
        return hexed
    return value.encode("utf-8")


# Cheap English-likeness heuristics used to break score ties in xor_brute:
# clustered ciphertext bytes make many keys fully printable, so real words
# must outrank junk like "aLEFF" / "@mddg".
_COMMON_BIGRAMS = frozenset(
    (
        "th", "he", "in", "er", "an", "re", "on", "at", "en", "nd", "ti", "es", "or", "te",
        "of", "ed", "is", "it", "al", "ar", "st", "to", "nt", "ng", "se", "ha", "as", "ou", "io",
    )
)
_OK_BIGRAMS = frozenset(
    (
        "le", "ve", "co", "me", "de", "hi", "ri", "ro", "ic", "ne", "ea", "ra", "ce", "li", "ch",
        "ll", "be", "ma", "si", "om", "ur", "ca", "el", "ta", "la", "ns", "di", "fo", "ho", "pe",
        "ec", "pr", "no", "ct", "us", "ac", "ot", "il", "tr", "ly", "nc", "et", "ut", "ss", "so",
        "rs", "un", "lo", "wa", "ge", "ie", "wh", "ee", "ld", "rl", "wo", "ol",
    )
)


def _text_quality(text: str) -> float:
    """Rank how word-like a candidate is: bigram hits minus case ping-pong."""
    if len(text) < 2:
        return 0.0
    lowered = text.lower()
    hits = 0.0
    for i in range(len(lowered) - 1):
        bigram = lowered[i : i + 2]
        if bigram in _COMMON_BIGRAMS:
            hits += 2.0
        elif bigram in _OK_BIGRAMS:
            hits += 1.0
    quality = hits / (len(lowered) - 1)
    flips = sum(1 for a, b in itertools.pairwise(text) if a.isalpha() and b.isalpha() and a.isupper() != b.isupper())
    quality -= 0.5 * flips / (len(text) - 1)
    return quality


def _xor_brute(data: bytes) -> list[dict[str, Any]]:
    """Brute force all 255 non-trivial single-byte XOR keys.

    Key 0 (identity) is skipped — it adds no information. A decoded value
    survives only when its printable-ASCII fraction is >=
    ``_XOR_SCORE_THRESHOLD``. Because clustered ciphertext bytes make many
    keys fully printable, ties on printable score are broken by
    ``_text_quality`` (English bigram hits); at most ``_XOR_TOP_N``
    *distinct* decoded values are kept.
    """
    if not data or len(data) > _MAX_XOR_BYTES:
        return []
    distinct: dict[bytes, tuple[float, int, float]] = {}
    for key in range(1, 256):
        decoded = bytes(b ^ key for b in data)
        score = _printable_score_bytes(decoded)
        if score < _XOR_SCORE_THRESHOLD:
            continue
        text = _bytes_to_text(decoded)
        prev = distinct.get(decoded)
        quality = _text_quality(text)
        if prev is None or score > prev[0]:
            distinct[decoded] = (score, key, quality)
    ranked = sorted(distinct.items(), key=lambda kv: (-kv[1][0], -kv[1][2], kv[0]))
    candidates = []
    for decoded, (score, key, _quality) in ranked[:_XOR_TOP_N]:
        candidates.append(
            {
                "scheme": "xor_brute",
                "result": _bytes_to_text(decoded),
                "score": round(score, 4),
                "printable": score >= 1.0,
                "key": key,
            }
        )
    return candidates


def _squash(candidate: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Wrap a single optional candidate in a list."""
    return [candidate] if candidate else []


def _bytes_candidate(scheme: str, data: bytes | None) -> dict[str, Any] | None:
    """Build a candidate dict from decoded bytes; None for empty/failed."""
    if not data:
        return None
    score = _printable_score_bytes(data)
    return {
        "scheme": scheme,
        "result": _bytes_to_text(data),
        "score": round(score, 4),
        "printable": score >= 1.0,
    }


def _text_candidate(scheme: str, text: str) -> dict[str, Any] | None:
    """Build a candidate dict from a transformed string; None for empty."""
    if not text:
        return None
    score = _printable_score_text(text)
    return {
        "scheme": scheme,
        "result": text,
        "score": round(score, 4),
        "printable": score >= 1.0,
    }


def _decode_with_scheme(value: str, scheme: str) -> list[dict[str, Any]]:
    """Decode ``value`` with one specific scheme; malformed input -> empty list."""
    if scheme == "hex":
        return _squash(_bytes_candidate("hex", _try_hex(value)))
    if scheme == "decimal":
        return _squash(_bytes_candidate("decimal", _try_decimal(value)))
    if scheme == "base32":
        return _squash(_bytes_candidate("base32", _try_base32(value)))
    if scheme == "base64":
        return _squash(_bytes_candidate("base64", _try_base64(value)))
    if scheme == "base64url":
        return _squash(_bytes_candidate("base64url", _try_base64url(value)))
    if scheme == "rot13":
        return _squash(_text_candidate("rot13", _rot13(value)))
    if scheme == "rot47":
        return _squash(_text_candidate("rot47", _rot47(value)))
    if scheme == "reverse":
        return _squash(_text_candidate("reverse", _reverse(value)))
    if scheme == "xor_brute":
        return _xor_brute(_xor_source_bytes(value))
    return []  # unknown scheme: skip, never raise


def decode_value(value: str, scheme: str = "auto") -> dict[str, Any]:
    """Try decoders and return ranked candidates.

    Returns ``{"candidates": [{scheme, result, score, printable}, ...],
    "value": value}``. xor_brute candidates additionally carry the winning
    ``key``.

    Schemes: hex, base32, base64, base64url, rot13, rot47, reverse,
    xor_brute, decimal (comma/space separated byte list).

    ``"auto"`` tries every scheme that applies and ranks candidates by
    (printable score desc, decoded length asc — decoding schemes shrink
    real payloads, while rot/reverse merely reshuffle the input). Malformed
    input for a scheme skips that scheme; nothing ever raises.
    """
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")  # LLM tool args sometimes arrive as bytes
    elif not isinstance(value, str):
        value = str(value)
    result: dict[str, Any] = {"value": value, "candidates": []}
    if not value.strip() or len(value) > _MAX_INPUT_CHARS:
        return result

    normalized = (scheme or "auto").strip().lower()
    normalized = _SCHEME_ALIASES.get(normalized, normalized)

    if normalized in ("", "auto"):
        candidates: list[dict[str, Any]] = []
        for name in SCHEMES:
            candidates.extend(_decode_with_scheme(value, name))
    elif normalized in SCHEMES:
        candidates = _decode_with_scheme(value, normalized)
    else:
        return result  # unknown scheme requested -> no candidates, no error

    candidates.sort(key=lambda c: (-c["score"], len(c["result"])))
    result["candidates"] = candidates
    return result


def format_decode_report(result: dict[str, Any]) -> str:
    """Format decode_value() output as markdown (pure, testable)."""
    lines = ["## String Decode Report\n"]
    value = str(result.get("value", ""))
    lines.append(f"**Input:** `{value[:200]}`\n")

    candidates = result.get("candidates") or []
    if not candidates:
        lines.append(
            "No decodable candidates found. The input may be malformed for every "
            "scheme — try passing an explicit `scheme`, or check for typos."
        )
        return "\n".join(lines)

    lines.append(f"**{len(candidates)} candidate(s)**, ranked by printable score:\n")
    for i, cand in enumerate(candidates[:10], 1):
        key_txt = f", key 0x{cand['key']:02x}" if "key" in cand else ""
        printable_txt = "printable" if cand.get("printable") else "partial"
        shown = str(cand.get("result", "")).replace("`", "'")
        lines.append(f"{i}. **{cand.get('scheme', '?')}** ({printable_txt}, score {cand.get('score', 0)}{key_txt}): `{shown}`")
    if len(candidates) > 10:
        lines.append(f"\n...and {len(candidates) - 10} more candidate(s).")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Part 2 — stack-string recovery (pure engine over disassembly lines)
# ---------------------------------------------------------------------------

_MIN_STACK_STRING_LEN = 4  # minimum total reconstructed length
_MAX_IMM_BYTES = 8  # immediates wider than 64-bit are not char material
_MAX_RUN_GAP = 1  # tolerated non-immediate instructions inside a run
_MAX_IDA_FUNC_INSNS = 20_000  # skip enormous functions
_MAX_BINJA_FUNCTIONS = 5_000
_MAX_REPORT_FUNCTIONS = 50
_MAX_REPORT_STRINGS_PER_FUNC = 10

_IMM_MNEMONICS = frozenset({"mov", "movabs", "push"})
_QUOTED_IMM_RE = re.compile(r"^'([^']{1,8})'$")
_HEX_0X_IMM_RE = re.compile(r"^0[xX][0-9a-fA-F]+$")
_HEX_H_IMM_RE = re.compile(r"^[0-9][0-9a-fA-F]*[hH]$")
_IDA_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# _classify_disasm_line() outcome kinds:
_LINE_IMM = "imm"  # store/push of a 1..8 byte printable immediate
_LINE_IMM_BAD = "imm_bad"  # immediate present but non-printable / wrong size -> break run
_LINE_OTHER = "other"  # not an immediate instruction -> gap (tolerated up to 1)


def _classify_disasm_line(text: str) -> tuple[str, bytes | None]:
    """Classify one disassembly line for stack-string purposes.

    Returns ``(kind, immediate_bytes)`` where kind is ``imm`` (bytes set),
    ``imm_bad`` (an immediate exists but fails size/printable constraints —
    this *breaks* a run), or ``other`` (no immediate — counts as a gap).

    Accepts IDA style (``mov [rbp+var_14], 65h``, ``push 6C6C6548h``,
    quoted chars ``'abcd'``) and Binary Ninja style (``0x65``,
    ``mov qword ptr [rbp-0x14 {var_14}], 0x65``). Plain decimal and negative
    immediates are deliberately skipped (too noisy / not requested).
    """
    t = text.strip()
    if not t:
        return (_LINE_OTHER, None)
    parts = t.split(None, 1)
    mnemonic = parts[0].lower()
    if mnemonic not in _IMM_MNEMONICS:
        return (_LINE_OTHER, None)
    rest = parts[1] if len(parts) > 1 else ""
    # Immediate is the LAST operand (after the final comma); strip IDA comments.
    last_operand = rest.rsplit(",", 1)[-1]
    imm_text = last_operand.split(";", 1)[0].strip()
    if not imm_text:
        return (_LINE_OTHER, None)

    quoted = _QUOTED_IMM_RE.match(imm_text)
    if quoted:
        # IDA char constants: literal characters, in order.
        try:
            raw = quoted.group(1).encode("latin-1", "replace")
        except Exception:
            return (_LINE_IMM_BAD, None)
    elif _HEX_0X_IMM_RE.match(imm_text) or _HEX_H_IMM_RE.match(imm_text):
        digits = imm_text[2:] if imm_text[:2].lower() == "0x" else imm_text[:-1]
        try:
            value = int(digits, 16)
        except ValueError:
            return (_LINE_IMM_BAD, None)
        nbytes = (value.bit_length() + 7) // 8
        if nbytes < 1 or nbytes > _MAX_IMM_BYTES:
            return (_LINE_IMM_BAD, None)
        raw = value.to_bytes(nbytes, "little")
    else:
        # Not immediate-looking (register, memory, label...): a plain gap.
        return (_LINE_OTHER, None)

    if not raw or len(raw) > _MAX_IMM_BYTES:
        return (_LINE_IMM_BAD, None)
    if not all(_is_printable_byte(b) for b in raw):
        return (_LINE_IMM_BAD, None)
    return (_LINE_IMM, raw)


def find_stack_strings_in_lines(lines: list[tuple[int, str]] | None) -> list[dict[str, Any]]:
    """Recover strings built from consecutive immediate stores/pushes.

    ``lines`` is ``[(address, disasm_text), ...]`` in program order. A run is
    a sequence of instructions whose immediates (1..8 bytes each) are fully
    printable ASCII in little-endian byte order; up to one non-immediate
    instruction may appear between two immediates (compilers interleave
    ``lea``/register moves). A non-printable immediate breaks the run.

    Returns ``[{func_hint, address, end_address, string, instructions}]``
    per run whose reconstructed string is at least
    ``_MIN_STACK_STRING_LEN`` characters long.
    """
    results: list[dict[str, Any]] = []
    run_bytes = bytearray()
    run_addrs: list[int] = []
    gap = 0

    def flush() -> None:
        nonlocal run_bytes, run_addrs, gap
        if run_addrs and len(run_bytes) >= _MIN_STACK_STRING_LEN:
            results.append(
                {
                    "func_hint": None,
                    "address": run_addrs[0],
                    "end_address": run_addrs[-1],
                    "string": run_bytes.decode("ascii", "replace"),
                    "instructions": list(run_addrs),
                }
            )
        run_bytes = bytearray()
        run_addrs = []
        gap = 0

    for entry in lines or []:
        try:
            addr, text = entry
        except Exception:
            continue
        addr_i = _coerce_addr(addr)
        if addr_i is None:
            continue
        kind, raw = _classify_disasm_line(text if isinstance(text, str) else str(text))
        if kind == _LINE_IMM and raw is not None:
            if run_addrs and gap > _MAX_RUN_GAP:
                flush()
            gap = 0
            run_bytes.extend(raw)
            run_addrs.append(addr_i)
        elif kind == _LINE_IMM_BAD:
            flush()
        else:
            if run_addrs:
                gap += 1
    flush()
    return results


def _coerce_addr(addr: Any) -> int | None:
    """Coerce an address that may arrive as int, decimal or hex string."""
    try:
        if isinstance(addr, str):
            try:
                return int(addr, 0)
            except ValueError:
                return int(addr)
        return int(addr)
    except Exception:
        return None


def _fmt_addr(addr: Any) -> str:
    try:
        return hex(int(addr))
    except Exception:
        return str(addr)


def format_stack_strings_report(result: dict[str, Any]) -> str:
    """Format collect_stack_strings() output as markdown (pure, testable)."""
    functions = result.get("functions") or []
    lines = ["## Stack String Recovery Report\n"]

    if not functions:
        lines.append("No stack strings recovered from immediate stores/pushes.")
        lines.append("")
        lines.append(
            "Tip: obfuscated binaries often build strings via sequences like "
            "`mov [rbp+var_X], 6C6C6548h` / `push 0x6c6c6548` — none were found. "
            "Try `decode_string` on individual suspicious constants instead."
        )
        return "\n".join(lines)

    total = result.get("total")
    if not isinstance(total, int):
        total = sum(len(f.get("strings") or []) for f in functions)
    lines.append(f"Recovered **{total} stack string(s)** across **{len(functions)} function(s)**.\n")

    for func in functions[:_MAX_REPORT_FUNCTIONS]:
        name = func.get("name") or "??"
        strings = func.get("strings") or []
        lines.append(f"### {name} (`{_fmt_addr(func.get('address'))}`)\n")
        for entry in strings[:_MAX_REPORT_STRINGS_PER_FUNC]:
            text = str(entry.get("string", "")).replace("`", "'")
            n_insns = len(entry.get("instructions") or [])
            lines.append(
                f"- `{text}` — {n_insns} instruction(s), "
                f"`{_fmt_addr(entry.get('address'))}`..`{_fmt_addr(entry.get('end_address'))}`"
            )
        extra = len(strings) - _MAX_REPORT_STRINGS_PER_FUNC
        if extra > 0:
            lines.append(f"- ...and {extra} more string(s) in this function")
        lines.append("")

    extra_funcs = len(functions) - _MAX_REPORT_FUNCTIONS
    if extra_funcs > 0:
        lines.append(f"...and {extra_funcs} more function(s) with findings.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Host collectors
# ---------------------------------------------------------------------------


def _clean_ida_line(text: str) -> str:
    """Strip IDA color tags / control characters from a disassembly line."""
    if _IDA_LINES_AVAILABLE:
        try:
            cleaned = ida_lines.tag_remove(text)
            if isinstance(cleaned, str):
                return cleaned
        except Exception:
            pass
    return _IDA_CONTROL_CHARS_RE.sub("", text)


def _collect_lines_ida(func_addr: int) -> list[tuple[int, str]]:
    """Collect (address, disasm text) for every instruction in an IDA function."""
    lines: list[tuple[int, str]] = []
    try:
        items = idautils.FuncItems(func_addr)
    except Exception:
        return lines
    count = 0
    for ea in items:
        count += 1
        if count > _MAX_IDA_FUNC_INSNS:
            break
        try:
            ea_int = int(ea)
        except Exception:
            continue
        text: Any = None
        try:
            text = idc.generate_disasm_line(ea_int, 0)
        except Exception:
            text = None
        if not text:
            try:
                text = idc.GetDisasm(ea_int)
            except Exception:
                text = None
        if not text:
            continue
        lines.append((ea_int, _clean_ida_line(str(text))))
    return lines


def _collect_lines_binja(func: Any) -> list[tuple[int, str]]:
    """Collect (address, disasm text) for a Binary Ninja function.

    ``get_disassembly()`` yields one line per instruction, so lines are
    paired with addresses from ``func.instructions``; when the counts
    disagree (API drift, interleaved labels), the function is skipped.
    """
    try:
        text = func.get_disassembly()
    except Exception:
        return []
    if not isinstance(text, str) or not text:
        return []
    try:
        addrs = [int(addr) for _data, addr in func.instructions]
    except Exception:
        return []
    text_lines = text.splitlines()
    if len(text_lines) != len(addrs):
        return []
    return list(zip(addrs, text_lines, strict=True))


def _find_stack_strings_ida() -> dict[str, Any]:
    """Scan every (reasonably sized) function in the IDA database."""
    functions_out: list[dict[str, Any]] = []
    total = 0
    try:
        func_addrs = list(idautils.Functions())
    except Exception:
        return {"functions": [], "total": 0}
    for func_addr in func_addrs:
        try:
            n_items = len(list(idautils.FuncItems(func_addr)))
        except Exception:
            continue
        if n_items > _MAX_IDA_FUNC_INSNS:
            continue
        try:
            name = idc.get_func_name(func_addr) or ""
        except Exception:
            name = ""
        try:
            lines = _collect_lines_ida(func_addr)
        except Exception:
            continue
        if not lines:
            continue
        try:
            found = find_stack_strings_in_lines(lines)
        except Exception:
            continue
        if not found:
            continue
        functions_out.append({"address": func_addr, "name": name, "strings": found})
        total += len(found)
    return {"functions": functions_out, "total": total}


def _find_stack_strings_binja() -> dict[str, Any]:
    """Scan every (up to _MAX_BINJA_FUNCTIONS) function in the BinaryView."""
    functions_out: list[dict[str, Any]] = []
    total = 0
    bv = get_binary_ninja_view()
    if bv is None:
        return {"functions": [], "total": 0}
    try:
        funcs = list(bv.functions)
    except Exception:
        return {"functions": [], "total": 0}
    for func in funcs[:_MAX_BINJA_FUNCTIONS]:
        try:
            addr = int(func.start)
        except Exception:
            continue
        try:
            name = str(func.name)
        except Exception:
            name = ""
        try:
            lines = _collect_lines_binja(func)
        except Exception:
            continue
        if not lines:
            continue
        try:
            found = find_stack_strings_in_lines(lines)
        except Exception:
            continue
        if not found:
            continue
        functions_out.append({"address": addr, "name": name, "strings": found})
        total += len(found)
    return {"functions": functions_out, "total": total}


def collect_stack_strings() -> dict[str, Any]:
    """Host-agnostic aggregation of stack-string findings.

    Returns ``{"host": "ida" | "binary_ninja" | None, "functions":
    [{"address", "name", "strings": [...]}], "total": int}``.
    """
    if IDA_AVAILABLE:
        result = _find_stack_strings_ida()
        result["host"] = "ida"
        return result
    if BINJA_AVAILABLE:
        result = _find_stack_strings_binja()
        result["host"] = "binary_ninja"
        return result
    return {"host": None, "functions": [], "total": 0}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(
    category="analysis",
    description="Decode an obfuscated string (hex/base32/base64/rot/xor-brute...) with ranked candidates",
)
def decode_string(
    value: Annotated[str, "The obfuscated string to decode"],
    scheme: Annotated[str, "Specific scheme (hex/base32/base64/base64url/rot13/rot47/reverse/xor_brute/decimal) or 'auto'"] = "auto",
) -> str:
    """Decode an obfuscated string and return ranked candidate decodings as markdown."""
    return format_decode_report(decode_value(value, scheme))


@tool(
    category="analysis",
    description="Recover stack strings built from immediate stores/pushes across all functions",
)
def find_stack_strings() -> str:
    """Scan all functions for stack strings assembled from immediates; markdown report."""
    result = collect_stack_strings()
    if result.get("host") is None:
        return (
            "Stack string recovery unavailable: no disassembler host detected. "
            "Run this tool inside IDA Pro or Binary Ninja so disassembly can be collected."
        )
    return format_stack_strings_report(result)
