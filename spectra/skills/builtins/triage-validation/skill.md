---
name: triage-validation
description: Finding validation before writing any report — 7-Question Gate (all 7 questions), 4 pre-submission gates, always-rejected list, conditionally valid with chain table, CVSS 3.1 quick reference, severity decision guide, report title formula, 60-second pre-submit checklist. Use BEFORE writing any report. One wrong answer = kill the finding and move on. Saves N/A ratio.
---

# TRIAGE & VALIDATION

One wrong answer = STOP. Kill it. Move on.

> "N/A hurts your validity ratio. Informative is neutral. Only submit what passes all 7 questions."

---

## THE 7-QUESTION GATE

Ask IN ORDER. One wrong answer = STOP immediately.

---

### Q1: Can an attacker use this RIGHT NOW, step by step?

Complete this template:
```
1. Setup:   I need [own account / another user's ID / no account]
2. Request: [exact HTTP method, URL, headers, body — copy-paste ready]
3. Result:  I can [read / modify / delete] [exact data shown in response]
4. Impact:  The real-world consequence is [account takeover / PII read / money stolen]
5. Cost:    Time: [X minutes], Capital: [$0 / $X subscription required]
```

**If you CANNOT write step 2 as a real HTTP request → KILL IT.**

---

### Q2: Is the impact on the program's accepted impact list?

Go to the program page. Find "Vulnerability Types" or "Out of Scope."

Common tiers:
- **Critical**: Any-user ATO without interaction, RCE, SQLi with data exfil, admin auth bypass
- **High**: Mass PII exfil, privilege escalation, internal SSRF with data, stored XSS all users
- **Medium**: IDOR on specific user non-critical data, XSS on sensitive page requiring click
- **Low**: Non-sensitive info disclosure, clickjacking with PoC

**If your bug maps to a listed exclusion → KILL IT.**

---

### Q3: Is the root cause in an in-scope asset?

Confirm:
- Vulnerable domain is on the in-scope list (not `*.internal.target.com`)
- It's a production asset (not staging/dev unless explicitly in scope)
- It's not a third-party service the company just uses (not Stripe, Salesforce, Google Auth)

**If out-of-scope → KILL IT.**

---

### Q4: Does it require privileged access that an attacker can't realistically get?

- "Admin can do X" = centralization risk = **KILL IT** (on 99% of programs)
- "Non-admin can do X that only admin should do" = valid
- "Requires physical access / MFA device" = usually invalid
- "Requires compromised victim account to work" = questionable, low severity at best

---

### Q5: Is this already known or accepted behavior?

Search:
1. Program's HackerOne/Bugcrowd disclosed reports: Ctrl+F endpoint name + bug class
2. GitHub issues on target repo: `is:issue label:security ENDPOINT_NAME`
3. Changelog/CHANGELOG.md — does it mention this behavior?
4. API docs / design docs — is it documented as intended?

**If acknowledged/design decision → KILL IT.**

---

### Q6: Can you prove impact beyond "technically possible"?

- XSS → show actual cookie theft or session hijack, not just `alert(1)` or `alert(document.domain)`
- SSRF → hit an internal endpoint that returns data, not just DNS ping
- SQLi → show actual data exfil from a real table, not just error message
- IDOR → show actual other-user's data in response, not just a 200 status code

**If you can only show "technically possible" → DOWNGRADE severity, not kill.**

---

### Q7: Is this a known-invalid bug class?

Check the NEVER SUBMIT list below. If it's on this list without a chain → **KILL IT.**

---

## 4 PRE-SUBMISSION GATES

Run in sequence. ALL 4 must PASS.

### Gate 0: Reality Check (30 seconds)
```
[ ] Bug is REAL — confirmed with actual HTTP requests, not code reading alone
[ ] Bug is IN SCOPE — checked program scope page explicitly
[ ] Reproducible from scratch — can reproduce starting from fresh session
[ ] Evidence ready — screenshot, response body, or video
```

