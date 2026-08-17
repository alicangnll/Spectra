"""Pure-Python binary format parsing (ELF / PE / Mach-O).

Shared foundation for the file-level tools (checksec, entropy report,
binary diff, file metadata). Everything is stdlib-only and parses bytes
directly — no external command and no pip dependency is ever required.

The public entry point is :func:`parse_binary`, which dispatches on the
file magic and returns a format report dict. Common keys across formats:

- ``format``      "ELF" | "PE" | "Mach-O" | "Fat Mach-O"
- ``arch``        human architecture name ("x86_64", "arm64", ...)
- ``bits``        32 | 64
- ``endian``      "little" | "big"
- ``pie``         bool | None   (None = not applicable)
- ``nx``          bool | None
- ``relro``       "full" | "partial" | "none" | None (ELF only)
- ``canary``      bool (heuristic stack-cookie indicator)
- ``sections``    [{name, offset, size, vaddr, exec, write}]
- ``needed``      imported shared libraries (DT_NEEDED / import DLLs / dylibs)
- ``symbols``     [{name, addr, size}] (size 0 where the format has none)
- ``overlay``     {offset, size} trailing data beyond declared sections
"""

from __future__ import annotations

import struct

# Sanity caps so a malformed file can never make us allocate wildly.
MAX_SYMBOLS = 20000
MAX_IMPORT_DLLS = 512
MAX_FUNCS_PER_DLL = 4000

# ─── ELF constants ────────────────────────────────────────────────────────

_PT_LOAD = 1
_PT_DYNAMIC = 2
_PT_INTERP = 3
_PT_GNU_STACK = 0x6474E551
_PT_GNU_RELRO = 0x6474E552

_DT_NEEDED = 1
_DT_STRTAB = 5
_DT_BIND_NOW = 24
_DT_FLAGS = 30
_DT_FLAGS_1 = 0x6FFFFFFB

_DF_BIND_NOW = 0x8
_DF_1_NOW = 0x1

_SHT_SYMTAB = 2
_SHT_DYNSYM = 11
_SHF_WRITE = 0x1
_SHF_EXECINSTR = 0x4

_ELF_MACHINES = {
    0x03: "x86",
    0x3E: "x86_64",
    0x28: "arm",
    0xB7: "aarch64",
    0xF3: "riscv64",
    0x08: "mips",
    0x14: "powerpc",
    0x15: "powerpc64",
}

# ─── PE constants ─────────────────────────────────────────────────────────

_PE_MACHINE = {
    0x014C: "x86",
    0x8664: "x86_64",
    0xAA64: "arm64",
    0x01C0: "arm",
    0x01C4: "armv7",
    0x0200: "ia64",
}

_IMAGE_DLL_CHARACTERISTICS_HIGH_ENTROPY_VA = 0x0020
_IMAGE_DLL_CHARACTERISTICS_DYNAMIC_BASE = 0x0040
_IMAGE_DLL_CHARACTERISTICS_NX_COMPAT = 0x0100
_IMAGE_DLL_CHARACTERISTICS_NO_SEH = 0x0400
_IMAGE_DLL_CHARACTERISTICS_GUARD_CF = 0x4000

_IMAGE_SCN_MEM_EXECUTE = 0x20000000
_IMAGE_SCN_MEM_WRITE = 0x80000000

_DIR_EXPORT = 0
_DIR_IMPORT = 1
_DIR_SECURITY = 4
_DIR_DEBUG = 6
_DIR_TLS = 9
_DIR_LOAD_CONFIG = 10

_PE_SUBSYSTEM = {
    1: "native",
    2: "windows-gui",
    3: "windows-cui",
    5: "os2-cui",
    7: "posix-cui",
    10: "efi-app",
    14: "xbox",
}

# ─── Mach-O constants ─────────────────────────────────────────────────────

_MH_PIE = 0x200000

_LC_SEGMENT = 0x1
_LC_SYMTAB = 0x2
_LC_LOAD_DYLIB = 0xC
_LC_CODE_SIGNATURE = 0x1D
_LC_ENCRYPTION_INFO = 0x21
_LC_ENCRYPTION_INFO_64 = 0x2C

_MACHO_CPU = {
    7: "x86",
    7 + 0x01000000: "x86_64",
    12: "arm",
    12 + 0x01000000: "arm64",
}

_FAT_MAGIC = {0xCAFEBABE, 0xCAFEBABF}


