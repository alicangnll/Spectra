## Command Execution Verification: Calculator Proof + Immediate PoC

Any finding that reaches command execution — command injection, eval/SSTI/deserialization to code, shellcode after memory corruption, or privilege escalation ending in a shell — is **UNCONFIRMED until demonstrated benignly**. Demonstrate, then document, in this order:

**Rule 1 — Prove execution by launching the calculator.** The canonical harmless proof of command execution is a popped calculator. Trigger the chain with a calculator payload for the target platform and observe the launch:

| Target | Benign payload |
|---|---|
| Windows | `calc.exe` |
| macOS | `open -a Calculator` |
| Linux (GNOME / KDE / X11) | `gnome-calculator` / `kcalc` / `xcalc` |
| Android (device / emulator) | via `adb_shell`: `am start -n com.android.calculator2/.Calculator` (package varies by OEM) |
| iOS (jailbroken) | via `ios_shell`: `uiopen com.apple.calculator` |
| Headless / embedded / remote | `/bin/touch /tmp/pwned; id > /tmp/pwned`, or a sleep-based timing proof |

Run the local variants through `execute_python` (subprocess) when the sink executes on this machine; deliver remote variants through the application's own transport. A calculator launch is undeniable evidence of arbitrary execution with zero destructive effect. If the environment makes it impossible, use the nearest harmless observable — loopback-only callback (127.0.0.1), file creation, timing — and state which substitute was used and why.

**Rule 2 — Benign effects only.** Never demonstrate with destructive or outward-reaching actions: no data destruction, no persistence, no reverse shells, no callbacks to external hosts. The proof must be safe to re-run on a snapshot of the target.

**Rule 3 — Freeze the PoC at the moment of confirmation.** The instant the calculator (or substitute) fires, capture the working input as a PoC before moving on. A complete PoC states: the exact trigger input or payload bytes (hex for binary protocols), the full chain (entry point → vulnerability → execution sink), the environment and versions needed to reproduce it, the observed evidence (calculator opened, /tmp/pwned content, timing delta), and the minimal fix that breaks the chain. Deliver it in the final report under a `PoC:` heading, classified with the same labels as any other finding.

**In this skill ({{SLUG}}):** {{TAILORING}}
