## Protection Encountered During Analysis: Attempt Bypass

When a protection mechanism blocks auditing or exploitation, bypassing it is part of the
workflow — do not stop at "it's packed / obfuscated / protected". Run the loop
**IDENTIFY → BYPASS → RE-ANALYZE → DOCUMENT**:

| Protection | Identify with | Bypass attempts |
|---|---|---|
| Packer / compression (UPX, Themida, VMProtect) | `entropy_report`, `file_meta` | generic unpack (`UPX -d`), memory dump at OEP, emulate the entry stub |
| Obfuscation / control-flow flattening / VM code | `/vm-obfuscation-detection` | `/deobfuscation` and `/vm-obfuscation-detection` skills: trace lifting, devirtualization, symbolic state recovery |
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

**In this skill ({{SLUG}}):** {{TAILORING}}