def _read_cstring(data: bytes, offset: int, max_len: int = 4096) -> str:
    """Read a NUL-terminated string at *offset*; '' when out of bounds."""
    if offset < 0 or offset >= len(data):
        return ""
    end = data.find(b"\x00", offset, min(len(data), offset + max_len))
    if end < 0:
        end = min(len(data), offset + max_len)
    return data[offset:end].decode("utf-8", "replace")


def _ascii_name(raw: bytes) -> str:
    """Section/segment names are fixed-width NUL padded fields."""
    return raw.split(b"\x00", 1)[0].decode("utf-8", "replace")


# ═══ ELF ═════════════════════════════════════════════════════════════════


def _elf_phdrs(data: bytes, is64: bool, little: bool) -> list[dict]:
    e = "<" if little else ">"
    if is64:
        phoff = struct.unpack_from(e + "Q", data, 32)[0]
        phentsize = struct.unpack_from(e + "H", data, 54)[0]
        phnum = struct.unpack_from(e + "H", data, 56)[0]
    else:
        phoff = struct.unpack_from(e + "I", data, 28)[0]
        phentsize = struct.unpack_from(e + "H", data, 42)[0]
        phnum = struct.unpack_from(e + "H", data, 44)[0]

    phdrs: list[dict] = []
    if phentsize == 0:
        return phdrs
    for i in range(min(phnum, 4096)):
        off = phoff + i * phentsize
        if off + phentsize > len(data):
            break
        if is64:
            p_type, p_flags, p_offset, p_vaddr, _paddr, p_filesz = struct.unpack_from(
                e + "IIQQQQ", data, off
            )
        else:
            p_type, p_offset, p_vaddr, _paddr, p_filesz = struct.unpack_from(
                e + "IIIII", data, off
            )
            p_flags = struct.unpack_from(e + "I", data, off + 24)[0]
        phdrs.append(
            {"type": p_type, "flags": p_flags, "offset": p_offset, "vaddr": p_vaddr, "filesz": p_filesz}
        )
    return phdrs


def _elf_sections(data: bytes, is64: bool, little: bool) -> list[dict]:
    e = "<" if little else ">"
    if is64:
        e_shoff = struct.unpack_from(e + "Q", data, 40)[0]
        e_shentsize = struct.unpack_from(e + "H", data, 58)[0]
        e_shnum = struct.unpack_from(e + "H", data, 60)[0]
        e_shstrndx = struct.unpack_from(e + "H", data, 62)[0]
    else:
        e_shoff = struct.unpack_from(e + "I", data, 32)[0]
        e_shentsize = struct.unpack_from(e + "H", data, 46)[0]
        e_shnum = struct.unpack_from(e + "H", data, 48)[0]
        e_shstrndx = struct.unpack_from(e + "H", data, 50)[0]

    raw: list[dict] = []
    if 0 < e_shnum <= 65536 and e_shoff + e_shnum * e_shentsize <= len(data):
        for i in range(e_shnum):
            off = e_shoff + i * e_shentsize
            if is64:
                sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size = struct.unpack_from(
                    e + "IIQQQQ", data, off
                )
                sh_link = struct.unpack_from(e + "I", data, off + 40)[0]
            else:
                sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size = struct.unpack_from(
                    e + "IIIIII", data, off
                )
                sh_link = struct.unpack_from(e + "I", data, off + 24)[0]
            raw.append(
                {
                    "sh_name": sh_name,
                    "sh_type": sh_type,
                    "sh_flags": sh_flags,
                    "sh_addr": sh_addr,
                    "sh_offset": sh_offset,
                    "sh_size": sh_size,
                    "sh_link": sh_link,
                }
            )

    # Names come from the shstrtab section.
    if 0 <= e_shstrndx < len(raw):
        strtab = raw[e_shstrndx]
        base = strtab["sh_offset"]
        for sec in raw:
            pos = base + sec["sh_name"]
            sec["name"] = _read_cstring(data, pos) if pos < len(data) else ""
    else:
        for sec in raw:
            sec["name"] = ""

    sections: list[dict] = []
    for sec in raw:
        sections.append(
            {
                "name": sec["name"],
                "offset": sec["sh_offset"],
                "size": sec["sh_size"],
                "vaddr": sec["sh_addr"],
                "exec": bool(sec["sh_flags"] & _SHF_EXECINSTR),
                "write": bool(sec["sh_flags"] & _SHF_WRITE),
                "_raw": sec,
            }
        )
    return sections


