# Spectra Architecture Documentation

Complete technical reference for the Spectra reverse engineering agent system.

## Overview

Spectra is an AI-powered reverse engineering assistant that integrates directly into IDA Pro and Binary Ninja. It provides an agentic loop architecture with streaming responses, tool orchestration, and persistent memory.

## Core Architecture

### Agent Loop

The heart of Spectra is the generator-based agent loop implemented in `spectra/agent/loop.py`:

```python
def run(user_message: str) -> Generator[TurnEvent, None, None]:
    # 1. Parse commands and resolve skills
    # 2. Build system prompt with binary context
    # 3. Stream LLM response token-by-token
    # 4. Execute tool calls
    # 5. Feed results back to LLM
    # 6. Repeat until completion
```

### Turn Event System

Communication between the agent loop and UI uses `TurnEvent` objects:

- `TEXT_DELTA` - Streaming text tokens
- `TOOL_CALL_START` - Tool invocation begins
- `TOOL_RESULT` - Tool execution result
- `TURN_START` / `TURN_END` - Turn boundaries
- `ERROR` - Error conditions
- `MUTATION_RECORDED` - Database modification tracking

## Tool Framework

### Tool Definition

Tools are defined using the `@tool` decorator:

```python
@tool(category="functions", mutating=True)
def rename_function(old_name: str, new_name: str) -> str:
    """Rename a function in the database."""
    # Implementation
```

### Tool Registry

Central registry in `spectra/tools/registry.py` manages:
- Tool discovery and registration
- Parameter validation (required parameters checked before execution)
- Argument type coercion (LLM-friendly type conversion)
- Execution with timeout handling
- Reverse operation tracking for undo

### Parameter Validation

Before executing any tool, the registry validates that all required parameters are present:

```python
# Validate required parameters are present
missing = []
for param in defn.parameters:
    if param.required and param.name not in arguments:
        missing.append(param.name)
if missing:
    raise ToolValidationError(f"Tool {name} missing required parameters: {', '.join(missing)}")
```

This prevents cryptic TypeError messages and provides clear feedback to the LLM about which parameters are missing.

### Tool Categories

- **Navigation** - Movement and positioning
- **Functions** - Function analysis and manipulation
- **Strings** - String searching and extraction
- **Database** - Segment, import, export queries
- **Disassembly** - Assembly listing
- **Decompiler** - Pseudocode generation
- **Xrefs** - Cross-reference queries
- **Annotations** - Renaming and commenting
- **Types** - Structure and type manipulation
- **Scripting** - Python execution with approval

## Skills System

### Skill Format

Skills are Markdown files with YAML frontmatter:

```markdown
---
name: Malware Analysis
description: Windows PE malware analysis workflow
tags: [malware, windows]
allowed_tools: [decompile_function, list_imports, search_strings]
mode: exploration
---
Task: Analyze this binary as potential malware.
```

### Skill Activation

Commands starting with `/` trigger skills:
- `/malware-analysis` - Activate malware analysis skill
- `/deobfuscation` - Activate deobfuscation workflow
- `/modify <goal>` - Enter binary modification mode

### Built-in Skills

33 built-in skills covering:
- Memory corruption and exploitation
- Reverse engineering techniques
- Protocol analysis
- Cryptographic analysis
- Firmware RE
- Mobile app analysis
- Web application security
- CTF utilities

## Exploration Mode

### Four-Phase Flow

Exploration mode implements autonomous binary analysis:

1. **EXPLORE** - Map binary structure
2. **PLAN** - Synthesize modification plan
3. **EXECUTE** - Apply patches
4. **SAVE** - Persist changes

### Knowledge Base

Accumulates findings during exploration:
- `relevant_functions` - Discovered functions
- `findings` - Structured observations
- `hypotheses` - Inferred behaviors

### Subagents

Isolated agent instances for parallel analysis:
- Clean context windows
- Independent tool execution
- Result synthesis

## UI Layer

### Panel Architecture

Shared panel core in `spectra/ui/panel_core.py`:
- Chat interface with message history
- Tool execution display
- Mutation tracking panel
- Context bar with model info

### Event Polling

QTimer polls agent output at 50ms intervals:
- Dequeues events from background thread
- Routes to appropriate UI components
- Handles user interactions

### Session Management

Multi-tab sessions with:
- Independent conversation histories
- Token usage tracking
- Session persistence
- Fork and merge operations

