"""AI-Enhanced Features for reverse engineering.

Provides semantic search, similarity detection, auto-documentation,
and code explanation capabilities using embedding-based analysis.
"""

from __future__ import annotations

import re
from typing import Any

# Try to import IDA API
try:
    import ida_xref
    import idaapi
    import idautils
    import idc

    IDA_AVAILABLE = True
except ImportError:
    IDA_AVAILABLE = False

# Try to import Binary Ninja API
try:
    import binaryninja  # noqa: F401 — availability probe

    BINJA_AVAILABLE = True
except ImportError:
    BINJA_AVAILABLE = False


# Algorithm and pattern signatures
ALGORITHM_SIGNATURES = {
    # Sorting algorithms
    "bubble_sort": {
        "patterns": [r"for.*for.*if.*swap", r"compare.*adjacent"],
        "keywords": ["bubble", "swap", "adjacent"],
        "complexity": "O(n²)",
    },
    "quick_sort": {
        "patterns": [r"partition", r"pivot", r"quicksort"],
        "keywords": ["pivot", "partition", "quick"],
        "complexity": "O(n log n)",
    },
    "merge_sort": {
        "patterns": [r"merge", r"divide.*conquer", r"merge.*sort"],
        "keywords": ["merge", "divide", "conquer"],
        "complexity": "O(n log n)",
    },
    # Hash functions
    "md5": {
        "patterns": [r"MD5", r"md5", r"0x67452301"],
        "keywords": ["md5", "0x67452301", "aabbccdd"],
        "complexity": "O(n)",
    },
    "sha1": {
        "patterns": [r"SHA1", r"sha1", r"0x5a827999", r"0x6ed9eba1"],
        "keywords": ["sha1", "0x5a827999"],
        "complexity": "O(n)",
    },
    "sha256": {
        "patterns": [r"SHA256", r"sha256", r"0x6a09e667"],
        "keywords": ["sha256", "sha-256", "0x6a09e667"],
        "complexity": "O(n)",
    },
    "crc32": {
        "patterns": [r"CRC32", r"crc32", r"0xedb88320", r"0x82f63b78"],
        "keywords": ["crc32", "0xedb88320"],
        "complexity": "O(n)",
    },
    # Encryption
    "aes": {
        "patterns": [r"AES", r"aes", r"Rijndael", r"sbox", r"mixcolumns"],
        "keywords": ["aes", "rijndael", "sbox", "shiftrow"],
        "complexity": "O(n)",
    },
    "rsa": {
        "patterns": [r"RSA", r"mod.*exp", r"pow.*mod", r"private.*public"],
        "keywords": ["rsa", "modulo", "exponent"],
        "complexity": "O(log n)",
    },
    "xor_cipher": {
        "patterns": [r"\^.*\^", r"xor.*loop", r"key.*xor"],
        "keywords": ["xor", "obfuscate"],
        "complexity": "O(n)",
    },
    # Compression
    "gzip": {
        "patterns": [r"gzip", r"deflate", r"0x1f8b"],
        "keywords": ["gzip", "deflate", "inflate"],
        "complexity": "O(n)",
    },
    "lz4": {
        "patterns": [r"LZ4", r"lz4", r"rapid.*compress"],
        "keywords": ["lz4", "rapid", "compress"],
        "complexity": "O(n)",
    },
    "zlib": {
        "patterns": [r"zlib", r"compress.*bound", r"adler32"],
        "keywords": ["zlib", "adler", "deflate"],
        "complexity": "O(n)",
    },
    # Data structures
    "linked_list": {
        "patterns": [r"next.*ptr", r"->next", r"\.next", r"head.*node"],
        "keywords": ["next", "prev", "head", "node"],
        "complexity": "O(n)",
    },
    "binary_tree": {
        "patterns": [r"left.*right", r"->left", r"->right", r"tree.*node"],
        "keywords": ["left", "right", "root", "tree"],
        "complexity": "O(log n)",
    },
    "hash_table": {
        "patterns": [r"hash.*table", r"bucket", r"collision", r"rehash"],
        "keywords": ["hash", "bucket", "table", "collision"],
        "complexity": "O(1)",
    },
}