### Gate 1: Impact Validation (2 minutes)
```
[ ] Can answer: "What can attacker DO that they couldn't before?"
[ ] Answer is more than "see non-sensitive data" (unless program pays for info disclosure)
[ ] Real victim: another user's data, company's data, financial loss
[ ] Not relying on victim doing something unlikely
```

### Gate 2: Deduplication Check (5 minutes)
```
[ ] Searched HackerOne Hacktivity for this program + similar bug title/endpoint
[ ] Searched GitHub issues for target repo
[ ] Read most recent 5 disclosed reports for this program
[ ] Not a "known issue" in their changelog or public docs
[ ] Google: "TARGET_NAME ENDPOINT_NAME bug bounty"
```

### Gate 3: Report Quality (10 minutes)
```
[ ] Title: [Bug Class] in [Endpoint] allows [actor] to [impact]
[ ] Steps to Reproduce: copy-pasteable HTTP request
[ ] Evidence: screenshot/video of actual impact (not just 200 status)
[ ] Severity: matches CVSS 3.1 score AND program's severity definitions
[ ] Remediation: 1-2 sentences of concrete fix
[ ] NEVER used "could potentially" or "may allow"
```

---

## NEVER SUBMIT LIST

Submitting these destroys your validity ratio.

```
Missing CSP / HSTS / security headers
Missing SPF / DKIM / DMARC
GraphQL introspection alone (no auth bypass, no IDOR demonstrated)
Banner / version disclosure without working CVE exploit
Clickjacking on non-sensitive pages (no sensitive action PoC)
Tabnabbing
CSV injection (no actual code execution shown)
CORS wildcard (*) without credential exfil proof of concept
Logout CSRF
Self-XSS (only exploits own account)
Open redirect alone (no ATO or OAuth theft chain)
OAuth client_secret in mobile app (known, expected)
SSRF DNS callback only (no internal service access or data)
Host header injection alone (no password reset poisoning PoC)
Rate limit on non-critical forms (search, contact, login with Cloudflare)
Session not invalidated on logout
Concurrent sessions
Internal IP in error message
Mixed content
SSL weak ciphers
Missing HttpOnly / Secure cookie flags alone
Broken external links
Autocomplete on password fields
Pre-account takeover (usually — very specific conditions required)
```

---

## CONDITIONALLY VALID — CHAIN REQUIRED

Build the chain first, prove it works end to end, THEN report.

| Standalone Finding | Chain Required | Valid Result |
|---|---|---|
| Open redirect | + OAuth redirect_uri → auth code theft | ATO (Critical) |
| Clickjacking | + sensitive action + working PoC | Medium |
| CORS wildcard | + credentialed request exfils user PII | High |
| CSRF | + sensitive action (transfer funds, change email, delete account) | High |
| Rate limit bypass | + OTP/reset token brute force succeeds | Medium/High |
| SSRF DNS-only | + internal service access + data returned | Medium |
| Host header injection | + password reset email uses injected host | High |
| Prompt injection | + reads other user's data (IDOR) | High |
| S3 bucket listing | + JS bundles contain API keys or OAuth secrets | Medium/High |
| Self-XSS | + CSRF to trigger it on victim without their knowledge | Medium |
| Subdomain takeover | + OAuth redirect_uri registered at that subdomain | Critical |
| GraphQL introspection | + auth bypass mutation or IDOR on node() | High |

---

## CVSS 3.1 QUICK REFERENCE

### Common Score Examples

| Finding | Score | Severity | Vector |
|---|---|---|---|
| IDOR read PII, any user, auth required | 6.5 | Medium | AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N |
| IDOR write/delete, any user | 7.5 | High | AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N |
| Auth bypass → admin panel | 9.8 | Critical | AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H |
| Stored XSS → cookie theft, stored | 8.8 | High | AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:L/A:N |
| SQLi → full DB dump | 8.6 | High | AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N |
| SSRF → cloud metadata | 9.1 | Critical | AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:N |
| Race → double spend | 7.5 | High | AV:N/AC:H/PR:L/UI:N/S:U/C:H/I:H/A:N |
| GraphQL auth bypass | 8.7 | High | AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N |
| JWT none algorithm | 9.1 | Critical | AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H |

