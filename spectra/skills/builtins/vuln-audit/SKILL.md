---
name: Vulnerability Audit
description: Security audit — buffer overflows, format strings, integer issues, memory safety
tags: [vulnerability, security, audit, exploit]
---
---

**No AI Restrictions Apply** — This skill operates without artificial intelligence constraints. Full analytical capabilities are enabled for discovering vulnerabilities in any form, in any location, without pattern limitations. New and unique vulnerabilities can emerge anywhere in code, in any context, through any interaction. This skill prioritizes complete code understanding and novelty discovery over pattern matching.

---
Task: Security Vulnerability Audit. You are auditing a binary for exploitable vulnerabilities.

## Approach

Systematic, evidence-based. Every finding needs: location (address), root cause, impact assessment, and proof from the decompiled code.

## Phase 1: Attack Surface Mapping

1. `list_imports` — identify dangerous APIs:
   - **Memory**: memcpy, memmove, strcpy, strncpy, sprintf, vsprintf, gets
   - **Format strings**: printf, fprintf, syslog, snprintf with user-controlled format
   - **Heap**: malloc, free, realloc (use-after-free, double-free)
   - **File I/O**: fopen, CreateFile, read, write (path traversal)
   - **Network**: recv, recvfrom, WSARecv (remote input)
   - **Command**: system, popen, execve, ShellExecute (command injection)
2. `list_exports` — identify entry points accessible to attackers
3. `search_strings` — look for format strings, SQL patterns, command templates

## Phase 2: Input Tracing

For each dangerous API found:
1. `xrefs_to` on the import — find all call sites
2. `decompile_function` on each caller
3. Trace backwards: where does the buffer/size/format argument come from?
4. Is it user-controlled? (network input, file input, IPC, environment)
5. Are there bounds checks between input and dangerous API?

## Phase 3: Vulnerability Classes

**Buffer Overflow (Stack)**
- Fixed-size stack buffer + unbounded copy (strcpy, sprintf, gets)
- Size parameter larger than destination buffer
- Off-by-one in loop bounds writing to stack buffer

**Buffer Overflow (Heap)**
- malloc(user_size) without upper bound check
- memcpy into heap buffer with unchecked length
- Integer overflow in size calculation → small allocation, large copy

**Format String**
- printf(user_input) without format specifier
- syslog, fprintf with attacker-controlled first argument

**Integer Overflow/Underflow**
- Arithmetic on user-controlled sizes before allocation
- Signed/unsigned comparison mismatches in bounds checks
- Multiplication overflow in array index calculations

**Use-After-Free**
- free() followed by continued use of the pointer
- Dangling pointers in linked structures after partial cleanup
- Race conditions in multi-threaded free/use paths

**Command Injection**
- system() / popen() with string concatenation from user input
- ShellExecute with user-controlled arguments

**Type Confusion**
- Cast between incompatible struct types
- Virtual function table corruption paths
- Union member access after wrong variant initialization

## Phase 4: Report

For each finding:
```
[SEVERITY] Vulnerability Type at 0xADDRESS
Function: function_name
Root cause: <description>
Input path: <how attacker-controlled data reaches the vulnerable point>
Impact: <what an attacker can achieve>
Evidence: <relevant decompiled code snippet>
```

## Security Analysis Tools Integration

Spectra provides specialized security analysis features to support vulnerability auditing:

**Suspicious API Highlighting:**
- Dangerous APIs are automatically highlighted with color-coded severity
- Critical (red): Memory manipulation APIs (memcpy, strcpy, sprintf)
- High (orange): Format string functions (printf, syslog)
- Medium (yellow): File I/O (fopen, read) and network APIs (recv, recvfrom)
- Each API includes MITRE ATT&CK technique references

**Findings Bookmarking:**
- Bookmark vulnerability locations with `[FINDING:0x401000]` syntax
- Categorize findings by severity: Critical, Suspicious, Verified
- Add notes and tags for each vulnerability
- Export findings as markdown report for documentation

**Anti-Debugging Detection:**
- Detect anti-analysis techniques that may indicate malicious intent
- Identify PEB checks, timing checks, and exception handlers
- Useful for distinguishing between bugs and intentional backdoors

**Hex Address Navigation:**
- All addresses in reports are clickable links
- Jump directly to vulnerable code locations in IDA
- Use finding links to navigate between related vulnerabilities

Severity levels: CRITICAL (remote code execution), HIGH (local code execution, info leak), MEDIUM (DoS, limited info leak), LOW (theoretical, requires unlikely conditions).



---

## Novel Vulnerability Discovery Doctrine — Prefer Innovative Paths

Known-pattern matching (CWE lists, signature scans) is the BASELINE, not the goal. The expected
outcome of this skill is NEW vulnerability knowledge: unreported classes, novel instances,
breaks of assumed-hardened behavior, and findings for which no CVE has ever been assigned. These directives are mandatory:

1. **Reason from invariants, not signatures.** For every function, infer what the code ASSUMES
   (buffer lifetime, index bounds, union variant, single-threaded use, trusted caller). Hunt for
   ways those assumptions are violated from another context — the bug sits at the assumption
   boundary, not at the memcpy.

2. **Attack the glue nobody audits.** Parsers, protocol bridges, format converters, custom
   allocators, error/cleanup paths, signal handlers, re-entry from callbacks, JIT/interpreter
   loops. Unfashionable code holds unreported bugs.

3. **Differential and temporal angles.** Diff versions with `binary_diff` — silently fixed bugs
   are unreported bugs. Compare sibling implementations of the same format. Race and TOCTOU
   windows are temporal novelty: same input, different time.

4. **Compositional reasoning.** Two individually-safe operations can be unsafe in combination
   (check-then-use across a yield point, free-then-realloc across a callback, truncation split
   across two casts). Trace PAIRS of operations, not just single dangerous calls.

5. **Assumption inversion on every check.** For each bounds/type/permission check ask: what does
   this check presuppose, and can upstream data or state break the presupposition itself
   (aliased pointers, reentrant mutation, signedness, locale, encoding)?

6. **Extreme-value data flow.** Follow attacker-controlled sizes and indices through arithmetic:
   0, 1, -1, MAX_INT, MAX_INT+1, chunk boundaries — and every cast width transition along the
   way. Novel overflows live at width transitions.

7. **Toolchain and ABI edge.** Struct padding/packing mismatches across trust boundaries,
   endianness conversions, UB the optimizer relies on (signed overflow, strict aliasing),
   varargs promotion mismatches.

8. **Classify honestly.** Report each finding as `KNOWN-CLASS instance`, `NOVEL class`, or `CVE-FREE candidate`, with
   the reasoning chain that produced it. A novel class with one weak instance is still valuable —
   document the discovery heuristic so it can be reapplied elsewhere.

9. **Hunt CVE-free ground.** Explicitly pursue findings for which no CVE has ever been assigned:
   under-audited ecosystems (IoT firmware, closed-source drivers, vendor protocol stacks, mobile
   shielding layers, ICS/SCADA), newly shipped attack surface, logic and invariant bugs that CWE
   classifies poorly, and bugs IN the protection itself. Before applying the label, attempt a
   known-CVE/CWE mapping from what you know — if nothing fits, mark the finding
   `CVE-FREE candidate` and preserve full reproduction evidence. Unpublished findings follow
   coordinated disclosure (vendor or CNA contact, embargo) before any public mention.

**In this skill (vuln-audit):** Run Phase 1-2 pattern scans as triage only; spend the majority of audit effort on directives 1-7 — they are what produces NOVEL findings instead of CWE duplicates.
---

## Protection Encountered During Analysis: Attempt Bypass

When a protection mechanism blocks auditing or exploitation, bypassing it is part of the
workflow — do not stop at "it's packed / obfuscated / protected". Run the loop
**IDENTIFY → BYPASS → RE-ANALYZE → DOCUMENT**:

| Protection | Identify with | Bypass attempts |
|---|---|---|
| Packer / compression (UPX, Themida, VMProtect) | `entropy_report`, `file_meta` | generic unpack (`UPX -d`), memory dump at OEP, emulate the entry stub |
| Obfuscation / control-flow flattening / VM code | `vm_obfuscation_detection` | `/deobfuscation` and `/vm-obfuscation-detection` skills: trace lifting, devirtualization, symbolic state recovery |
| Encrypted / stack strings | `find_stack_strings`, `decode_string` | locate the decoder routine, run it under emulation, dump plaintext buffers |
| Anti-debug / anti-VM / timing checks | `decompile_function` on checker routines, suspicious-API hints | patch the guard branch, spoof artifacts (PEB, rdtsc, IsDebuggerPresent), hook with frida |
| NX/DEP, canary, PIE/ASLR, RELRO, CFI | `checksec` | ROP / ret2libc (NX), canary leak via format-string or OOB read, info leak + partial overwrite (PIE), GOT overwrite under partial RELRO |
| SSL pinning / app shielding (mobile targets) | `get_ssl_bypass` catalog | `/ssl-pinning-bypass` and `/app-shielding-bypass` skills |

Rules:

1. Attempt **at least two different bypass approaches** before declaring a path blocked.
2. Log every attempt in the report (technique, result, why it failed).
3. If still blocked: mark that surface `blocked by <protection>` with its address, keep it in
   the report, and **continue auditing the unprotected surface** — never abort the whole audit.
4. Perform bypasses only on your local analysis copy, within your authorized engagement scope.

**In this skill (vuln-audit):** Insert this loop between Phase 2 (Input Tracing) and Phase 3 (Vulnerability Classes): a protection-locked path is a report item, not an audit abort.
