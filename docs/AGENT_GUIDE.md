# Spectra Agent Addition Guide

There are 3 main ways to add new agents to Spectra:

## 1. Creating a New Skill (Easiest)

Skills actually act as agents. You can add a new agent by creating a new skill.

### Skill Structure:

```
my-custom-agent/
├── skill.md           # Agent definition and instructions
└── (optional)         # Additional files (if any)
```

### Example: Creating a New Agent

```bash
# 1. Create new skill directory
cd /path/to/Spectra/spectra/skills/builtins
mkdir my-custom-agent
cd my-custom-agent

# 2. Create skill.md
cat > skill.md << 'EOF'
---
name: My Custom Agent
description: Custom analysis agent - specialized in a specific field
tags: [custom, analysis, specialized]
mode: plan
---
Task: This agent performs X analysis.

## Approach
- Step 1: ...
- Step 2: ...
- Step 3: ...

## Tools Used
- tool_name_1
- tool_name_2

## Workflow
1. tool_name_1 → ...
2. tool_name_2 → ...
3. ...

## Expected Output
- ...
EOF
```

### 3. Save the Skill

```bash
# Skill is loaded automatically
# Spectra discovers the skill on next launch
```

### 4. Using in IDA Pro

```
// In Spectra panel (Ctrl+Shift+I)
/my-custom-analyze

// Or automatically
/my-custom-analyze this function
```

## 2. Copying and Modifying an Existing Skill

Copy an existing skill and modify it according to your needs.

### Example: Customizing Vuln-Audit Skill

```bash
# 1. Copy vuln-audit skill
cd /path/to/Spectra/spectra/skills/builtins
cp -r vuln-audit my-vuln-audit
cd my-vuln-audit

# 2. Edit skill.md
nano skill.md

# 3. New name and description
---
name: My Vulnerability Audit
description: Custom vulnerability scan
tags: [security, vuln-audit, custom]
mode: plan
---
Task: This custom vulnerability audit agent does:
- Search for stack overflow
- Search for heap overflow
- SQL injection scan
- XSS scan

## Approach
...
```

### 4. Save the Skill

Skill is loaded automatically, no special registration needed.

## 3. Adding A2A (Agent-to-Agent) Agents

Integrate agents outside of Spectra into Spectra.

### Configuration File:

```json
// ~/.idapro/spectra/config.json
{
  "a2a_agents": [
    {
      "name": "Ghidra Agent",
      "type": "external",
      "endpoint": "http://localhost:8080/agent",
      "api_key": "ghidra-api-key",
      "capabilities": ["decompile", "analyze", "disassemble"]
    },
    {
      "name": "Binary Ninja Cloud Agent",
      "type": "external",
      "endpoint": "https://api.binary.ninja.com/v1/agent",
      "api_key": "bn-api-key",
      "capabilities": ["lift", "analyze", "decompile"]
    }
  ]
}
```

### Usage:

```
// In Spectra panel
/ask Ghidra Agent: Decompile this function at 0x401000

// Automatic routing
Spectra routes the task to external agent
```

## 4. Writing Custom Agent Handler (Advanced)

You can write custom agent handlers with Python code.

### Agent Handler Example:

```python
# /path/to/Spectra/spectra/agents/custom_agent.py

from typing import Any, Dict
from ..agent.base import AgentHandler

class CustomAnalyzerAgent(AgentHandler):
    """Custom analysis agent handler."""

    def __init__(self):
        super().__init__()
        self.name = "Custom Analyzer"
        self.version = "1.0.0"

    def can_handle(self, task: str) -> bool:
        """Can this agent handle the task?"""
        keywords = ["analyze", "scan", "examine"]
        return any(keyword in task.lower() for keyword in keywords)

    def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the task."""

        # 1. Analyze the task
        analysis_result = self._analyze_task(task)

        # 2. Use IDA API
        results = []
        for address in analysis_result["addresses"]:
            result = self._analyze_address(address)
            results.append(result)

        # 3. Return results
        return {
            "agent": self.name,
            "task": task,
            "results": results,
            "status": "completed"
        }

    def _analyze_task(self, task: str) -> Dict[str, Any]:
        """Analyze the task."""
        # Extract addresses from task
        import re
        addresses = re.findall(r'0x[0-9a-fA-F]+', task)
        return {"addresses": addresses}

    def _analyze_address(self, address: int) -> Dict[str, Any]:
        """Analyze address."""
        # Use IDA API
        try:
            import idaapi
            func_name = idaapi.get_func_name(address)
            return {
                "address": address,
                "function": func_name,
                "analysis": "manual review needed"
            }
        except:
            return {
                "address": address,
                "error": "Failed to analyze"
            }
```