def _elf_symbols(data: bytes, sections: list[dict], is64: bool, little: bool) -> list[dict]:
    e = "<" if little else ">"
    out: list[dict] = []
    for sec in sections:
        raw = sec["_raw"]
        if raw["sh_type"] not in (_SHT_SYMTAB, _SHT_DYNSYM) or raw["sh_link"] >= len(sections):
            continue
        strtab = sections[raw["sh_link"]]["_raw"]
        entsize = 24 if is64 else 16
        count = min(raw["sh_size"] // entsize, MAX_SYMBOLS)
        for i in range(count):
            off = raw["sh_offset"] + i * entsize
            if off + entsize > len(data):
                break
            st_name, st_info = struct.unpack_from(e + "IB", data, off)
            if is64:
                st_value, st_size = struct.unpack_from(e + "QQ", data, off + 8)
            else:
                st_value, st_size = struct.unpack_from(e + "II", data, off + 4)
            if st_info & 0xF != 2:  # STT_FUNC
                continue
            name = _read_cstring(data, strtab["sh_offset"] + st_name)
            if name:
                out.append({"name": name, "addr": st_value, "size": st_size})
    return out


def _parse_elf(data: bytes) -> dict:
    is64 = data[4] == 2
    little = data[5] == 1
    e = "<" if little else ">"
    e_type, e_machine = struct.unpack_from(e + "HH", data, 16)

    phdrs = _elf_phdrs(data, is64, little)
    sections = _elf_sections(data, is64, little)

    def vaddr_to_offset(vaddr: int) -> int | None:
        for ph in phdrs:
            if ph["type"] == _PT_LOAD and ph["vaddr"] <= vaddr < ph["vaddr"] + ph["filesz"]:
                return ph["offset"] + (vaddr - ph["vaddr"])
        return None

    # ── dynamic table: NEEDED libraries + BIND_NOW / FLAGS ──
    needed: list[str] = []
    bind_now = False
    strtab_vaddr = 0
    for ph in phdrs:
        if ph["type"] != _PT_DYNAMIC:
            continue
        entsize = 16 if is64 else 8
        for off in range(ph["offset"], min(ph["offset"] + ph["filesz"], len(data) - entsize), entsize):
            if is64:
                d_tag, d_val = struct.unpack_from(e + "qQ", data, off)
            else:
                d_tag, d_val = struct.unpack_from(e + "iI", data, off)
            if d_tag == 0:
                break
            if d_tag == _DT_NEEDED:
                if not strtab_vaddr:
                    for off2 in range(
                        ph["offset"],
                        min(ph["offset"] + ph["filesz"], len(data) - entsize),
                        entsize,
                    ):
                        tag2, val2 = (
                            struct.unpack_from(e + "qQ", data, off2)
                            if is64
                            else struct.unpack_from(e + "iI", data, off2)
                        )
                        if tag2 == _DT_STRTAB:
                            strtab_vaddr = val2
                            break
                        if tag2 == 0:
                            break
                base = vaddr_to_offset(strtab_vaddr)
                if base is not None:
                    name = _read_cstring(data, base + d_val)
                    if name and len(needed) < MAX_IMPORT_DLLS:
                        needed.append(name)
            elif d_tag == _DT_BIND_NOW:
                bind_now = True
            elif d_tag == _DT_FLAGS and d_val & _DF_BIND_NOW:
                bind_now = True
            elif d_tag == _DT_FLAGS_1 and d_val & _DF_1_NOW:
                bind_now = True

    has_relro = any(ph["type"] == _PT_GNU_RELRO for ph in phdrs)
    if has_relro and bind_now:
        relro = "full"
    elif has_relro:
        relro = "partial"
    else:
        relro = "none"

    gnu_stack = next((ph for ph in phdrs if ph["type"] == _PT_GNU_STACK), None)
    if gnu_stack is None:
        nx = True  # non-executable stack by default when PT_GNU_STACK is absent
    else:
        nx = not bool(gnu_stack["flags"] & 0x1)  # PF_X

    interp = next((ph for ph in phdrs if ph["type"] == _PT_INTERP), None)
    interpreter = _read_cstring(data, interp["offset"]) if interp is not None else ""

    symbols = _elf_symbols(data, sections, is64, little)
    canary = any(s["name"] == "__stack_chk_fail" for s in symbols) or b"__stack_chk_fail" in data

    # Overlay = trailing bytes after everything the file declares, including
    # the section header table itself.
    if is64:
        e_shoff = struct.unpack_from(e + "Q", data, 40)[0]
        e_shentsize = struct.unpack_from(e + "H", data, 58)[0]
        e_shnum = struct.unpack_from(e + "H", data, 60)[0]
    else:
        e_shoff = struct.unpack_from(e + "I", data, 32)[0]
        e_shentsize = struct.unpack_from(e + "H", data, 46)[0]
        e_shnum = struct.unpack_from(e + "H", data, 48)[0]
    sh_end = e_shoff + e_shentsize * e_shnum if e_shnum else 0
    last = max([s["offset"] + s["size"] for s in sections if s["offset"]] + [sh_end])
    overlay = {"offset": last, "size": max(0, len(data) - last)}

    return {
        "format": "ELF",
        "arch": _ELF_MACHINES.get(e_machine, f"machine-{e_machine:#x}"),
        "bits": 64 if is64 else 32,
        "endian": "little" if little else "big",
        "file_type": {1: "relocatable", 2: "executable", 3: "shared-object"}.get(e_type, str(e_type)),
        "pie": e_type == 3,
        "nx": nx,
        "relro": relro,
        "canary": canary,
        "cfg": None,
        "sections": [{k: v for k, v in s.items() if k != "_raw"} for s in sections],
        "needed": needed,
        "interpreter": interpreter,
        "static": interp is None,
        "symbols": symbols,
        "signed": None,
        "encrypted": False,
        "overlay": overlay,
        "file_size": len(data),
    }


# ═══ PE ═════════════════════════════════════════════════════════════════


def _pe_sections(data: bytes, opt_off: int, num_sections: int, opt_size: int) -> tuple[list[dict], int]:
    sections: list[dict] = []
    sec_off = opt_off + opt_size
    count = min(num_sections, 96)
    for i in range(count):
        off = sec_off + i * 40
        if off + 40 > len(data):
            break
        name = _ascii_name(data[off : off + 8])
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, off + 8)
        chars = struct.unpack_from("<I", data, off + 36)[0]
        sections.append(
            {
                "name": name,
                "offset": rawptr,
                "size": rawsize,
                "vaddr": vaddr,
                "vsize": vsize,
                "exec": bool(chars & _IMAGE_SCN_MEM_EXECUTE),
                "write": bool(chars & _IMAGE_SCN_MEM_WRITE),
            }
        )
    return sections, sec_off + count * 40


