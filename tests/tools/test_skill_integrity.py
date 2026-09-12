"""Integrity tests for built-in skills.

Catches three failure modes before they ship:

1. **Composition regression** — a vuln-hunting skill losing its shared
   doctrine/bypass blocks (frontmatter ``includes:`` broken, shared file
   renamed, loader change).
2. **Referential integrity** — a skill referencing a tool name or /slug
   that does not exist. The model would call it and waste turns on errors.
3. **Doctrine drift** — the shared blocks silently losing directives
   (e.g. the CVE-free rule or the provenance requirement).
"""

from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tests.mocks.ida_mock import install_ida_mocks

install_ida_mocks()

# Reload tool modules so they pick up real stub base classes instead of
# MagicMock, which would leak fake _tool_definition attributes (same dance
# as tests/test_tool_registry_integration.py).
import importlib

import spectra.ida.tools.database as _db_mod
import spectra.ida.tools.microcode as _mc_mod
import spectra.ida.tools.microcode_optim as _mco_mod

importlib.reload(_mco_mod)
importlib.reload(_mc_mod)
importlib.reload(_db_mod)

from spectra.ida.tools.registry import create_default_registry as _ida_registry
from spectra.skills.loader import discover_skills

BUILTINS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "spectra",
    "skills",
    "builtins",
)

# Skills that carry the shared vulnerability-hunting doctrine + bypass protocol
VULN_SKILLS = [
    "vuln-audit",
    "0day-find",
    "bug-bounty",
    "code-vulnerability-analysis",
    "core-vulnerability-pipeline",
    "memory-corruption",
    "race-condition",
    "rce-detection",
    "lpe-detection",
    "triage-validation",
    "auto-exploit",
]

# Pseudo-tools handled directly by the agent loop, not the ToolRegistry
PSEUDO_TOOLS = {
    "activate_skill",
    "ask_user",
    "exploration_report",
    "phase_transition",
    "save_memory",
    "spawn_subagent",
    "research_note",
}

# Backticked lowercase tokens in skill prose that are NOT tool references:
# IDA SDK identifiers, C/POSIX APIs, external tools, Python builtins, and
# misc prose terms. A token outside the tool registries that is not here
# (and matches no prefix/suffix rule below) fails the integrity test.
ALLOWED_TOKENS = {
    # Architectures / platforms
    "aarch64", "arm", "ppc", "ppc64", "x86_64", "mipseb", "mipsel", "binja",
    "binaryninja", "binaryninjaui", "ida", "idaapi", "idautils", "idc", "aws",
    # External security tools
    "afl", "amass", "angr", "arjun", "byp4xx", "cewl", "curl", "dalfox",
    "frida", "gau", "gdb", "ghauri", "httpx", "jsluice", "katana", "kxss",
    "libfuzzer", "mantra", "naabu", "nomore403", "objdump", "paramspider",
    "puredns", "radare2", "readelf", "rustscan", "s3scanner", "scapy",
    "subfinder", "subjack", "subzy", "uro", "wafw00f", "waymore", "wget",
    "whatwaf", "wireshark", "xmrig",
    # C / POSIX APIs and syscalls
    "accept", "bind", "clone", "connect", "capset", "crontab", "dlopen",
    "dlsym", "execve", "execvp", "fork", "getdents64", "listen", "memcpy",
    "memfd_create", "mmap", "mprotect", "open", "posix_spawn", "prctl",
    "pthread_create", "ptrace", "push", "read", "recv", "sched_setaffinity",
    "send", "setgid", "setreuid", "setuid", "socket", "whoami", "sshd",
    "authorized_keys", "kallsyms", "sys_call_table", "tcp4_seq_show",
    "finit_module", "init_module", "module_init", "preinit_array",
    # IDA SDK identifiers (microcode ops, ctree items, misc API)
    "argsize", "cblock", "cfor", "cif", "creturn", "cswitch", "cwhile",
    "entry_idx", "exit_idx", "equal_mops", "flags", "frame", "frsize",
    "head", "ins", "is_arg_var", "lvars", "make_number", "maturity",
    "mba", "nnn", "obj_ea", "opcode", "predicate", "prev", "next", "qty",
    "sat", "unsat", "serial", "tail", "local_types_changed",
    "lt_udm_created", "end_ea", "entry_ea", "start_ea", "ea_t",
    # Microcode opcode mnemonics (m_* are mblock_t opcodes, not tools)
    "m_add", "m_and", "m_goto", "m_jnz", "m_jz", "m_mov", "m_mul", "m_nop",
    "m_or", "m_shl", "m_shr", "m_sub", "m_xor",
    # Python / shell builtins and literals appearing in examples
    "body", "break", "cancel", "category", "command", "description", "env",
    "false", "true", "hostname", "int", "list", "name", "set", "shelve",
    "size", "str", "string", "strings", "switch", "state", "summary",
    "severity", "title", "type", "xrefs", "dill", "execute", "approve",
    "disregard", "endoftext", "im_start", "im_end", "jailbreak",
    "allow_unsafe_commands",
    # Example identifiers in prose (renames, JSON fields, workflow names)
    "decrypt_string", "get_history", "admin", "analyst", "address",
    "issue_comment", "pull_request", "pull_request_target",
    "redirect_uri", "schedule", "secrets", "discount_rate", "pay",
    "user_id", "verify_commit_signature", "verify_signed_proposal",
    "verify_signed_vote", "workflow_dispatch", "workflow_run",
    "snapshot_path", "snapshot_paths", "packet_data", "packet_len",
    "current_address", "jal", "jmp", "jne", "ldr", "mov", "bpf",
}