### Registering the Agent:

```python
# /path/to/Spectra/spectra/agents/__init__.py

from .custom_agent import CustomAnalyzerAgent

# Register agent
AGENT_REGISTRY.register(CustomAnalyzerAgent)
```

## 5. Defining Subagents (For Exploration Mode)

You can define subagents used in exploration mode.

```python
# /path/to/Spectra/spectra/agents/subagents.py

from typing import Any, Dict

class FunctionAnalyzerSubagent:
    """Function analysis subagent."""

    def analyze_functions(self, addresses: list[int]) -> Dict[str, Any]:
        """Analyze functions."""
        results = {}

        for addr in addresses:
            try:
                # Use IDA API for analysis
                import idaapi
                func = idaapi.get_func(addr)
                results[addr] = {
                    "name": func.get_name(),
                    "size": func.get_size(),
                    "bounds": func.get_bounds()
                }
            except:
                results[addr] = {"error": "Failed to analyze"}

        return results
```

## 6. Most Practical: Quick Agent Creation

### Template Skill File:

```markdown
---
name: Quick Analysis Agent
description: Automatic and fast binary analysis
tags: [fast, analysis, automated]
mode: auto
---
Task: This agent analyzes binary quickly.

## Auto-Analysis Workflow
1. `get_binary_info` → get general info
2. `list_imports` → scan imports
3. `list_exports` → scan exports
4. `search_functions` → find critical functions
5. Create auto-report

## Speed Optimization
- Do parallel analysis
- Focus only on critical areas
- Don't follow deep recursion

## Quick Report
- Summary analysis result
- Risk scores
- Recommended next steps
```

## 7. Agent Testing

### Test Command:

```bash
# Test agent
cd /path/to/Spectra
python -m pytest tests/agent/test_agent.py -v

# Test specific skill
python -m pytest tests/tools/test_skills.py::test_my_custom_agent -v
```

### Testing in IDA Pro:

```
// In Spectra panel
/test-agent my-custom-agent "Analyze 0x401000"
```

## 8. Agent Management

### View Active Agents:

```
// In Spectra panel
/agents list

// Output:
Active Agents: 3
- Main Orchestrator
- Function Analyzer (0x401000)
- String Searcher
```

### Control Agents:

```
/agents pause          // Stop all agents
/agents resume         // Resume agents
/agents stop           // Stop all agents
```

## 9. Agent Configuration

### Adjust Agent Behavior:

```json
// ~/.idapro/spectra/config.json
{
  "exploration_turn_limit": 100,    // Stop after how many turns
  "max_concurrent_agents": 5,      // Maximum parallel agents
  "agent_timeout": 300,          // Agent timeout (seconds)
  "subagent_auto_cleanup": true  // Auto cleanup completed agents
}
```

## 10. Example: Cryptographic Analysis Agent

### Crypto Analysis Skill:

```markdown
---
name: Crypto Analyst
description: Cryptographic primitive and algorithm analysis
tags: [crypto, encryption, analysis]
mode: plan
---
Task: This agent analyzes cryptographic usage in binary.

## Crypto Patterns
- Block cipher usage (AES, DES)
- Stream cipher usage (RC4, ChaCha20)
- Hash function usage (SHA-1, SHA-256, MD5)
- Public key cryptography (RSA, ECC)
- Random number generation

## Detection Methods
1. API detection: CryptEncrypt, CryptDecrypt, etc.
2. Constant key detection
3. Mode and padding detection
4. Key length analysis

## Analysis Workflow
1. `search_functions` → find crypto functions
2. `decompile_function` → analyze each function
3. Constant scan → search for keys and IVs
4. Cross-reference → find crypto usage areas
```

### Usage:

```
// In IDA Pro
/crypto Analyze encryption usage in this binary

// Automatic
/crypto Find all AES-256 implementations
```

## Summary: Which Method to Use When?

| Method | Difficulty | Flexibility | Use Case |
|--------|------------|-------------|----------|
| **Skill Creation** | Easy | High | Custom analysis needs |
| **Skill Copying** | Very Easy | Medium | Customizing existing agent |
| **A2A Agent** | Medium | Low | External tool integration |
| **Custom Handler** | Hard | Very High | Full control, advanced |

**Recommendation for beginners:** First copy and modify an existing skill, then create your own skill.

**Documentation:**
- Skill writing: Look at skill.md files in `/path/to/Spectra/spectra/skills/builtins/`
- Agent API: Examine modules in `/path/to/Spectra/spectra/agent/`
- Test examples: Look at test files in `/path/to/Spectra/tests/agent/`