# Common code idioms and compiler patterns
COMPILER_IDIOMS = {
    "prologue": {
        "x86": [r"push.*ebp", r"mov.*ebp.*esp", r"sub.*esp.*0x"],
        "x64": [r"push.*rbp", r"mov.*rbp.*rsp", r"sub.*rsp.*0x"],
        "arm": [r"stp.*x29.*x30", r"mov.*x29.*sp"],
    },
    "epilogue": {
        "x86": [r"leave", r"ret", r"pop.*ebp"],
        "x64": [r"leave", r"ret", r"pop.*rbp"],
        "arm": [r"ldp.*x29.*x30", r"ret"],
    },
    "string_length": {
        "x86": [r"rep.*scasb", r"lodsb.*test"],
        "x64": [r"rep.*scasb", r"lodsb.*test"],
    },
    "memcpy": {
        "x86": [r"rep.*movs[bwd]", r"movs[bwd]"],
        "x64": [r"rep.*movs[bwdq]"],
    },
    "memset": {
        "x86": [r"rep.*stos[bwd]", r"stos[bwd]"],
        "x64": [r"rep.*stos[bwdq]"],
    },
}


# Semantic categories for function classification
FUNCTION_CATEGORIES = {
    "crypto": {
        "keywords": ["crypt", "cipher", "decrypt", "encrypt", "hash", "md5", "sha", "aes", "rsa"],
        "apis": ["CryptEncrypt", "CryptDecrypt", "CryptHash", "MD5Init", "SHA1Init"],
    },
    "network": {
        "keywords": ["socket", "connect", "bind", "listen", "send", "recv", "http", "tcp", "udp"],
        "apis": ["socket", "connect", "bind", "send", "recv", "WSASocket", "InternetConnect"],
    },
    "file": {
        "keywords": ["file", "open", "close", "read", "write", "seek", "create"],
        "apis": ["CreateFile", "OpenFile", "ReadFile", "WriteFile", "fopen", "fclose"],
    },
    "string": {
        "keywords": ["string", "str", "memcpy", "strcpy", "strcmp", "strlen"],
        "apis": ["strcpy", "strcmp", "strlen", "memcpy", "memcmp"],
    },
    "memory": {
        "keywords": ["malloc", "free", "alloc", "heap", "pool"],
        "apis": ["malloc", "free", "HeapAlloc", "HeapFree", "ExAllocatePool"],
    },
    "thread": {
        "keywords": ["thread", "mutex", "lock", "create", "synchroniz"],
        "apis": ["CreateThread", "pthread_create", "EnterCriticalSection", "pthread_mutex_lock"],
    },
    "registry": {
        "keywords": ["registry", "reg", "key", "value"],
        "apis": ["RegOpenKey", "RegCreateKey", "RegSetValue", "RegQueryValue"],
    },
    "ui": {
        "keywords": ["window", "dialog", "menu", "message", "paint", "draw"],
        "apis": ["CreateWindow", "DialogBox", "BeginPaint", "DefWindowProc"],
    },
}


def _get_disasm_text(ea: int) -> str:
    """Get disassembly text for an address, compatible with IDA Pro 9.x.

    Replaces the deprecated idc.generate_disasm_text().
    """
    try:
        disasm = idaapi.get_disasm(ea)
        if disasm:
            return disasm
    except Exception:
        pass

    # Fallback: build from mnemonic and operands
    try:
        mnem = idaapi.print_insn_mnem(ea)
        op1 = idaapi.print_operand(ea, 0)
        op2 = idaapi.print_operand(ea, 1)
        result = mnem
        if op1:
            result += f" {op1}"
        if op2:
            result += f", {op2}"
        return result
    except Exception:
        return f"loc_{ea:x}"