def _pe_rva_to_offset(sections: list[dict], rva: int) -> int | None:
    for s in sections:
        span = max(s["vsize"], s["size"])
        if s["vaddr"] <= rva < s["vaddr"] + span:
            delta = rva - s["vaddr"]
            if delta < s["size"]:
                return s["offset"] + delta
            return None
    if rva < 0x1000:  # the headers themselves
        return rva
    return None


def _pe_imports(
    data: bytes, sections: list[dict], import_rva: int, import_size: int, is64: bool
) -> dict[str, list[str]]:
    base = _pe_rva_to_offset(sections, import_rva)
    if base is None:
        return {}
    n_desc = min(import_size // 20 if import_size else 96, MAX_IMPORT_DLLS)
    imports: dict[str, list[str]] = {}
    for i in range(n_desc):
        desc = base + i * 20
        if desc + 20 > len(data):
            break
        oft, _ts, _fwd, name_rva, ft = struct.unpack_from("<IIIII", data, desc)
        if oft == 0 and ft == 0:
            break
        thunk_rva = oft or ft
        name_off = _pe_rva_to_offset(sections, name_rva)
        dll = _read_cstring(data, name_off) if name_off is not None else f"rva-{name_rva:#x}"
        funcs: list[str] = []
        thunk_off = _pe_rva_to_offset(sections, thunk_rva)
        if thunk_off is not None:
            width = 8 if is64 else 4
            ordinal_flag = 0x8000000000000000 if is64 else 0x80000000
            for j in range(MAX_FUNCS_PER_DLL):
                pos = thunk_off + j * width
                if pos + width > len(data):
                    break
                val = struct.unpack_from("<Q" if is64 else "<I", data, pos)[0]
                if val == 0:
                    break
                if val & ordinal_flag:
                    funcs.append(f"ordinal-{val & 0xFFFF}")
                    continue
                fname_off = _pe_rva_to_offset(sections, val)  # IMAGE_IMPORT_BY_NAME
                if fname_off is not None:
                    fname = _read_cstring(data, fname_off + 2)  # skip the Hint field
                    if fname:
                        funcs.append(fname)
        imports[dll] = funcs
    return imports


def _pe_exports(data: bytes, sections: list[dict], export_rva: int) -> list[dict]:
    base = _pe_rva_to_offset(sections, export_rva)
    if base is None or base + 40 > len(data):
        return []
    (_chars, _ts, _maj, _min, _name_rva, _ord_base, _nfuncs, nnames,
     addr_funcs, addr_names, addr_ords) = struct.unpack_from("<IIHHIIIIIII", data, base)

    def _read_rva_array(rva: int, count: int) -> list[int]:
        off = _pe_rva_to_offset(sections, rva)
        if off is None:
            return []
        vals: list[int] = []
        for i in range(min(count, MAX_SYMBOLS)):
            if off + i * 4 + 4 > len(data):
                break
            vals.append(struct.unpack_from("<I", data, off + i * 4)[0])
        return vals

    funcs = _read_rva_array(addr_funcs, _nfuncs)
    names = _read_rva_array(addr_names, nnames)
    ords = _read_rva_array(addr_ords, nnames)

    out: list[dict] = []
    for i, name_rva in enumerate(names):
        noff = _pe_rva_to_offset(sections, name_rva)
        name = _read_cstring(data, noff) if noff is not None else ""
        if not name:
            continue
        func_addr = funcs[ords[i]] if i < len(ords) and ords[i] < len(funcs) else 0
        out.append({"name": name, "addr": func_addr, "size": 0})
    return out


def _parse_pe(data: bytes) -> dict:
    if data[:2] != b"MZ":
        raise ValueError("not a PE file (missing MZ header)")
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_off : pe_off + 4] != b"PE\x00\x00":
        raise ValueError("not a PE file (missing PE signature)")

    machine, nsections, timestamp, _sym_ptr, _nsyms, opt_size, characteristics = struct.unpack_from(
        "<HHIIIHH", data, pe_off + 4
    )
    opt_off = pe_off + 24
    magic = struct.unpack_from("<H", data, opt_off)[0]
    is64 = magic == 0x20B
    if magic not in (0x10B, 0x20B):
        raise ValueError(f"unknown PE optional header magic {magic:#x}")

    entry_rva = struct.unpack_from("<I", data, opt_off + 16)[0]
    subsystem = struct.unpack_from("<H", data, opt_off + (68 if is64 else 66))[0]
    dll_chars = struct.unpack_from("<H", data, opt_off + (70 if is64 else 68))[0]
    nrva = struct.unpack_from("<I", data, opt_off + (108 if is64 else 92))[0]
    dirs_off = opt_off + (112 if is64 else 96)

    dirs: list[tuple[int, int]] = []
    for i in range(min(nrva, 16)):
        rva, size = struct.unpack_from("<II", data, dirs_off + i * 8)
        dirs.append((rva, size))

    sections, end_of_sections = _pe_sections(data, opt_off, nsections, opt_size)

    imports: dict[str, list[str]] = {}
    if len(dirs) > _DIR_IMPORT and dirs[_DIR_IMPORT][0]:
        imports = _pe_imports(data, sections, dirs[_DIR_IMPORT][0], dirs[_DIR_IMPORT][1], is64)

    exports: list[dict] = []
    if len(dirs) > _DIR_EXPORT and dirs[_DIR_EXPORT][0]:
        exports = _pe_exports(data, sections, dirs[_DIR_EXPORT][0])

    canary = bool(len(dirs) > _DIR_LOAD_CONFIG and dirs[_DIR_LOAD_CONFIG][0])
    security_dir = dirs[_DIR_SECURITY] if len(dirs) > _DIR_SECURITY else (0, 0)
    debug_dir = dirs[_DIR_DEBUG] if len(dirs) > _DIR_DEBUG else (0, 0)
    tls_dir = dirs[_DIR_TLS] if len(dirs) > _DIR_TLS else (0, 0)

    last_raw = max([s["offset"] + s["size"] for s in sections] or [end_of_sections])
    overlay = {"offset": last_raw, "size": max(0, len(data) - last_raw)}

    return {
        "format": "PE",
        "arch": _PE_MACHINE.get(machine, f"machine-{machine:#x}"),
        "bits": 64 if is64 else 32,
        "endian": "little",
        "file_type": "dll" if characteristics & 0x2000 else "executable",
        "pie": bool(dll_chars & _IMAGE_DLL_CHARACTERISTICS_DYNAMIC_BASE),
        "nx": bool(dll_chars & _IMAGE_DLL_CHARACTERISTICS_NX_COMPAT),
        "relro": None,
        "canary": canary,  # load-config directory present → /GS likely
        "cfg": bool(dll_chars & _IMAGE_DLL_CHARACTERISTICS_GUARD_CF),
        "high_entropy_va": bool(dll_chars & _IMAGE_DLL_CHARACTERISTICS_HIGH_ENTROPY_VA),
        "no_seh": bool(dll_chars & _IMAGE_DLL_CHARACTERISTICS_NO_SEH),
        "sections": sections,
        "needed": list(imports.keys()),
        "imports": imports,
        "exports": exports,
        "entry_rva": entry_rva,
        "subsystem": _PE_SUBSYSTEM.get(subsystem, str(subsystem)),
        "timestamp": timestamp,
        "signed": bool(security_dir[0]),  # Authenticode table present
        "has_debug_dir": bool(debug_dir[0]),
        "has_tls_callbacks": bool(tls_dir[0]),
        "symbols": [{"name": x["name"], "addr": x["addr"], "size": 0} for x in exports],
        "encrypted": False,
        "overlay": overlay,
        "file_size": len(data),
    }


