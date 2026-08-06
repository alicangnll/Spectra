"""AI-Enhanced Features tool for IDA Pro."""

from __future__ import annotations

from typing import Annotated

# Try to import IDA API
try:
    import idautils
    IDA_AVAILABLE = True
except ImportError:
    IDA_AVAILABLE = False

from ...tools.ai_features import (
    auto_document_function,
    find_similar_functions,
    semantic_search,
)
from ...tools.base import tool


@tool(category="ai", description="Search functions by semantic meaning")
def search_functions(
    query: Annotated[str, "Natural language query (e.g., 'crypto functions', 'file operations')"],
    limit: Annotated[int, "Maximum number of results"] = 10,
) -> str:
    """Search for functions using natural language queries.

    Examples:
    - "crypto functions" - finds encryption/hashing functions
    - "file operations" - finds file I/O functions
    - "network" - finds socket/network functions
    - "string manipulation" - finds string functions

    Args:
        query: Natural language search query
        limit: Maximum results to return

    Returns:
        Ranked list of matching functions with relevance scores
        and reasons for each match.
    """
    return semantic_search(query, limit)


@tool(category="ai", description="Find functions similar to a given function")
def find_similar(
    address: Annotated[int, "Function address to find similar functions for"],
    limit: Annotated[int, "Maximum number of results"] = 10,
) -> str:
    """Find functions that are similar to the given function.

    Similarity is based on:
    - Algorithm used
    - Function category
    - Size metrics
    - Import/API patterns
    - Call patterns

    Args:
        address: Function address
        limit: Maximum results to return

    Returns:
        List of similar functions with similarity scores.
    """
    return find_similar_functions(address, limit)


@tool(category="ai", description="Generate automatic documentation for a function")
def document_function(
    address: Annotated[int, "Function address to document"],
) -> str:
    """Generate comprehensive documentation for a function.

    Documentation includes:
    - Function name and address
    - Detected category (crypto, network, file, etc.)
    - Algorithm detection (if applicable)
    - Size metrics (instructions, basic blocks)
    - Functions called
    - External APIs used
    - Referenced strings
    - Behavior summary
    - Analysis notes

    Args:
        address: Function address

    Returns:
        Formatted markdown documentation.
    """
    return auto_document_function(address)


@tool(category="ai", description="Identify algorithms used in functions")
def identify_algorithms(
    pattern: Annotated[str, "Algorithm pattern: crypto, hash, sort, compress, encrypt"] = "crypto",
) -> str:
    """Identify functions that implement specific algorithms.

    Args:
        pattern: Type of algorithm to search for
                 - crypto: All cryptographic algorithms
                 - hash: Hash functions (MD5, SHA, CRC)
                 - sort: Sorting algorithms
                 - compress: Compression algorithms
                 - encrypt: Encryption algorithms

    Returns:
        List of functions implementing the requested algorithm type.
    """
    from ...tools.ai_features import ALGORITHM_SIGNATURES, _extract_function_features_ida

    # Map pattern to algorithm types
    pattern_map = {
        "crypto": ["md5", "sha1", "sha256", "aes", "rsa", "crc32"],
        "hash": ["md5", "sha1", "sha256", "crc32"],
        "sort": ["bubble_sort", "quick_sort", "merge_sort"],
        "compress": ["gzip", "lz4", "zlib"],
        "encrypt": ["aes", "rsa", "xor_cipher"],
    }

    target_algos = pattern_map.get(pattern.lower(), [])

    if not target_algos:
        return f"Unknown pattern: {pattern}. Try: crypto, hash, sort, compress, encrypt"

    results = []
    for func_ea in idautils.Functions():
        features = _extract_function_features_ida(func_ea)
        if features.get("detected_algorithm") in target_algos:
            results.append(features)

    if not results:
        return f"No {pattern} algorithms found."

    report = f"## {pattern.title()} Algorithms Detected\n\n"
    report += f"**Count:** {len(results)}\n\n"

    for func in results[:20]:
        report += f"### {func['name']}\n"
        report += f"**Address:** `0x{func['address']:X}`\n"
        report += f"**Algorithm:** {func['detected_algorithm']}\n"
        report += f"**Size:** {func['instruction_count']} instructions\n\n"

    if len(results) > 20:
        report += f"_... and {len(results) - 20} more_\n"

    return report