def _extract_function_features_ida(func_ea: int) -> dict[str, Any]:
    """Extract features from a function for similarity matching."""
    if not IDA_AVAILABLE:
        return {}

    func_name = idc.get_func_name(func_ea)

    # Get basic metrics
    instr_count = 0
    basic_blocks = 0
    calls = []
    strings = []
    imports = []

    try:
        flow = idaapi.FlowChart(idaapi.get_func(func_ea))
        basic_blocks = flow.size

        for block in flow:
            for instr_ea in idautils.Heads(block.start_ea, block.end_ea):
                instr_count += 1

                # Track function calls
                if idc.get_operand_type(instr_ea, 0) == idc.o_far or idc.get_operand_type(instr_ea, 0) == idc.o_near:
                    xref = idc.get_operand_value(instr_ea, 0)
                    if xref:
                        called = idc.get_name(xref)
                        if called:
                            calls.append(called)

                # Track string references
                for xref in idautils.XrefsFrom(instr_ea):
                    if xref.type == idaapi.XREF_DATA:
                        # Check if data is string
                        str_type = idc.get_str_type_contents(xref.to)
                        if str_type:
                            str_val = idc.get_strlit_contents(xref.to)
                            if str_val:
                                strings.append(str(str_val))

    except Exception:
        # Fallback
        func = idaapi.get_func(func_ea)
        func_end = func.end_ea if func else func_ea
        for _instr_ea in idautils.Heads(func_ea, func_end):
            instr_count += 1

    # Get imports used by function
    func = idaapi.get_func(func_ea)
    func_end = func.end_ea if func else func_ea
    for xref in idautils.XrefsTo(func_ea):
        # Check for call xrefs (XREF_FAR = 0x2 in IDA 9.x)
        # Note: XREF_NEAR may not exist, use getattr or numeric value
        xref_far = ida_xref.XREF_FAR
        xref_near = getattr(ida_xref, "XREF_NEAR", 4)  # Fallback to numeric value
        if xref.type in (xref_far, xref_near):
            # Check if called function is import
            for imp_xref in idautils.XrefsFrom(xref.frm):
                # Import xrefs have type XREF_DATA (0x1) pointing to import table
                # Check if xref type is XREF_DATA
                if imp_xref.type == ida_xref.XREF_DATA:
                    imp_name = idc.get_name(xref.frm)
                    if imp_name and "import" in idc.get_full_name(xref.frm).lower():
                        imports.append(imp_name)

    # Get function text for pattern matching
    func_text = ""
    try:
        import ida_hexrays

        if ida_hexrays.init_hexrays_plugin():
            cfunc = ida_hexrays.decompile(func_ea)
            if cfunc:
                func_text = str(cfunc).lower()
    except Exception:
        pass

    if not func_text:
        func = idaapi.get_func(func_ea)
        func_end = func.end_ea if func else func_ea
        for instr_ea in idautils.Heads(func_ea, func_end):
            disasm = _get_disasm_text(instr_ea)
            func_text += disasm.lower() + "\n"

    # Detect algorithm
    detected_algo = None
    for algo_name, algo_info in ALGORITHM_SIGNATURES.items():
        for pattern in algo_info["patterns"]:
            if re.search(pattern, func_text, re.IGNORECASE):
                detected_algo = algo_name
                break
        if detected_algo:
            break

    # Classify function category
    category = None
    for cat_name, cat_info in FUNCTION_CATEGORIES.items():
        for keyword in cat_info["keywords"]:
            if keyword in func_name.lower() or keyword in func_text:
                category = cat_name
                break
            for api in cat_info.get("apis", []):
                if api.lower() in func_text:
                    category = cat_name
                    break
            if category:
                break
        if category:
            break

    return {
        "address": func_ea,
        "name": func_name,
        "instruction_count": instr_count,
        "basic_blocks": basic_blocks,
        "calls": calls[:10],
        "strings": strings[:5],
        "imports": imports[:10],
        "detected_algorithm": detected_algo,
        "category": category,
        "text_sample": func_text[:500],  # Sample for matching
    }


