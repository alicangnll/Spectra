"""Tests for the pure-Python ELF/PE/Mach-O parser (spectra/tools/binary_format.py).

The test binaries are synthesized with struct.pack — no real files, so the
suite runs identically on every platform.
"""

from __future__ import annotations

import struct
import unittest

from spectra.tools.binary_format import detect_format, parse_binary

# ═══════════════════════════════ ELF64 builder ═══════════════════════════


def build_elf64(
    e_type: int = 2,
    gnu_stack_flags: int = 0,   # 1 = executable stack (NX off)
    bind_now: bool = True,
    canary: bool = True,
    overlay: bool = False,
) -> bytes:
    INTERP_OFF, DYNSTR_OFF, DYNSYM_OFF, SYMTAB_OFF = 0x160, 0x180, 0x1A0, 0x1D0
    DYN_OFF, TEXT_OFF, SHSTRTAB_OFF, SHOFF = 0x200, 0x240, 0x248, 0x280

    if canary:
        dynstr = b"\x00libc.so.6\x00__stack_chk_fail\x00main\x00"
        libc_off, chk_off, main_off = 1, 11, 28
        dynsym = b"\x00" * 24 + struct.pack("<IBBHQQ", chk_off, 0x12, 0, 1, 0x1000, 16)
    else:
        dynstr = b"\x00libc.so.6\x00main\x00"
        libc_off, main_off = 1, 11
        dynsym = b"\x00" * 24
    symtab = b"\x00" * 24 + struct.pack("<IBBHQQ", main_off, 0x12, 0, 1, 0x1000, 42)

    dyn = struct.pack("<qQ", 1, libc_off) + struct.pack("<qQ", 5, DYNSTR_OFF)
    if bind_now:
        dyn += struct.pack("<qQ", 24, 0)
    dyn += struct.pack("<qQ", 0, 0)

    text = b"\x48\x31\xc0\xc3"
    shstrtab = b"\x00.text\x00.dynsym\x00.dynstr\x00.symtab\x00.dynamic\x00.interp\x00.shstrtab\x00"
    interp = b"/lib64/ld-linux-x86-64.so.2\x00"

    ehsize, phentsize, phnum, shentsize, shnum, shstrndx = 64, 56, 5, 64, 8, 7
    file_end = SHOFF + shnum * shentsize
    ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\x00" * 8
    ehdr = ident + struct.pack(
        "<HHIQQQIHHHHHH",
        e_type, 0x3E, 1, 0x1000, 0x40, SHOFF, 0,
        ehsize, phentsize, phnum, shentsize, shnum, shstrndx,
    )

    def ph(p_type, flags, off, vaddr, filesz):
        return struct.pack("<IIQQQQQQ", p_type, flags, off, vaddr, vaddr, filesz, filesz, 0x1000)

    phdrs = b"".join(
        [
            ph(1, 5, 0, 0, file_end),                       # PT_LOAD  R+X
            ph(2, 6, DYN_OFF, DYN_OFF, len(dyn)),           # PT_DYNAMIC
            ph(0x6474E552, 4, DYN_OFF, DYN_OFF, len(dyn)),  # PT_GNU_RELRO
            struct.pack("<IIQQQQQQ", 0x6474E551, gnu_stack_flags, 0, 0, 0, 0, 0, 0x10),
            ph(3, 4, INTERP_OFF, INTERP_OFF, len(interp)),  # PT_INTERP
        ]
    )

    def sh(name, s_type, flags, addr, off, size, link=0, info=0, entsize=0):
        return struct.pack("<IIQQQQIIQQ", name, s_type, flags, addr, off, size, link, info, 0, entsize)

    shdrs = b"".join(
        [
            sh(0, 0, 0, 0, 0, 0),
            sh(1, 1, 6, TEXT_OFF, TEXT_OFF, len(text)),
            sh(7, 11, 2, DYNSYM_OFF, DYNSYM_OFF, len(dynsym), 3, 1, 24),   # .dynsym
            sh(15, 3, 2, DYNSTR_OFF, DYNSTR_OFF, len(dynstr)),             # .dynstr
            sh(23, 2, 0, 0, SYMTAB_OFF, len(symtab), 3, 1, 24),            # .symtab
            sh(31, 6, 3, DYN_OFF, DYN_OFF, len(dyn), 0, 0, 16),            # .dynamic
            sh(40, 3, 2, INTERP_OFF, INTERP_OFF, len(interp)),             # .interp
            sh(48, 3, 0, 0, SHSTRTAB_OFF, len(shstrtab)),                  # .shstrtab
        ]
    )

    buf = bytearray(file_end)
    def put(off, blob):
        buf[off : off + len(blob)] = blob
    put(0, ehdr)
    put(0x40, phdrs)
    put(INTERP_OFF, interp)
    put(DYNSTR_OFF, dynstr)
    put(DYNSYM_OFF, dynsym)
    put(SYMTAB_OFF, symtab)
    put(DYN_OFF, dyn)
    put(TEXT_OFF, text)
    put(SHSTRTAB_OFF, shstrtab)
    put(SHOFF, shdrs)
    if overlay:
        return bytes(buf) + b"OVERLAY!"
    return bytes(buf)