## Provider Layer

### LLM Providers

Abstracted provider interface supporting:
- Anthropic Claude (with prompt caching)
- OpenAI-compatible APIs
- Google Gemini
- Ollama (local models)
- Custom endpoints

### Streaming Responses

Token-by-token streaming provides:
- Real-time feedback
- Progressive tool call display
- Early error detection

### Retry Logic

Automatic retry with exponential backoff:
- Rate limit handling
- Transient error recovery
- User notification during retries

## Context Management

### Window Management

Smart context window handling:
- Token counting and estimation
- Message compaction at 80% threshold
- Head and tail preservation
- Middle message summarization

### Persistent Memory

`SPECTRA.md` files store cross-session findings:
- Per-binary memory
- Automatic loading on startup
- Save via tool or explicit command

## Mutation Tracking

### Undo System

Every database modification is tracked:
- Pre-state capture
- Reverse operation generation
- Mutation log panel display
- Undo command support

### Reversible Operations

Supported mutations:
- Function renaming
- Variable renaming
- Comment setting
- Type modifications

Irreversible operations:
- `execute_python` scripts
- Binary patching

## Thread Safety

### IDA Pro Integration

All IDA API calls marshaled to main thread via `@idasync` decorator:
- Automatic thread switching
- Synchronous execution from background
- Safety for IDA's Python limitations

### Binary Ninja

Thread-safe API allows direct calls from background threads.

## MCP Integration

### Server Management

MCP server support provides:
- External tool integration
- Custom server configuration
- Health monitoring
- Tool schema bridging

### Configuration

`~/.spectra/mcp_servers.json` defines available servers and their toolsets.

## Performance Optimizations

### Prompt Caching

Anthropic-specific optimization:
- Cache control headers
- System prompt caching
- Reduced costs for long conversations

### Tool Batching

Parallel tool execution for independent operations:
- Multiple decompilation requests
- Batch xref queries
- Simultaneous renaming operations

### Result Truncation

Large tool results truncated to:
- Prevent context explosion
- Maintain token budget
- Preserve critical information

## Error Handling

### Exception Hierarchy

Structured error types:
- `AgentError` - Loop-level failures
- `CancellationError` - User cancellation
- `ProviderError` - LLM API issues
- `ToolError` - Tool execution failures
- `MCPError` - MCP protocol issues

### Consecutive Error Tracking

Three consecutive tool failures trigger:
- Temporary tool disabling
- Text-only fallback mode
- User notification

## Logging

### Multi-Output Logging

Logs written to:
- IDA output window (INFO level)
- Debug file (DEBUG level with fsync)
- Structured JSONL for machine parsing

### Log Locations

- `~/.spectra/spectra_debug.log` - Human-readable
- `~/.spectra/spectra_structured.jsonl` - Machine-parseable

## Security

### Python Execution

`execute_python` tool requires:
- Explicit user approval
- Code display before execution
- Per-approval caching
- Safety warnings

### Binary Safety

Agent explicitly prevented from:
- Running target binaries
- File system writes outside sandbox
- Network operations without approval

## Extension Points

### Custom Tools

Add tools by:
1. Creating function with `@tool` decorator
2. Adding to appropriate registry
3. Rebuilding tool list

### Custom Skills

Create skills by:
1. Creating Markdown file in skills directory
2. Adding YAML frontmatter
3. Implementing task instructions

### MCP Servers

Extend functionality via:
1. Configure server in `mcp_servers.json`
2. Server tools auto-registered
3. Available in all sessions

## Development Workflow

### Adding Features

1. Implement tool or skill
2. Add tests if needed
3. Update documentation
4. Submit pull request

### Debugging

Enable debug logging:
```bash
export SPECTRA_DEBUG=1
```

View logs in real-time:
```bash
tail -f ~/.spectra/spectra_debug.log
```

## Architecture Decisions

### Generator-Based Loop

Rationale:
- Enables streaming responses
- Simplifies event handling
- Supports cancellation
- Clean separation of concerns

### In-Process Tool Execution

Rationale:
- Zero latency for tool calls
- Direct database access
- No IPC overhead
- Thread-safe by design

### Persistent Memory Files

Rationale:
- Cross-session continuity
- Human-readable storage
- Easy to edit and review
- Git-trackable findings

---

For implementation details, see source code in `spectra/` directory.
For usage instructions, see [README.md](README.md).