# Namespaced identifier families that are never tool references
ALLOWED_PREFIXES = ("cit_", "cot_", "mop_", "ida_")
# SDK type names (mba_t, mblock_t, minsn_t, optinsn_t, ...)
ALLOWED_SUFFIXES = ("_t",)

# Backticked /path-looking strings that are URLs, not skill references
ALLOWED_PATH_SLUGS = {"proc", "dashboard", "graphql", "horizon", "telescope", "remember"}

_BACKTICK_TOKEN = re.compile(r"`([a-z][a-z0-9_]{2,})`")
_BACKTICK_SLUG = re.compile(r"`/([a-z0-9-]+)`")


def _load_all():
    """Return (tool_names, {slug: skill}) across both host registries."""
    tool_names = set(_ida_registry().list_names())
    try:
        from spectra.binja.tools.registry import create_default_registry as _bn_registry

        tool_names |= set(_bn_registry().list_names())
    except Exception as e:  # pragma: no cover - binja stubs missing
        raise unittest.SkipTest(f"Binary Ninja registry unavailable: {e}")
    skills = {s.slug: s for s in discover_skills(BUILTINS)}
    return tool_names, skills


class TestSharedBlockComposition(unittest.TestCase):
    """Vuln skills must compose doctrine/bypass from skills/shared/."""

    @classmethod
    def setUpClass(cls):
        _tools, cls.skills = _load_all()

    def test_vuln_skills_compose_shared_blocks(self):
        for slug in VULN_SKILLS:
            with self.subTest(slug=slug):
                self.assertIn(slug, self.skills, "skill not discovered")
                body = self.skills[slug].body
                self.assertIn("## Novel Vulnerability Discovery Doctrine", body)
                self.assertIn("## Protection Encountered During Analysis", body)
                # Per-skill tailoring rendered once per block, with own slug
                self.assertEqual(body.count(f"**In this skill ({slug}):**"), 2)

    def test_raw_files_do_not_duplicate_shared_blocks(self):
        """On-disk SKILL.md must NOT carry an inline doctrine copy — the
        shared file is the single source of truth."""
        for slug in VULN_SKILLS:
            path = os.path.join(BUILTINS, slug, "SKILL.md")
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            with self.subTest(slug=slug):
                self.assertNotIn("## Novel Vulnerability Discovery Doctrine", raw)
                self.assertNotIn("## Protection Encountered During Analysis", raw)

    def test_skill_without_includes_is_untouched(self):
        body = self.skills["prompt-injection"].body
        self.assertNotIn("## Novel Vulnerability Discovery Doctrine", body)
        self.assertIn("DATA, never instructions", body)