# ═══════════════════════════════ PE64 builder ════════════════════════════


def build_pe64(
    dll_chars: int = 0x0160,  # HIGH_ENTROPY_VA | DYNAMIC_BASE | NX_COMPAT
    load_config: bool = True,
    overlay: bool = True,
) -> bytes:
    PE_OFF, OPT_OFF, OPT_SIZE = 0x80, 0x98, 0xF0
    TEXT_RAW, IDATA_RAW = 0x400, 0x600

    file_header = struct.pack("<HHIIIHH", 0x8664, 2, 0x5F000000, 0, 0, OPT_SIZE, 0x0022)

    opt = bytearray(OPT_SIZE)
    struct.pack_into("<H", opt, 0, 0x20B)                     # PE32+ magic
    struct.pack_into("<I", opt, 16, 0x1000)                   # AddressOfEntryPoint
    struct.pack_into("<Q", opt, 24, 0x140000000)              # ImageBase
    struct.pack_into("<H", opt, 68, 3)                        # Subsystem = CUI
    struct.pack_into("<H", opt, 70, dll_chars)                # DllCharacteristics
    struct.pack_into("<I", opt, 108, 16)                      # NumberOfRvaAndSizes
    dirs = [
        (0x2080, 0x50),  # export
        (0x2000, 0x28),  # import
        (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0),
        (0, 0),                                        # TLS
        (0x2050, 0x90) if load_config else (0, 0),     # LOAD_CONFIG
    ] + [(0, 0)] * 5
    for i, (rva, size) in enumerate(dirs):
        struct.pack_into("<II", opt, 112 + i * 8, rva, size)

    def sec(name, vaddr, vsize, rawsize, rawptr, chars):
        return name.ljust(8, b"\x00") + struct.pack("<IIII", vsize, vaddr, rawsize, rawptr) + \
            b"\x00" * 12 + struct.pack("<I", chars)  # 40 bytes total

    sections = (
        sec(b".text", 0x1000, 0x200, 0x200, TEXT_RAW, 0x60000020)
        + sec(b".idata", 0x2000, 0x200, 0x200, IDATA_RAW, 0xC0000040)
    )

    idata = bytearray(0x200)
    # Import descriptors at RVA 0x2000 (file 0x600)
    struct.pack_into("<IIIII", idata, 0x00, 0x2020, 0, 0, 0x2040, 0x2060)
    struct.pack_into("<IIIII", idata, 0x14, 0, 0, 0, 0, 0)
    idata[0x20:0x20 + 4] = struct.pack("<I", 0x2030)            # name RVAs
    idata[0x24:0x24 + 4] = struct.pack("<I", 0)
    idata[0x30:0x30 + 2] = b"\x00\x00"                          # Hint
    idata[0x32:0x32 + 12] = b"CreateFileW\x00"
    idata[0x40:0x40 + 13] = b"KERNEL32.DLL\x00"
    idata[0x60:0x60 + 4] = struct.pack("<I", 0x2030)            # IAT
    idata[0x64:0x64 + 4] = struct.pack("<I", 0)
    # Export directory at RVA 0x2080 (file 0x680)
    struct.pack_into("<IIHHIIIIIII", idata, 0x80, 0, 0, 0, 0, 0, 1, 1, 1,
                     0x20B0, 0x20C0, 0x20D0)
    struct.pack_into("<I", idata, 0xB0, 0x1050)                 # funcs[0] RVA
    struct.pack_into("<I", idata, 0xC0, 0x20E0)                 # names[0] RVA
    struct.pack_into("<H", idata, 0xD0, 0)                      # ordinals[0]
    idata[0xE0:0xE0 + 8] = b"DllMain\x00"

    head = bytearray(TEXT_RAW)
    head[0:2] = b"MZ"
    struct.pack_into("<I", head, 0x3C, PE_OFF)
    head[PE_OFF : PE_OFF + 4] = b"PE\x00\x00"
    head[PE_OFF + 4 : PE_OFF + 4 + 20] = file_header
    head[OPT_OFF : OPT_OFF + OPT_SIZE] = opt
    head[OPT_OFF + OPT_SIZE : OPT_OFF + OPT_SIZE + 80] = sections

    out = bytes(head) + b"\xCC" * 0x200 + bytes(idata)
    if overlay:
        out += b"OVERLAY!"
    return out