### Metric Quick Guide

| What you have | Metric | Value |
|---|---|---|
| Exploitable over internet | AV | Network (N) |
| No special timing or race | AC | Low (L) |
| Free account needed | PR | Low (L) |
| No login needed | PR | None (N) |
| Admin needed | PR | High (H) |
| No victim action | UI | None (N) |
| Victim must click | UI | Required (R) |
| Reads all data | C | High (H) |
| Reads some data | C | Low (L) |
| Modifies all data | I | High (H) |
| Crashes service | A | High (H) |
| Affects only app | S | Unchanged (U) |
| Affects browser/OS/cloud | S | Changed (C) |

---

## KILL FAST RULES

The goal is to QUICKLY disqualify bad leads so you hunt real bugs:

1. **5-minute rule**: If you can't fill in Q1's template in 5 minutes → move on
2. **Precondition count**: More than 2 preconditions simultaneously required → kill it
3. **Impact test**: "What does attacker walk away with?" — if nothing tangible → kill it
4. **Admin bypass**: "Admin can do X" is NEVER a bug → kill it immediately
5. **Design doc test**: If it's documented behavior → kill it immediately
6. **Rabbit hole signal**: 30+ min on Q6 with no reproducible PoC → kill it

---

## ANTI-PATTERNS THAT LOSE MONEY

```
Writing a report before confirming the bug exists (most common)
Submitting theoretical impact without proof
"The API returns more fields than necessary" (sensitivity matters — is it actually sensitive?)
Chaining A+B into one report when they're separate bugs (two separate payouts)
Reporting B saying "similar to A in my other report" — fresh Gate 0 for every bug
Overclaiming severity — triagers trust you less next time
Under-describing impact — triager doesn't understand why it matters
```

---

# ZERO-DAY TRIAGE — Novel Vulnerability Validation

> **For vulnerabilities that don't fit known patterns**: Extra validation to prove this is genuinely novel and exploitable.

## Novel Vulnerability Gate Questions

### Q0: Is This Genuinely Novel?

A finding is NOVEL if at least one is true:

```
[ ] Requires combining 2+ features (feature interaction bug)
[ ] Exploits a design contradiction (doc vs implementation)
[ ] Uses untested code path (error handling, corner case)
[ ] Requires protocol/state violation (wrong sequence, parallel requests)
[ ] Found via source code taint analysis (not pattern matching)
[ ] Exploits race condition/TOCTOU (timing-dependent)
[ ] Requires POP chain or deserialization abuse
[ ] Uses memory corruption/type confusion (low-level)
```

**If NONE of these apply → Use standard N-Day validation above.**

---

### Q1-Novel: Can You Prove the Chain Works End-to-End?

For novel vulnerabilities, prove EVERY link in the chain:

```
[ ] Link A: Feature A exists and is accessible
[ ] Link B: Feature B exists and is accessible
[ ] Connection: A's output can reach B's input
[ ] Exploit: Attacker can control data flow A → B
[ ] Impact: Result achieves [RCE/ATO/PII exfil/financial loss]
```

**Example: Export → Import Privilege Escalation**
```
[✓] Export feature exists: /api/export (confirmed working)
[✓] Import feature exists: /api/import (confirmed working)
[✓] Connection: Export output format matches Import input format
[✓] Exploit: Export → Edit (add admin:true) → Import succeeds
[✓] Impact: Imported user becomes admin → ATO achieved
```

---

### Q2-Novel: Did You Check This Isn't Known Architecture?

Novel vulnerabilities often look like architecture decisions. Verify:

```
[ ] Not documented in architecture/decision docs (ADR)
[ ] Not mentioned in SECURITY.md or known issues
[ ] Not mentioned in GitHub issues as "intended behavior"
[ ] Not acknowledged in changelog/commit messages
[ ] Not a documented workaround for another limitation
```

**If documented as architecture → Kill it.**

---

### Q3-Novel: Is the Exploit Reproducible by Triager?

For complex novel vulnerabilities, provide:

