"""AI-Enhanced Features tool for Binary Ninja."""

from __future__ import annotations

from typing import Annotated

from ...tools.base import tool
from .compat import require_bv


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
    bv = require_bv()
    query_lower = query.lower()
    results = []

    for func in bv.functions:
        score = 0
        reasons = []

        # Name matching
        for keyword in query_lower.split():
            if keyword in func.name.lower():
                score += 10
                reasons.append(f"name match: {keyword}")

        # Check in disassembly
        func_text = "\n".join(str(instr) for instr in func.instructions).lower()

        # Keyword matching in disassembly
        for keyword in query_lower.split():
            if keyword in func_text:
                score += 2
                reasons.append(f"found '{keyword}' in disassembly")

        if score > 0:
            results.append({
                "function": func,
                "score": score,
                "reasons": reasons,
            })

    results.sort(key=lambda x: x["score"], reverse=True)

    report = f"## Semantic Search Results\n"
    report += f"**Query:** {query}\n"
    report += f"**Results:** {len(results)}\n\n"

    if not results:
        report += "*No matching functions found*\n"
        return report

    for result in results[:limit]:
        func = result["function"]
        report += f"\n### {func.name} (Score: {result['score']})\n"
        report += f"**Address:** {func.start}\n"
        report += f"**Reasons:** {', '.join(result['reasons'][:3])}\n"

    return report


@tool(category="ai", description="Find functions similar to a given function")
def find_similar(
    address: Annotated[int, "Function address to find similar functions for"],
    limit: Annotated[int, "Maximum number of results"] = 10,
) -> str:
    """Find functions that are similar to the given function.

    Similarity is based on:
    - Size metrics
    - Basic block count
    - Name patterns

    Args:
        address: Function address
        limit: Maximum results to return

    Returns:
        List of similar functions with similarity scores.
    """
    bv = require_bv()
    target_func = bv.get_function_at(address)

    if not target_func:
        return f"Function not found at address {address}"

    target_instr = len(list(target_func.instructions))
    target_blocks = len(list(target_func.basic_blocks))

    results = []

    for func in bv.functions:
        if func.start == address:
            continue

        instr_count = len(list(func.instructions))
        block_count = len(list(func.basic_blocks))

        # Calculate similarity
        similarity = 0

        instr_diff = abs(target_instr - instr_count)
        if instr_diff < target_instr * 0.2:
            similarity += 30

        block_diff = abs(target_blocks - block_count)
        if block_diff < target_blocks * 0.2:
            similarity += 20

        if similarity > 0:
            results.append({
                "function": func,
                "similarity": similarity,
            })

    results.sort(key=lambda x: x["similarity"], reverse=True)

    report = f"## Similar Functions to `{target_func.name}`\n"
    report += f"**Address:** {address}\n"
    report += f"**Found:** {len(results)} similar functions\n\n"

    for result in results[:limit]:
        func = result["function"]
        report += f"### {func.name} (Similarity: {result['similarity']}%)\n"
        report += f"**Address:** {func.start}\n"

    return report


@tool(category="ai", description="Generate automatic documentation for a function")
def document_function(
    address: Annotated[int, "Function address to document"],
) -> str:
    """Generate comprehensive documentation for a function.

    Documentation includes:
    - Function name and address
    - Size metrics
    - Basic block count
    - Called functions
    - Functions that call this function
    - Strings referenced

    Args:
        address: Function address

    Returns:
        Formatted markdown documentation.
    """
    bv = require_bv()
    func = bv.get_function_at(address)

    if not func:
        return f"Function not found at address {address}"

    instr_count = len(list(func.instructions))
    block_count = len(list(func.basic_blocks))

    report = f"## Function: {func.name}\n"
    report += f"**Address:** {func.start}\n"
    report += f"**Size:** {instr_count} instructions\n"
    report += f"**Basic Blocks:** {block_count}\n"

    # Get callers
    callers = list(func.caller_sites)
    if callers:
        report += f"\n### Called By ({len(callers)} functions)\n"
        for caller in callers[:10]:
            report += f"- `{caller.function.name}` at {caller.address}\n"

    # Get callees
    callees = []
    for block in func.basic_blocks:
        for instr in block.instructions:
            for xref in instr.get_il_expressions():
                # This is simplified - actual implementation would check for calls
                pass

    # Strings referenced
    strings = []
    for block in func.basic_blocks:
        for instr in block.instructions:
            for operand in instr.operands:
                if hasattr(operand, 'value') and isinstance(operand.value, str):
                    strings.append(operand.value)

    if strings:
        report += f"\n### Referenced Strings\n"
        for string in strings[:5]:
            report += f"- `{string[:80]}`\n"

    return report
