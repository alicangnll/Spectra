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

**Provenance (mandatory).** Close every report with one line per key finding naming the directive
or heuristic that produced it, e.g. "provenance: heap overflow at parse_size — directive 6
extreme-value data flow". Without provenance lines the report is incomplete.

**In this skill ({{SLUG}}):** {{TAILORING}}