```
[ ] Working PoC script (Python/Bash/PHP) in poc/ directory
[ ] Clear setup steps (environment, dependencies)
[ ] Expected output shown (what success looks like)
[ ] Idempotent test (can run multiple times, same result)
[ ] No external dependencies besides standard tools
```

---

### Q4-Novel: What Makes This Different from Known Vulns?

Explicitly state why scanners/checklists miss this:

```
This is novel because:
[ ] Requires combining [Feature A] + [Feature B] (not tested together)
[ ] Exploits [design contradiction] between docs and implementation
[ ] Uses [untested code path]: [error handler/race condition/corner case]
[ ] Found via [source code taint analysis] (no scanner pattern exists)
[ ] Requires [protocol violation]: [wrong state/sequence/parallel]
[ ] Uses [POP chain/deserialization] (context-dependent exploitation)
```

---

## Novel Vulnerability Severity Guide

| Novel Finding Type | Typical Severity | Why |
|---|---|---|
| Feature interaction → ATO | Critical | 2+ features, unexpected path |
| Design contradiction → Data leak | High | Doc says X, code does Y |
| Race condition → Double spend | High | Timing-dependent, financial |
| POP chain → RCE | Critical | Deserialization abuse |
| TOCTOU → Privilege esc. | High | Check-then-use gap |
| Memory corruption → RCE | Critical | Low-level exploitation |
| Type confusion → Auth bypass | High | Input validation failure |

---

## Novel Vulnerability Report Template

```
## Summary

A [novel design flaw / feature interaction bug / POP chain] in [component]
allows [attacker role] to achieve [impact] by [exploit method].

## Why This Is Novel

This vulnerability is not covered by existing scanners/checklists because:
1. [Requirement 1]: Requires combining [Feature A] + [Feature B]
2. [Requirement 2]: Exploits [specific design contradiction]
3. [Requirement 3]: Involves [unusual code path]

## Root Cause

[Explain the design contradiction or feature interaction]

## Steps to Reproduce

1. [Setup step]
2. [Link A operation]
3. [Connection between A and B]
4. [Link B operation]
5. [Impact achieved]

## Supporting Material

[PoC script in poc/ directory]
[Video demonstration]

## Impact

- [Concrete business impact]
- [Quantification: affects N users / $X value]

## Severity Assessment

CVSS 3.1 Score: X.X ([Severity])
[Justification for score]
```

---

## Novel Vulnerability Kill Signals

Even for 0-days, kill these immediately:

```
[ ] "Architecture allows this" → Kill (unless you can prove it's unintended)
[ ] Requires social engineering → Kill (unless extremely convincing)
[ ] "Would work IF they add feature X" → Kill (must work NOW)
[ ] Requires unrealistic timing (<1ms race) → Kill
[ ] Requires insider access → Kill
[ ] "Testing environment only" → Kill (must work in production)
[ ] Proof requires triager to write custom code → Provide script instead
```

---

## Novel vs N-Day Decision Flow

```
                    ┌──────────────────┐
                    │  Can you find     │
                    │  this in a        │
                    │  checklist?       │
                    └────────┬─────────┘
                             │
              ┌──────────────┴───────────────┐
              │ YES                          │ NO
              ▼                              ▼
     ┌──────────────────┐          ┌──────────────────┐
     │ N-Day Validation │          │ 0-Day Validation │
     │ (use 7-Question  │          │ (use Q0-Q4-Novel) │
     │  Gate above)     │          └──────────────────┘
     └──────────────────┘                     │
                                            ▼
                                  ┌──────────────────┐
                                  │  Can scanners    │
                                  │  detect this?    │
                                  └────────┬─────────┘
                                           │
                             ┌─────────────┴─────────────┐
                             │ YES                │ NO
                             ▼                     ▼
                    ┌──────────────┐    ┌──────────────────┐
                    │ Kill - not   │    │ Novel confirmed │
                    │ truly novel  │    │ → Proceed with │
                    └──────────────┘    │ Q1-Q4-Novel      │
                                         └──────────────────┘
```
