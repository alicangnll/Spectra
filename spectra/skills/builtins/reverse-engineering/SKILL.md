---
name: Reverse Engineering Mastery
description: Comprehensive reverse engineering — binary analysis, decompilation, control flow, data flow, and reconstruction techniques
tags: [reverse-engineering, binary-analysis, decompilation, security-analysis]
---

Task: Reverse Engineering Mastery. You are performing comprehensive binary analysis, reconstructing high-level logic from assembly code.

## Approach

Build a mental map of the binary's structure. Start at the entry point or user-specified function. Name functions as you understand them — each rename makes the next function easier to read. Focus on what the user is interested in, not exhaustive coverage.

## When to Use

Use this skill when:
- Analyzing binary executables and understanding program structure
- Reconstructing high-level logic from assembly code
- Performing comprehensive control flow and data flow analysis
- Understanding compiler optimizations and code patterns
- Reversing proprietary algorithms and data structures
- Analyzing obfuscated code and anti-debugging techniques
- Documenting reverse engineering findings
- Creating detailed technical analysis reports

## Workflow

1. **Binary Overview**
   - `get_binary_info` — format, architecture, size, function count
   - Identify file type (PE, ELF, Mach-O)
   - Map out section structure and layout
   - Find entry points and main execution paths

2. **Interface Analysis**
   - `list_imports` + `list_exports` — understand the binary's interface
   - Identify external dependencies and APIs used
   - Find exported functions (libraries, drivers)

3. **Function Analysis**
   - Build control flow graphs (CFGs)
   - Analyze function boundaries and calling patterns
   - Identify key algorithms and data structures
   - Use `decompile_function` → understand → `rename_function` / `rename_variable`

4. **Data Flow Analysis**
   - Track variable lifetimes and usage
   - Map data transformations
   - Identify global data access patterns
   - Use `xrefs_to` and `xrefs_from` to trace references

5. **Pattern Recognition**
   - Match known code patterns and idioms
   - Identify library functions and standard algorithms
   - Detect custom implementations and optimizations
   - Recognize compiler-generated code

## Call Graph Strategy

Use xref tools BEFORE decompiling for exploration — they're cheaper:
1. `function_xrefs` on entry → map top-level subsystems
2. `xrefs_to` on interesting imports → find API usage
3. Decompile only the nodes you actually need
4. After understanding a function, check its callers

Depth guidance:
- Immediate callers/callees: quick orientation
- 2 levels: neighborhood — usually sufficient
- 3+ levels: subsystem mapping — deep dives

## Domain-Specific Analysis

**Libraries/Frameworks:**
- Focus on exported functions and calling conventions
- Use `list_exports` to map the public API
- Document function signatures and parameters

**Drivers/Kernel Modules:**
- Identify dispatch routines and IOCTL handlers
- Analyze initialization and cleanup
- Consider using `/driver-analysis` for Windows drivers

**Proprietary Formats:**
- Trace parsing code
- Use `create_struct` and `suggest_struct_from_accesses`
- Apply structures with `apply_struct_to_address`

**Firmware/Embedded:**
- Check for library signatures in function prologues
- Map memory-mapped I/O via `list_segments`
- Handle unknown architectures

**Statically Linked (Go/Rust):**
- No imports — look for runtime strings
- Search for `runtime.`, `go.itab.`, `panicked at`
- Function count is high — focus on entry and user code

## Decompilation Strategy

**Assembly Understanding:**
- Learn common instruction patterns
- Recognize compiler optimizations
- Understand calling conventions
- Identify control flow primitives

**Pseudo-code Generation:**
- Convert assembly to readable pseudo-code
- Reconstruct loops and conditionals
- Identify switch statements (jump tables)
- Rebuild exception handling

**Type Recovery:**
- Analyze function signatures
- Reconstruct data types and structures
- Identify class hierarchies (C++)
- Understand template usage

## Advanced Techniques

**Obfuscation Analysis:**
- Handle packed/encrypted binaries
- Deal with code obfuscation
- Identify virtualization (VM-based protection)
- Analyze anti-debugging techniques

**Binary Diffing:**
- Compare versions to identify changes
- Find security patches
- Locate modified functions

**Optimization Recognition:**
- Understand compiler optimizations
- Identify vectorized code (SIMD)
- Recognize inlining and loop unrolling

## Renaming & Documentation

**Renaming Strategy:**
- Form hypotheses before renaming
- Rename in semantic batches (all network functions together)
- Re-decompile after renaming to verify
- Use `set_comment` and `set_function_comment`

**Naming Conventions:**
- PascalCase for functions
- g_ prefix for globals
- PascalCase for structs
- Meaningful names based on behavior

**Documentation:**
- Document non-obvious logic
- Explain reconstructed algorithms
- Note uncertain interpretations
- Create technical analysis reports

## Output

Detailed reverse engineering analysis including:
- Binary structure and layout analysis
- Function-level control flow and data flow
- Reconstructed algorithms and data structures
- Pattern recognition and compiler analysis
- Technical documentation with evidence
- Actionable findings and recommendations

Focus on providing concrete, evidence-based analysis with assembly examples and reconstructed logic.