# ═══════════════════════════════ Mach-O builder ══════════════════════════


def build_macho64(pie: bool = True, code_signature: bool = True) -> bytes:
    header = struct.pack(
        "<IIIIIII", 0xFEEDFACF, 0x0100000C, 0, 2, 3, 72 + 56 + 16,
        0x200000 if pie else 0,
    )

    seg = struct.pack(
        "<II16sQQQQiiII", 0x19, 72, b"__TEXT",
        0, 0x1000, 0, 0x200, 5, 5, 0, 0,
    )

    name = b"/usr/lib/libSystem.B.dylib\x00".ljust(32, b"\x00")
    dylib = struct.pack("<IIIIII", 0xC, 24 + len(name), 24, 0, 0, 0) + name

    sig = struct.pack("<IIII", 0x1D, 16, 0x200, 64)

    cmds = seg + dylib + (sig if code_signature else b"")
    total = bytearray(0x240)
    total[0:32] = header
    total[32 : 32 + len(cmds)] = cmds
    total[0x200:0x240] = b"S" * 64
    return bytes(total)


def build_fat_macho() -> bytes:
    slice_ = build_macho64()
    out = bytearray(0x100 + len(slice_))
    struct.pack_into(">I", out, 0, 0xCAFEBABE)
    struct.pack_into(">I", out, 4, 1)
    struct.pack_into(">IIII", out, 8, 0x0100000C, 0, 0x100, len(slice_))
    out[0x100:] = slice_
    return bytes(out)


# ═══════════════════════════════ Tests ═══════════════════════════════════


class TestDetectFormat(unittest.TestCase):
    def test_magics(self):
        self.assertEqual(detect_format(build_elf64()), "ELF")
        self.assertEqual(detect_format(build_pe64()), "PE")
        self.assertEqual(detect_format(build_macho64()), "Mach-O")
        self.assertEqual(detect_format(build_fat_macho()), "Fat Mach-O")
        self.assertIsNone(detect_format(b"just some text, not a binary"))
        self.assertIsNone(detect_format(b"MZ"))  # too short

    def test_parse_rejects_unknown(self):
        with self.assertRaises(ValueError):
            parse_binary(b"")
        with self.assertRaises(ValueError):
            parse_binary(b"\x00\x01\x02\x03garbage")


