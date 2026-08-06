# Spectra

<div align="center">
  <img src="img/logo.png" alt="Spectra Logo" width="200"/>
</div>

> **AI-Powered Reverse Engineering Agent** — An intelligent assistant that lives inside IDA Pro, Binary Ninja, and VSCode. Forked from [Rikugan](https://github.com/buzzer-re/Rikugan).

[Documentation](docs/USAGE.md) | [Architecture](docs/ARCHITECTURE.md) | [🇹🇷 Türkçe](docs_tr/README.md) | [Issues](https://github.com/alicangnll/Spectra/issues)

---

## Project Overview

Spectra is an **AI agent embedded in reverse engineering tools**. An assistant that works directly inside IDA Pro, Binary Ninja, and VSCode with support for multiple LLM providers.

**Forked from Rikugan** — Spectra is built on this powerful foundation and adds the following enhancements:
- **170+ tools** (IDA Pro + Binary Ninja)
- **39 built-in skills** (12 in Rikugan)
- **4 platforms** — IDA Pro, Binary Ninja, VSCode, JADX CLI
- **Advanced security analysis** — Exploitation, malware, firmware, mobile
- **JADX integration** — Android APK reverse engineering

---

## Spectra vs Rikugan

### Key Differences

| Feature | Rikugan | Spectra |
|---------|---------|---------|
| **Skills** | 12 built-in | 39 built-in |
| **Tools** | 60+ | 170+ |
| **Platforms** | IDA, Binary Ninja | IDA, Binary Ninja, VSCode, JADX |
| **Mobile Exploitation** | ❌ | ✅ iOS/Android PAC/MTE bypass |
| **APK Analysis** | ❌ | ✅ Full JADX integration |
| **Security Tools** | Basic | Advanced (Xref visualizer, smart naming) |
| **Type Recovery** | ❌ | ✅ Automatic detection |
| **Function Navigation** | ❌ | ✅ Clickable names/addresses |
| **Anti-Debug Detection** | ❌ | ✅ Automatic |
| **API Highlighting** | ❌ | ✅ MITRE ATT&CK labeled |
| **LPE Detection** | ❌ | ✅ Local privilege escalation |
| **RCE Detection** | ❌ | ✅ Remote code execution |
| **OWASP Top 10** | ❌ | ✅ Mobile + Web |
| **Driver Exploitation** | ❌ | ✅ Linux/macOS/Windows |
| **SSL Pinning Bypass** | ❌ | ✅ |
| **VM Obfuscation** | ❌ | ✅ Detection |
| **GLM Support** | ❌ | ✅ GLM-4 & GLM-5 series |

### Inherited Features (from Rikugan)

- **Generator-based agent loop** — Smooth responses
- **Automatic tool execution** — No manual intervention needed
- **Exploration mode** — Parallel subagent orchestration
- **Natural language patches** — Natural language patching with `/modify`
- **Deobfuscation** — Binary Ninja IL transformations
- **MCP integration** — Extensibility

### Added Features (Spectra)

- **39 security skills** — Exploitation, malware, firmware, mobile
- **VSCode extension** — Use outside RE tools
- **JADX CLI** — Android APK analysis
- **Xref Visualizer** — Interactive call graphs
- **Smart Function Naming** — AI-powered function naming
- **Type Library Auto-Detection** — Automatic type library detection
- **Findings Bookmarking** — Mark and export findings
- **Suspicious API Highlighting** — Highlight dangerous APIs
- **Anti-Debugging Detection** — Automatic anti-debug detection
- **Windows auto-install** — Automatic dependency installation

---

### Recommended Providers

*Prices as of 30.06.2026 — Input/Output per million tokens*

| Provider | Quality | Input | Output | Notes |
|----------|---------|-------|--------|-------|
| **Claude Opus 4.6** | ⭐⭐⭐⭐⭐ | $5.00 | $25.00 | Best overall, prompt caching, 1M ctx |
| **Claude Sonnet 4.6** | ⭐⭐⭐⭐ | $3.00 | $15.00 | Low cost, powerful, 1M ctx |
| **GLM-5.2** | ⭐⭐⭐⭐⭐ | $1.40 | $4.40 | 1M context, agentic engineering |
| **GLM-5** | ⭐⭐⭐⭐⭐ | $1.00 | $3.20 | Strong coding, complex systems |
| **GLM-5-Turbo** | ⭐⭐⭐⭐ | $1.20 | $4.00 | Fast, agent-optimized |
| **GLM-4-Plus** | ⭐⭐⭐⭐ | ¥5.00 (~$0.70) | ¥18.00 (~$2.50) | Reliable, 128K ctx |
| **GLM-4.7-Flash** | ⭐⭐⭐⭐ | $0.06 | $0.40 | Ultra-cheap, open source |
| **MiniMax M2.5** | ⭐⭐⭐⭐ | $0.30 | $1.20 | Generous limits, 197K ctx |
| **Gemini 3.1 Pro** | ⭐⭐⭐ | $2.00 | $12.00 | Good, more hallucinations |
| **Ollama (Local)** | ⭐⭐⭐ | — | — | Offline, model dependent |

---

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| **IDA Pro 9.0+** | ✅ Full | Requires Hex-Rays decompiler |
| **Binary Ninja 3164+** | ✅ Full | UI mode |
| **VSCode** | ✅ Full | Extension available |
| **JADX** | ✅ Full | APK analysis CLI |

---

## Installation

### Installation

**Auto-detects installed platforms:**

```bash
# Linux / macOS
curl -fsSL https://raw.githubusercontent.com/alicangnll/Spectra/main/install.sh | bash

# Windows (PowerShell)
irm https://raw.githubusercontent.com/alicangnll/Spectra/main/install.ps1 | iex
```

### Docker Installation

**Pull and run Spectra in a Docker container:**

```bash
# Build the image
./docker-build.sh

# Run interactively
./docker-run.sh

# Run with target directory
./docker-run.sh --target /path/to/code dir_loc /target

# Or use docker-compose
docker-compose up -d
docker-compose exec spectra-cli spectra_cli.py
```

**Docker Features:**
- **Isolated environment** — Clean Python 3.11 runtime
- **Persistent storage** — Volumes for sessions, skills, and logs
- **Easy deployment** — One-command build and run
- **Custom API** — Support for custom LLM endpoints
- **Target mounting** — Read-only mount for analysis targets

**Environment Variables:**
```bash
docker run -it \
  -e SPECTRA_API_KEY="sk-ant-xxx" \
  -e SPECTRA_PROVIDER="anthropic" \
  -e SPECTRA_MODEL="claude-sonnet-4-20250514" \
  -v spectra-data:/spectra/data \
  spectra
```

---

### Manual IDA Python Configuration (Linux / macOS)

> [!NOTE]
> The installer runs these steps automatically. Follow this section only if the auto-installer fails or if you need to reconfigure IDA's Python manually.

#### Why This Is Needed

IDA Pro ships with its **own embedded Python interpreter** — it does not use the system `python3` by default.
Packages installed via `pip3` are placed in the system Python's site-packages, which IDA cannot see unless both are configured to use the **same Python version**.

#### Step 1 — Check Which Python Version the System Uses

```bash
python3 --version
# Example output: Python 3.13.0
```

#### Step 2 — Run `idapyswitch` and Select the Matching Version

```bash
cd ~/ida-pro-9.1   # adjust to your IDA install directory
./idapyswitch
```

Example output:
```
The following Python installations were found:
    #0: 3.14.0 ('3.14') (/usr/lib/x86_64-linux-gnu/libpython3.14.so.1.0)
    #1: 3.13.0 ('3.13') (/usr/lib/x86_64-linux-gnu/libpython3.13.so.1.0)
Please pick a number between 0 and 1 (default: 0)
```

Select the entry that matches your `python3` version (e.g. type `1` for 3.13).

> [!IMPORTANT]
> Always pick the version that matches your system `python3` / `pip3`. Mismatching versions (e.g. IDA on 3.14, pip on 3.13) is the most common cause of "module not found" errors inside IDA.

#### Step 3 — Install `anthropic` for That Python Version

```bash
# Install for the selected Python version (e.g. 3.13)
python3 -m pip install --user anthropic>=0.39.0

# Verify it is installed
python3 -c "import anthropic; print(anthropic.__version__)"
```

#### Step 4 — Verify Inside IDA

Restart IDA Pro and open the Python console:
```python
import anthropic
print(anthropic.__version__)  # should print the installed version
```

If this still fails, check which site-packages path IDA's Python uses:
```python
import sys
for p in sys.path:
    print(p)
```
Then confirm that `~/.local/lib/pythonX.Y/site-packages` appears in that list.

#### Alternative: Install with `IDADIR` Override

You can also force the installer to use a specific IDA directory:
```bash
IDAPATH=/path/to/ida-pro-9.1 ./install_ida.sh
```

---


### 🤖 Agent Loop (Inherited from Rikugan)

**Generator-based turn cycle** for smooth responses:
- Real-time token streaming — See the AI think
- Automatic tool execution — No manual intervention
- Error recovery — Automatic recovery from errors
- Plan mode — Approval system for multi-step workflows
- Message queuing — Send follow-up messages while agent is running

### 🖥️ CLI Shell Interface (Spectra v1.4+)

**Claude-like interactive shell** for terminal-based analysis:
```bash
python spectra_cli.py dir_loc /path/to/target
```

**Features:**
- **39 built-in skills** — Access all security skills from CLI
- **170+ tools** — File operations, shell commands, code analysis
- **SSH integration** — Remote command execution, file transfer (SCP)
- **Session management** — Save/load analysis sessions
- **Plan/Research modes** — Structured analysis workflows
- **Collapse/Expand** — Press **Ctrl+O** to toggle tool result output
- **Interrupt AI** — Press **Ctrl+C** (when no text selected) or **Escape** to stop agent
- **Tab completion** — Categorized auto-complete (Skills, Config, Session, System)
- **Command history** — Persistent readline history (up/down arrows, Ctrl+R)
- **Multi-line input** — Use `\` to continue input on next line
- **Markdown rendering** — Tables, code blocks, syntax highlighting
- **Color output** — Syntax-highlighted results with color-coded events
- **Shell escape** — Execute shell commands with `!command`
- **Tool approval** — Safe execution with syntax-highlighted previews
- **Loading indicators** — Visual feedback during command execution (⏳)
- **File path display** — Tool calls show target file paths
- **Extended timeout** — 2-hour timeout for large codebase analysis (Linux kernel, etc.)
- **Auto-approve modes** — `/autolimit 0` for unlimited safe commands
- **Config commands** — Edit config via `/config_edit`, set API URL via `/apiurl`
- **LM Studio support** — Use local models via `/provider lmstudio`

**Keyboard Shortcuts:**
| Shortcut | Action |
|----------|--------|
| `Enter` | Submit message |
| `Shift+Enter` | New line |
| `Escape` | Cancel running AI |
| `Ctrl+C` | Cancel AI (no selection) / Copy text (selection) |
| `TAB` | Auto-complete commands (shows categories) |
| `Ctrl+O` | Toggle tool result collapse/expand |
| `Ctrl+R` | Search command history |

**Usage:**
```bash
spectra> /kernel-exploit        # Activate kernel exploitation skill
spectra> /vuln-audit            # Vulnerability assessment
spectra> /plan Analyze binary   # Plan mode for structured analysis
spectra> /save my-analysis      # Save session
spectra> /sessions              # List saved sessions
spectra> /autolimit 0           # Unlimited auto-approve (safe commands)
spectra> /provider lmstudio     # Use LM Studio (local LLM)
spectra> /apiurl http://localhost:1234/v1  # Set API URL
spectra> /config_edit           # Edit config in text editor
```

**Tab Completion Categories:**
```
spectra> /[TAB]

Skills:
  /0day-find  /ai-features  /android-exploit  ...

Config:
  /apikey  /apiurl  /autolimit  /config  /model  /provider  ...

Session:
  /load  /save  /sessions  /new

System:
  /help  /skills  /toggle
```

**Supported Providers:**
- `anthropic` — Claude API (Opus, Sonnet, Haiku)
- `openai` — OpenAI API (GPT-4, GPT-3.5)
- `gemini` — Google Gemini
- `ollama` — Local Ollama
- `glm` — Zhipu AI (GLM-4, GLM-5)
- `lmstudio` — LM Studio (local models)

### 🛠️ 170+ Tools

**IDA Pro (84 tools):**
- Navigation, decompilation, disassembly
- Cross-references, strings, imports, exports
- Annotations (rename, comment, set type)
- Microcode manipulation (Hex-Rays IL)
- Python scripting with approval

**Binary Ninja (86 tools):**
- Navigation, decompilation, HLIL
- Cross-references, strings, database queries
- IL read/write/transform
- Python scripting with approval

### 📚 39 Built-in Skills

**Exploitation & Security:**
- `memory-corruption` — UAF, OOB, PAC, ASLR, CFI, CET, MTE bypass
- `kernel-exploit` — SMEP/SMAP/KPTI bypass
- `rop-builder` — Automatic ROP chain building
- `race-condition` — TOCTOU exploitation
- `auto-exploit` — Automatic exploit generation
- `android-exploit` — Mobile exploitation techniques
- `ios-exploit` — ARM64 PAC bypass
- `lpe-detection` — Local privilege escalation
- `rce-detection` — Remote code execution

**Malware & Firmware:**
- `malware-analysis` — Classification, C2, config extraction
- `linux-malware` — Linux malware analysis
- `mobile-malware-analysis` — Mobile malware
- `firmware-re` — Extraction and analysis

**Analysis & Audit:**
- `vuln-audit` — Vulnerability assessment
- `reverse-engineering` — Binary analysis
- `protocol-analysis` — Network protocol RE
- `crypto-analysis` — Cryptographic algorithms
- `deobfuscation` — Control flow flattening removal (Binary Ninja)

**Mobile & Web:**
- `jadx-analysis` — Android APK analysis
- `mobile-pentest` — Mobile app assessment
- `owasp-mobile-top10` — OWASP Mobile Top 10
- `owasp-web-top10` — OWASP Web Top 10
- `ssl-pinning-bypass` — SSL pinning bypass
- `app-shielding-bypass` — App protection bypass

**Patching & Modification:**
- `modify` — Natural language binary patches
- `smart-patch-ida` — IDA patching workflow
- `smart-patch-binja` — Binary Ninja patching
- `shellcode-generator` — Payload generation

**CTF & Tools:**
- `ctf` — CTF competition utilities
- `ida-scripting` — IDAPython API reference
- `binja-scripting` — Binary Ninja Python API

### 🚀 Advanced Security Tools (v1.2.5+)

**Cross-Reference Visualizer**
- Interactive call graphs with complexity metrics
- Path finding between functions
- Dependency analysis

**Smart Function Naming**
- AI-powered pattern recognition
- Suggests meaningful names for `sub_XXX` functions
- Based on behavior analysis

**Type Library Auto-Detection**
- Automatically detects platform (Windows/Linux)
- Recovers structure definitions from type libraries

**Findings Bookmarking**
- Mark locations with categories (Critical, Suspicious, Verified, etc.)
- Export findings as markdown reports
- Persistent across sessions

**Suspicious API Highlighting**
- Color-coded dangerous APIs with MITRE ATT&CK references
- [CRIT] CreateRemoteThread, WriteProcessMemory, VirtualAllocEx
- [HIGH] VirtualProtect, GetProcAddress, LoadLibrary
- [MED] InternetConnect, socket, CryptEncrypt

**Anti-Debugging Detection**
- Windows API checks (IsDebuggerPresent, CheckRemoteDebuggerPresent)
- PEB BeingDebugged access patterns
- Assembly instructions (rdtsc, int 2d, int 3)

**Hex Address Navigation**
- All hex addresses become clickable (0x401000, 00401000, 401000h)
- Jump to location in disassembly view

**Function Name Navigation**
- CamelCase functions (generatePWFOTP) automatically linked
- snake_case functions (verify_password) linked
- Smart matching avoids common keywords

### 📱 JADX Integration (Spectra Exclusive)

**Android APK Analysis:**
```bash
# Analyze APK structure
python spectra_jadx.py analyze app.apk -o ./decompiled

# Search for strings
python spectra_jadx.py search app.apk "API_KEY"

# Analyze specific class
python spectra_jadx.py class app.apk com.example.MainActivity

# Interactive AI mode
python spectra_jadx.py interactive app.apk
```

**Features:**
- Automatic decompilation to Java source
- Manifest parsing (permissions, components, SDK)
- String search for API keys and endpoints
- Native library detection (.so files)
- Security assessment

---

### Access

| Platform | Shortcut | Menu Location |
|----------|---------|--------------|
| **IDA Pro** | `Ctrl+Shift+I` | Edit → Plugins → Spectra |
| **Binary Ninja** | `Ctrl+Shift+I` | Tools → Spectra → Open Chat |
| **VSCode** | `Ctrl+Shift+I` | Command Palette → "Spectra: Open Chat" |

### API Key Configuration

```bash
# Claude (Recommended)
export ANTHROPIC_API_KEY="sk-ant-..."

# OpenAI-compatible
export OPENAI_API_KEY="sk-..."

# Ollama (Local)
export OLLAMA_BASE_URL="http://localhost:11434"
```

---

## Requirements

- **Python 3.10+**
- **IDA Pro 9.0+** with Hex-Rays **OR** **Binary Ninja**
- **At least one LLM provider**
- **Windows, macOS, or Linux**

---

## Windows ARM64 Support

If you're using Windows ARM64 (e.g., Surface Pro X), IDA Pro runs under x64 emulation.

**Automatic Solution (v1.2.5+):**
```cmd
# Spectra automatically detects and installs missing dependencies
# Just launch IDA — you'll see:
[Spectra] Attempting auto-install...
[Spectra] anthropic installed successfully
```

If auto-install fails, see [docs/WINDOWS_ARM64_FIX.md](docs/WINDOWS_ARM64_FIX.md).

---

## Usage Examples

### Basic Analysis

```
User: Analyze this binary and find the main functionality
Spectra: [Explores binary, maps imports/exports, analyzes key functions]

User: What does the function at 0x401000 do?
Spectra: [Decompiles function, explains logic, identifies algorithms]
```

### Vulnerability Hunting

```
User: /skill memory-corruption
Spectra: [Activates skill, loads exploitation techniques]

User: Find OOB vulnerabilities and build RCE exploit
Spectra: [Scans for dangerous functions, finds bugs, builds chain]
```

### Mobile Exploitation

```
User: /skill ios-exploit
Spectra: [Activates iOS exploitation skill]

User: Analyze this binary for PAC bypass opportunities
Spectra: [Scans for pointer authentication violations]
Spectra: [Identifies PAC oracle gadgets and bypass strategies]
```

### APK Analysis

```
User: /jadx Analyze this APK
Spectra: [Decompiles APK with JADX]
Spectra: [Extracts manifest: permissions, activities, services]

User: Find the C2 server address
Spectra: [Searches decompiled sources for http:// patterns]
Spectra: [Found: hxxp://c2.example.com/api]
```

### Kernel Exploitation

```
User: /skill kernel-exploit
Spectra: [Activates kernel exploitation skill]

User: Check for SMEP/SMAP bypass
Spectra: [Scans for CR4 manipulation gadgets]
Spectra: [Identifies potential bypass techniques]
```

---

## Troubleshooting

**If plugin is not visible:**
```bash
spectra-doctor --check-install
spectra-install --force
```

**API connection issues:**
```bash
curl https://api.anthropic.com/v1/messages -H "x-api-key: $ANTHROPIC_API_KEY"
echo $HTTP_PROXY
```

**Performance issues:**
```bash
rm -rf ~/.spectra/cache/*
export SPECTRA_DEFAULT_MODEL="claude-sonnet-4-6"
```

---

## Development

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for setup instructions.

```bash
./ci-local.sh
python3 -m pytest tests/ -v
```

---

## Roadmap

**v1.3.x (Short term):**
- [ ] ML-based pattern recognition for deobfuscation
- [ ] Symbolic execution for automatic exploit generation
- [ ] Advanced kernel analysis capabilities

**v1.4.x (Medium term):**
- [ ] Multi-binary analysis workflow
- [ ] Collaborative analysis features
- [ ] Ghidra, Radare2 integration

---

## Contributing

Contributions are welcome! See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) and [docs/AGENTS.md](docs/AGENTS.md).

---

## Acknowledgments

- **[Rikugan](https://github.com/buzzer-re/Rikugan)** — buzzer-re's original project
- **Claude Code** — Amazing pair programmer
- **Anthropic** — Incredible AI models
- **Binary Ninja Team** — Excellent API and support
- **Hex-Rays** — IDA Pro and Hex-Rays decompiler
- **Community** — Feedback, testing, contributions

---

## License

MIT License — see [LICENSE](LICENSE) file.

---

## Disclaimer and Terms of Use

⚠️ **LEGAL WARNING AND TERMS OF USE**

By using Spectra, you agree to the following terms:

### 1. Educational and Research Purposes Only

Spectra is designed EXCLUSIVELY for:
• Authorized security testing and penetration testing
• Educational research and academic study
• Vulnerability disclosure programs (bug bounties)
• CTF (Capture The Flag) competitions
• Analysis of systems you OWN or have EXPLICIT PERMISSION to test

### 2. Prohibited Uses

Using Spectra for any of the following is STRICTLY PROHIBITED:
• Unauthorized access to computer systems (hacking without permission)
• Cyberattacks on systems you do not own or lack authorization
• Any illegal activity under applicable local, state, federal, or international law
• Violating terms of service of any platform or service
• Harassment, stalking, or any malicious activity

### 3. User Responsibility

By using Spectra, you agree that:
• YOU are solely responsible for your actions
• YOU must verify you have authorization before analyzing any system
• YOU must comply with all applicable laws and regulations
• The authors, contributors, and maintainers of Spectra are NOT liable
  for ANY misuse, damage, legal consequences, or illegal activities
  committed with this tool

### 4. Jurisdiction and Compliance

Laws vary by jurisdiction. It is YOUR responsibility to:
• Understand and comply with laws in your location
• Obtain necessary permissions before security testing
• Follow responsible disclosure practices for vulnerabilities found

Relevant laws may include (but are not limited to):
• Computer Fraud and Abuse Act (USA) / CFAA
• Computer Misuse Act (UK)
• GDPR, CCPA, and data protection laws
• Local cybersecurity and hacking laws
• International treaties and conventions

### 5. No Warranty

Spectra is provided "AS IS" without warranty of any kind. The authors
and contributors disclaim all warranties, express or implied, including
warranties of merchantability, fitness for a particular purpose, and
non-infringement.

### 6. Indemnification

By using Spectra, you agree to indemnify and hold harmless the authors,
contributors, and maintainers from any claims, damages, losses, liabilities,
legal fees, and expenses arising from your use or misuse of this software.

### 7. Age and Consent

You must be of legal age in your jurisdiction to use this software. By
using Spectra, you represent that you have the legal authority to agree
to these terms.

---

**If you do not agree to these terms, DO NOT use this software.**

---

**Made with passion by [Ali Can Gönüllü](https://github.com/alicangnll)**

*"The future of reverse engineering is automated, intelligent, and accessible to everyone."*