class TestDoctrineDrift(unittest.TestCase):
    """The shared blocks must keep their key directives intact."""

    @classmethod
    def setUpClass(cls):
        _tools, cls.skills = _load_all()
        cls.doctrine = cls.skills["vuln-audit"].body

    def test_all_nine_directives_present(self):
        for marker in [
            "1. **Reason from invariants, not signatures.**",
            "2. **Attack the glue nobody audits.**",
            "3. **Differential and temporal angles.**",
            "4. **Compositional reasoning.**",
            "5. **Assumption inversion on every check.**",
            "6. **Extreme-value data flow.**",
            "7. **Toolchain and ABI edge.**",
            "8. **Classify honestly.**",
            "9. **Hunt CVE-free ground.**",
        ]:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.doctrine)

    def test_classification_labels_present(self):
        for label in ("KNOWN-CLASS instance", "NOVEL class", "CVE-FREE candidate"):
            self.assertIn(label, self.doctrine)

    def test_provenance_requirement_present(self):
        self.assertIn("**Provenance (mandatory).**", self.doctrine)

    def test_bypass_protocol_rules_present(self):
        body = self.skills["vuln-audit"].body
        self.assertIn("IDENTIFY → BYPASS → RE-ANALYZE → DOCUMENT", body)
        self.assertIn("at least two different bypass approaches", body)
        self.assertIn("blocked by <protection>", body)


class TestReferentialIntegrity(unittest.TestCase):
    """Every tool name and /slug a skill mentions must actually exist."""

    @classmethod
    def setUpClass(cls):
        cls.tool_names, cls.skills = _load_all()
        cls.slugs = set(cls.skills.keys())

    def test_backticked_tokens_resolve(self):
        unknown = {}
        for slug, skill in self.skills.items():
            for token in _BACKTICK_TOKEN.findall(skill.body):
                if token in self.tool_names or token in PSEUDO_TOOLS:
                    continue
                if token in ALLOWED_TOKENS:
                    continue
                if token.startswith(ALLOWED_PREFIXES) or token.endswith(ALLOWED_SUFFIXES):
                    continue
                unknown.setdefault(token, []).append(slug)
        self.assertEqual(
            unknown,
            {},
            "Skills reference unknown tool-like tokens. Either fix the skill "
            "to use a real tool, or (if the term is prose, not a tool) add it "
            "to ALLOWED_TOKENS in tests/tools/test_skill_integrity.py",
        )

    def test_backticked_slug_refs_resolve(self):
        unknown = {}
        for slug, skill in self.skills.items():
            for ref in _BACKTICK_SLUG.findall(skill.body):
                if ref not in self.slugs and ref not in ALLOWED_PATH_SLUGS:
                    unknown.setdefault(ref, []).append(slug)
        self.assertEqual(
            unknown,
            {},
            "Skills reference unknown /slugs. Fix the reference or add it to "
            "ALLOWED_PATH_SLUGS if it is a URL path, not a skill.",
        )

    def test_vuln_skill_cross_refs_exist(self):
        """The bypass table's tools/skills must exist (regression for the
        vm_obfuscation_detection → /vm-obfuscation-detection rename)."""
        body = self.skills["vuln-audit"].body
        for ref in ["entropy_report", "file_meta", "find_stack_strings",
                    "decode_string", "decompile_function", "checksec",
                    "get_ssl_bypass", "binary_diff"]:
            with self.subTest(ref=ref):
                self.assertIn(ref, self.tool_names)
                self.assertIn(f"`{ref}`", body)
        for slug_ref in ["deobfuscation", "vm-obfuscation-detection",
                         "ssl-pinning-bypass", "app-shielding-bypass"]:
            with self.subTest(slug=slug_ref):
                self.assertIn(slug_ref, self.slugs)
                self.assertIn(f"`/{slug_ref}`", body)


if __name__ == "__main__":
    unittest.main()