class TestElf(unittest.TestCase):
    def test_full_report(self):
        r = parse_binary(build_elf64())
        self.assertEqual(r["format"], "ELF")
        self.assertEqual(r["arch"], "x86_64")
        self.assertEqual(r["bits"], 64)
        self.assertEqual(r["endian"], "little")
        self.assertFalse(r["pie"])          # ET_EXEC
        self.assertTrue(r["nx"])            # PT_GNU_STACK without PF_X
        self.assertEqual(r["relro"], "full")
        self.assertTrue(r["canary"])
        self.assertIn("libc.so.6", r["needed"])
        self.assertEqual(r["interpreter"], "/lib64/ld-linux-x86-64.so.2")
        self.assertFalse(r["static"])
        names = {s["name"] for s in r["symbols"]}
        self.assertIn("main", names)
        self.assertIn("__stack_chk_fail", names)
        main = next(s for s in r["symbols"] if s["name"] == "main")
        self.assertEqual(main["size"], 42)
        self.assertEqual(r["overlay"]["size"], 0)

    def test_pie(self):
        r = parse_binary(build_elf64(e_type=3))
        self.assertTrue(r["pie"])
        self.assertEqual(r["file_type"], "shared-object")

    def test_relro_partial_without_bind_now(self):
        r = parse_binary(build_elf64(bind_now=False))
        self.assertEqual(r["relro"], "partial")

    def test_executable_stack_disables_nx(self):
        r = parse_binary(build_elf64(gnu_stack_flags=1))
        self.assertFalse(r["nx"])

    def test_no_canary(self):
        r = parse_binary(build_elf64(canary=False))
        self.assertFalse(r["canary"])
        self.assertNotIn("__stack_chk_fail", {s["name"] for s in r["symbols"]})

    def test_overlay_detected(self):
        r = parse_binary(build_elf64(overlay=True))
        self.assertEqual(r["overlay"]["size"], len("OVERLAY!"))

    def test_sections_parsed(self):
        r = parse_binary(build_elf64())
        by_name = {s["name"]: s for s in r["sections"]}
        self.assertIn(".text", by_name)
        self.assertTrue(by_name[".text"]["exec"])
        self.assertFalse(by_name[".text"]["write"])
        self.assertIn(".dynstr", by_name)


class TestPe(unittest.TestCase):
    def test_full_report(self):
        r = parse_binary(build_pe64())
        self.assertEqual(r["format"], "PE")
        self.assertEqual(r["arch"], "x86_64")
        self.assertEqual(r["bits"], 64)
        self.assertTrue(r["pie"])            # DYNAMIC_BASE
        self.assertTrue(r["nx"])             # NX_COMPAT
        self.assertTrue(r["high_entropy_va"])
        self.assertFalse(r["cfg"])
        self.assertTrue(r["canary"])         # load-config dir present
        self.assertEqual(r["subsystem"], "windows-cui")
        self.assertEqual(r["imports"].get("KERNEL32.DLL"), ["CreateFileW"])
        self.assertEqual(r["needed"], ["KERNEL32.DLL"])
        self.assertEqual(r["exports"], [{"name": "DllMain", "addr": 0x1050, "size": 0}])
        self.assertFalse(r["signed"])
        self.assertEqual(r["overlay"]["size"], len("OVERLAY!"))

    def test_no_load_config_no_canary(self):
        r = parse_binary(build_pe64(load_config=False))
        self.assertFalse(r["canary"])

    def test_cfg_flag(self):
        r = parse_binary(build_pe64(dll_chars=0x4000))
        self.assertTrue(r["cfg"])
        self.assertFalse(r["pie"])
        self.assertFalse(r["nx"])


class TestMacho(unittest.TestCase):
    def test_full_report(self):
        r = parse_binary(build_macho64())
        self.assertEqual(r["format"], "Mach-O")
        self.assertEqual(r["arch"], "arm64")
        self.assertEqual(r["bits"], 64)
        self.assertTrue(r["pie"])
        self.assertTrue(r["nx"])             # __TEXT is not writable
        self.assertTrue(r["signed"])         # LC_CODE_SIGNATURE
        self.assertFalse(r["encrypted"])
        self.assertIn("/usr/lib/libSystem.B.dylib", r["needed"])
        self.assertEqual(r["file_type"], "executable")

    def test_no_pie_no_signature(self):
        r = parse_binary(build_macho64(pie=False, code_signature=False))
        self.assertFalse(r["pie"])
        self.assertFalse(r["signed"])

    def test_fat_binary(self):
        r = parse_binary(build_fat_macho())
        self.assertEqual(r["format"], "Fat Mach-O")
        self.assertEqual(r["arch"], "arm64")
        self.assertEqual(len(r["fat_slices"]), 1)
        self.assertEqual(r["fat_slices"][0]["format"], "Mach-O")


if __name__ == "__main__":
    unittest.main()