def _semantic_search_ida(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search for functions semantically similar to the query."""
    if not IDA_AVAILABLE:
        return []

    query_lower = query.lower()
    results = []

    # Extract keywords from query
    query_keywords = set(re.findall(r"\b\w+\b", query_lower))

    for func_ea in idautils.Functions():
        features = _extract_function_features_ida(func_ea)

        # Calculate relevance score
        score = 0

        # Name matching
        for keyword in query_keywords:
            if keyword in features["name"].lower():
                score += 10

        # Category matching
        if features["category"]:
            if features["category"] in query_lower:
                score += 15
            for keyword in query_keywords:
                if keyword in features["category"]:
                    score += 5

        # Algorithm matching
        if features["detected_algorithm"]:
            if features["detected_algorithm"] in query_lower:
                score += 20
            for keyword in query_keywords:
                if keyword in features["detected_algorithm"]:
                    score += 10

        # Import matching
        for imp in features["imports"]:
            imp_lower = imp.lower()
            for keyword in query_keywords:
                if keyword in imp_lower:
                    score += 3

        # String matching
        for string in features["strings"]:
            string_lower = string.lower()
            for keyword in query_keywords:
                if keyword in string_lower:
                    score += 2

        # Add to results if score > 0
        if score > 0:
            results.append(
                {
                    "function": features,
                    "score": score,
                    "reason": _get_match_reason(query, features),
                }
            )

    # Sort by score and return top results
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def _get_match_reason(query: str, features: dict[str, Any]) -> str:
    """Get human-readable reason for match."""
    reasons = []

    query_lower = query.lower()

    if features["category"] and features["category"] in query_lower:
        reasons.append(f"category: {features['category']}")

    if features["detected_algorithm"]:
        reasons.append(f"algorithm: {features['detected_algorithm']}")

    matching_imports = [imp for imp in features["imports"] if any(kw in imp.lower() for kw in query_lower.split())]
    if matching_imports:
        reasons.append(f"imports: {', '.join(matching_imports[:3])}")

    matching_strings = [s for s in features["strings"] if any(kw in s.lower() for kw in query_lower.split())]
    if matching_strings:
        reasons.append("strings match")

    if features["name"] and any(kw in features["name"].lower() for kw in query_lower.split()):
        reasons.append("name match")

    return "; ".join(reasons) if reasons else "semantic similarity"


def _find_similar_functions_ida(func_ea: int, limit: int = 10) -> list[dict[str, Any]]:
    """Find functions similar to the given function."""
    if not IDA_AVAILABLE:
        return []

    target_features = _extract_function_features_ida(func_ea)
    results = []

    for other_ea in idautils.Functions():
        if other_ea == func_ea:
            continue

        other_features = _extract_function_features_ida(other_ea)

        # Calculate similarity
        similarity = 0

        # Algorithm match
        if (
            target_features["detected_algorithm"]
            and target_features["detected_algorithm"] == other_features["detected_algorithm"]
        ):
            similarity += 30

        # Category match
        if target_features["category"] and target_features["category"] == other_features["category"]:
            similarity += 20

        # Size similarity
        size_diff = abs(target_features["instruction_count"] - other_features["instruction_count"])
        if size_diff < target_features["instruction_count"] * 0.2:
            similarity += 15

        # Import overlap
        target_imports = set(imp.lower() for imp in target_features["imports"])
        other_imports = set(imp.lower() for imp in other_features["imports"])
        if target_imports and other_imports:
            overlap = len(target_imports & other_imports)
            similarity += overlap * 2

        # Call pattern similarity
        target_calls = set(c.lower() for c in target_features["calls"])
        other_calls = set(c.lower() for c in other_features["calls"])
        if target_calls and other_calls:
            overlap = len(target_calls & other_calls)
            similarity += overlap

        # Add to results if similarity > 0
        if similarity > 10:
            results.append(
                {
                    "function": other_features,
                    "similarity": similarity,
                }
            )

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


def _generate_function_documentation(func_ea: int) -> str:
    """Generate automatic documentation for a function."""
    if not IDA_AVAILABLE:
        return "IDA Pro API not available"

    features = _extract_function_features_ida(func_ea)

    doc_lines = [f"## Function: {features['name']}\n"]
    doc_lines.append(f"**Address:** `0x{features['address']:X}`\n")

    # Category
    if features["category"]:
        doc_lines.append(f"**Category:** {features['category']}\n")

    # Algorithm
    if features["detected_algorithm"]:
        algo_info = ALGORITHM_SIGNATURES.get(features["detected_algorithm"], {})
        doc_lines.append(f"**Algorithm:** {features['detected_algorithm'].replace('_', ' ').title()}\n")
        if "complexity" in algo_info:
            doc_lines.append(f"**Complexity:** {algo_info['complexity']}\n")

    # Size metrics
    doc_lines.append("\n### Metrics\n")
    doc_lines.append(f"- **Instructions:** {features['instruction_count']}\n")
    doc_lines.append(f"- **Basic Blocks:** {features['basic_blocks']}\n")
    doc_lines.append(f"- **Calls:** {len(features['calls'])} functions\n")

    # Calls
    if features["calls"]:
        doc_lines.append("\n### Function Calls\n")
        for call in features["calls"][:10]:
            doc_lines.append(f"- `{call}`\n")

    # Imports
    if features["imports"]:
        doc_lines.append("\n### External APIs Used\n")
        for imp in features["imports"][:15]:
            doc_lines.append(f"- `{imp}`\n")

    # Strings
    if features["strings"]:
        doc_lines.append("\n### Referenced Strings\n")
        for string in features["strings"][:5]:
            doc_lines.append(f"- `{string[:80]}`\n")

    # Behavior summary
    doc_lines.append("\n### Behavior Summary\n")

    summary_parts = []

    if features["category"]:
        category_desc = {
            "crypto": "Performs cryptographic operations",
            "network": "Handles network communication",
            "file": "Performs file I/O operations",
            "string": "Manipulates string data",
            "memory": "Manages memory allocation",
            "thread": "Handles threading/synchronization",
            "registry": "Accesses system registry",
            "ui": "Manages user interface elements",
        }.get(features["category"], "")
        if category_desc:
            summary_parts.append(category_desc)

    if features["detected_algorithm"]:
        summary_parts.append(f"Implements {features['detected_algorithm'].replace('_', ' ')} algorithm")

    if features["imports"]:
        high_level_apis = [
            imp for imp in features["imports"] if any(kw in imp for kw in ["Create", "Open", "Connect", "Send", "Recv"])
        ]
        if high_level_apis:
            summary_parts.append(f"Uses high-level APIs: {', '.join(high_level_apis[:3])}")

    if summary_parts:
        doc_lines.append(f"{' '.join(summary_parts)}.\n")
    else:
        doc_lines.append(f"Function with {features['instruction_count']} instructions.\n")

    # Potential issues
    doc_lines.append("\n### Analysis Notes\n")

    if features["instruction_count"] > 500:
        doc_lines.append("- ⚠️ Large function - may benefit from refactoring\n")

    if features["basic_blocks"] > 20:
        doc_lines.append("- ⚠️ High complexity - consider control flow analysis\n")

    unsafe_calls = [
        call for call in features["calls"] if any(kw in call.lower() for kw in ["strcpy", "sprintf", "gets"])
    ]
    if unsafe_calls:
        doc_lines.append(f"- ⚠️ Uses potentially unsafe functions: {', '.join(unsafe_calls)}\n")

    return "\n".join(doc_lines)


def semantic_search(query: str, limit: int = 10) -> str:
    """Search for functions matching a semantic query.

    Args:
        query: Natural language query (e.g., "crypto functions", "file operations")
        limit: Maximum number of results

    Returns:
        Formatted markdown results
    """
    if IDA_AVAILABLE:
        results = _semantic_search_ida(query, limit)
    else:
        return "Error: IDA Pro API not available"

    report_lines = ["## Semantic Search Results\n"]
    report_lines.append(f"**Query:** {query}\n")
    report_lines.append(f"**Results:** {len(results)}\n")

    if not results:
        report_lines.append("\n*No matching functions found*\n")
        return "\n".join(report_lines)

    for result in results:
        func = result["function"]
        score = result["score"]

        report_lines.append(f"\n### {func['name']} (Score: {score})\n")
        report_lines.append(f"**Address:** `0x{func['address']:X}`\n")
        report_lines.append(f"**Reason:** {result['reason']}\n")
        report_lines.append(f"**Size:** {func['instruction_count']} instructions\n")

        if func["detected_algorithm"]:
            report_lines.append(f"**Algorithm:** {func['detected_algorithm']}\n")

        if func["category"]:
            report_lines.append(f"**Category:** {func['category']}\n")

    return "\n".join(report_lines)


def find_similar_functions(func_ea: int, limit: int = 10) -> str:
    """Find functions similar to the given function.

    Args:
        func_ea: Function address
        limit: Maximum number of results

    Returns:
        Formatted markdown results
    """
    if IDA_AVAILABLE:
        results = _find_similar_functions_ida(func_ea, limit)
    else:
        return "Error: IDA Pro API not available"

    func_name = idc.get_func_name(func_ea) if IDA_AVAILABLE else "unknown"

    report_lines = [f"## Similar Functions to `{func_name}`\n"]
    report_lines.append(f"**Address:** `0x{func_ea:X}`\n")
    report_lines.append(f"**Found:** {len(results)} similar functions\n")

    if not results:
        report_lines.append("\n*No similar functions found*\n")
        return "\n".join(report_lines)

    for result in results:
        func = result["function"]
        similarity = result["similarity"]

        report_lines.append(f"\n### {func['name']} (Similarity: {similarity}%)\n")
        report_lines.append(f"**Address:** `0x{func['address']:X}`\n")
        report_lines.append(f"**Size:** {func['instruction_count']} instructions\n")

        if func["detected_algorithm"]:
            report_lines.append(f"**Algorithm:** {func['detected_algorithm']}\n")

        if func["category"]:
            report_lines.append(f"**Category:** {func['category']}\n")

    return "\n".join(report_lines)


def auto_document_function(func_ea: int) -> str:
    """Generate automatic documentation for a function.

    Args:
        func_ea: Function address

    Returns:
        Formatted markdown documentation
    """
    return _generate_function_documentation(func_ea)


if __name__ == "__main__":
    print("AI-Enhanced Features module loaded")
    print("Available: semantic_search, find_similar_functions, auto_document_function")