# ═══ Mach-O ═════════════════════════════════════════════════════════════


def _parse_macho_slice(data: bytes) -> dict:
    magic = struct.unpack_from("<I", data, 0)[0]
    if magic in (0xFEEDFACE, 0xFEEDFACF):
        e = "<"
    elif magic in (0xCEFAEDFE, 0xCFFAEDFE):
        e = ">"
    else:
        raise ValueError("not a Mach-O slice")
    is64 = magic in (0xFEEDFACF, 0xCFFAEDFE)

    cputype, _cpusub, filetype, ncmds, _sizeofcmds, flags = struct.unpack_from(e + "IIIIII", data, 4)

    sections: list[dict] = []
    dylibs: list[str] = []
    symbols: list[dict] = []
    signed = False
    encrypted = False

    off = 32 if is64 else 28
    for _ in range(min(ncmds, 4096)):
        if off + 8 > len(data):
            break
        cmd, cmdsize = struct.unpack_from(e + "II", data, off)
        if cmdsize < 8 or off + cmdsize > len(data):
            break
        if cmd in (_LC_SEGMENT, 0x19):  # LC_SEGMENT / LC_SEGMENT_64
            seg64 = cmd == 0x19
            segname = _ascii_name(data[off + 8 : off + 24])
            if seg64:
                vmaddr, _vmsize, fileoff, filesize = struct.unpack_from(e + "QQQQ", data, off + 24)
                maxprot, initprot, nsects = struct.unpack_from(e + "III", data, off + 56)
                sect_base = off + 72
                sect_hdr = 80
            else:
                vmaddr, _vmsize, fileoff, filesize = struct.unpack_from(e + "IIII", data, off + 24)
                maxprot, initprot, nsects = struct.unpack_from(e + "III", data, off + 40)
                sect_base = off + 56
                sect_hdr = 68
            del maxprot
            sections.append(
                {
                    "name": segname,
                    "offset": fileoff,
                    "size": filesize,
                    "vaddr": vmaddr,
                    "exec": bool(initprot & 4),
                    "write": bool(initprot & 2),
                }
            )
            for i in range(min(nsects, 255)):
                so = sect_base + i * sect_hdr
                if so + sect_hdr > off + cmdsize:
                    break
                sectname = _ascii_name(data[so : so + 16])
                if seg64:
                    saddr, ssize = struct.unpack_from(e + "QQ", data, so + 32)
                    soff = struct.unpack_from(e + "I", data, so + 48)[0]
                else:
                    saddr, ssize = struct.unpack_from(e + "II", data, so + 32)
                    soff = struct.unpack_from(e + "I", data, so + 40)[0]
                sections.append(
                    {
                        "name": f"{segname},{sectname}",
                        "offset": soff,
                        "size": ssize,
                        "vaddr": saddr,
                        "exec": bool(initprot & 4),
                        "write": bool(initprot & 2),
                    }
                )
        elif cmd == _LC_LOAD_DYLIB:
            name_off_val = struct.unpack_from(e + "I", data, off + 8)[0]
            name = _read_cstring(data, off + name_off_val)
            if name and len(dylibs) < MAX_IMPORT_DLLS:
                dylibs.append(name)
        elif cmd == _LC_SYMTAB:
            symoff, nsyms, stroff, _strsize = struct.unpack_from(e + "IIII", data, off + 8)
            for i in range(min(nsyms, MAX_SYMBOLS)):
                so = symoff + i * 16
                if so + 16 > len(data):
                    break
                strx, n_type = struct.unpack_from(e + "IB", data, so)
                value = (
                    struct.unpack_from(e + "Q", data, so + 8)[0]
                    if is64
                    else struct.unpack_from(e + "I", data, so + 8)[0]
                )
                if n_type & 0xE == 0xE and strx:  # N_SECT symbols
                    name = _read_cstring(data, stroff + strx)
                    if name:
                        symbols.append({"name": name, "addr": value, "size": 0})
        elif cmd == _LC_CODE_SIGNATURE:
            signed = True
        elif cmd in (_LC_ENCRYPTION_INFO, _LC_ENCRYPTION_INFO_64):
            cryptid = struct.unpack_from(e + "I", data, off + 16)[0]
            encrypted = cryptid != 0
        off += cmdsize

    # __TEXT writability is the practical NX indicator on macOS.
    text = next((s for s in sections if s["name"] == "__TEXT"), None)
    nx = not text["write"] if text else None

    last = max([s["offset"] + s["size"] for s in sections] or [off])
    overlay = {"offset": last, "size": max(0, len(data) - last)}

    return {
        "format": "Mach-O",
        "arch": _MACHO_CPU.get(cputype, f"cputype-{cputype:#x}"),
        "bits": 64 if is64 else 32,
        "endian": "little" if e == "<" else "big",
        "file_type": {1: "object", 2: "executable", 6: "dylib", 7: "dylinker", 8: "bundle"}.get(
            filetype, str(filetype)
        ),
        "pie": bool(flags & _MH_PIE),
        "nx": nx,
        "relro": None,
        "canary": b"___stack_chk_guard" in data,
        "cfg": None,
        "sections": sections,
        "needed": dylibs,
        "symbols": symbols,
        "signed": signed,
        "encrypted": encrypted,
        "overlay": overlay,
        "file_size": len(data),
    }


def _parse_fat_macho(data: bytes) -> dict:
    nfat = struct.unpack_from(">I", data, 4)[0]
    slices: list[dict] = []
    for i in range(min(nfat, 16)):
        off = 8 + i * 20
        if off + 20 > len(data):
            break
        _cputype, _cpusub, slice_off, slice_size = struct.unpack_from(">IIII", data, off)
        if slice_off + slice_size <= len(data) and slice_size >= 32:
            try:
                sub = _parse_macho_slice(data[slice_off : slice_off + slice_size])
            except ValueError:
                continue
            sub["file_size"] = slice_size
            slices.append(sub)
    if not slices:
        raise ValueError("fat Mach-O contains no parseable slices")
    primary = dict(slices[0])
    primary["format"] = "Fat Mach-O"
    primary["fat_slices"] = slices
    return primary


# ═══ Dispatcher ═════════════════════════════════════════════════════════


def detect_format(data: bytes) -> str | None:
    if len(data) < 4:
        return None
    if data[:4] == b"\x7fELF":
        return "ELF"
    if data[:2] == b"MZ":
        return "PE"
    magic = struct.unpack_from("<I", data, 0)[0]
    be_magic = struct.unpack_from(">I", data, 0)[0]
    if magic in (0xFEEDFACE, 0xFEEDFACF) or be_magic in (0xFEEDFACE, 0xFEEDFACF):
        return "Mach-O"
    if be_magic in _FAT_MAGIC:
        return "Fat Mach-O"
    return None


def parse_binary(data: bytes) -> dict:
    """Parse raw file bytes and return a format report dict.

    Raises ValueError with a human-readable message on unrecognized or
    truncated files.
    """
    if not data:
        raise ValueError("empty file")
    kind = detect_format(data)
    if kind == "ELF":
        return _parse_elf(data)
    if kind == "PE":
        return _parse_pe(data)
    if kind == "Mach-O":
        return _parse_macho_slice(data)
    if kind == "Fat Mach-O":
        return _parse_fat_macho(data)
    raise ValueError("unrecognized file format (expected ELF, PE or Mach-O)")
