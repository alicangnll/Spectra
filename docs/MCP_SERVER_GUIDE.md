# MCP Server Guide for Spectra

> Complete guide to managing Model Context Protocol (MCP) servers in Spectra

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Understanding MCP Categories](#2-understanding-mcp-categories)
3. [Adding MCP Servers](#3-adding-mcp-servers)
4. [Managing Existing Servers](#4-managing-existing-servers)
5. [MCP Server Configuration](#5-mcp-server-configuration)
6. [Popular MCP Servers](#6-popular-mcp-servers)
7. [Troubleshooting](#7-troubleshooting)
8. [Security Considerations](#8-security-considerations)

---

## 1. Introduction

### 1.1 What are MCP Servers?

**MCP (Model Context Protocol)** servers extend Spectra's capabilities by providing external tools and data sources that the AI can use during analysis. Each MCP server offers specific functionality, such as:

- **Filesystem access** - Read/write files on your system
- **Database queries** - Query SQL databases
- **Web scraping** - Fetch and analyze web content
- **Code analysis** - Additional code understanding tools
- **Custom tools** - Your own specialized analysis capabilities

### 1.2 MCP Categories in Spectra

Spectra supports three categories of MCP servers:

| Category | Source | Description | Management |
|----------|--------|-------------|------------|
| **Spectra MCP Servers** | Manual configuration | Custom servers you configure | Fully manageable (add/remove/edit) |
| **Claude Code MCP Servers** | Auto-detected from Claude Code config | External servers discovered from Claude Code | Read-only (auto-detected) |
| **Codex MCP Servers** | Auto-detected from Codex config | External servers discovered from Codex | Read-only (auto-detected) |

---

## 2. Understanding MCP Categories

### 2.1 Spectra MCP Servers (Recommended)

These are MCP servers that you manually configure and manage within Spectra:

**✅ Advantages:**
- Full control over configuration
- Can add, remove, and edit servers
- Persistent across Spectra updates
- Works independently of other tools

**📝 When to use:**
- You want full control over MCP configuration
- You don't use Claude Code or Codex
- You need specific MCP servers not available elsewhere

### 2.2 Claude Code MCP Servers

These are automatically discovered from your Claude Code configuration:

**✅ Advantages:**
- No manual configuration needed
- Syncs with your Claude Code setup
- Automatically enables/disables with Claude Code

**📝 When to use:**
- You already use Claude Code with MCP servers
- You want consistency across tools
- You prefer auto-configuration

### 2.3 Codex MCP Servers

These are automatically discovered from Codex configuration:

**✅ Advantages:**
- Automatic discovery from Codex
- No manual setup required

**📝 When to use:**
- You use Codex with MCP integration
- You want shared configuration across tools

---

## 3. Adding MCP Servers

### 3.1 Accessing MCP Settings

1. **Open Spectra** in IDA Pro or Binary Ninja
2. Click the **⚙ Settings** button
3. Navigate to the **MCP** tab

### 3.2 Adding a Spectra MCP Server

#### Step 1: Click "+ Add Server"

You'll see the MCP server category selection dialog:

```
┌─────────────────────────────────────────┐
│  Select MCP Server Category             │
├─────────────────────────────────────────┤
│  Which type of MCP server do you want   │
│  to add?                                │
│                                         │
│  ◉ Spectra MCP Servers                  │
│    Custom MCP servers configured in     │
│    Spectra                               │
│                                         │
│  ○ Claude Code MCP Servers              │
│    External MCP servers from Claude     │
│    Code (read-only)                     │
│                                         │
│  ○ Codex MCP Servers                    │
│    External MCP servers from Codex      │
│    (read-only)                          │
│                                         │
│                    [Cancel]  [Next]    │
└─────────────────────────────────────────┘
```

#### Step 2: Select "Spectra MCP Servers"

#### Step 3: Fill in Server Details

The MCP Server configuration dialog will appear:

```
┌─────────────────────────────────────────┐
│  Add MCP Server                         │
├─────────────────────────────────────────┤
│  Server Name:     [________________]    │
│  Command:         [________________]    │
│  Arguments:       [________________]    │
│  Environment:     [________________]    │
│  Timeout:         [30 ▲] seconds       │
│                                         │
│                    [Cancel]  [Add]     │
└─────────────────────────────────────────┘
```

#### Step 4: Configure Server Parameters

| Field | Description | Example |
|-------|-------------|---------|
| **Server Name** | Unique identifier for the server | `filesystem`, `postgres`, `web-scraper` |
| **Command** | Executable command to start the server | `npx`, `uvx`, `python`, `/path/to/server` |
| **Arguments** | Command-line arguments for the server | `-y @modelcontextprotocol/server-filesystem` |
| **Environment** | Optional environment variables (KEY=value format) | `ALLOWED_PATHS=/tmp,/home/user/projects` |
| **Timeout** | Seconds to wait for server response | `30.0` |

---

## 4. Managing Existing Servers

### 4.1 Enabling/Disabling Servers

In the **MCP Settings** tab:

**For Spectra MCP Servers:**
- Use the checkboxes next to each server
- Changes apply immediately to new sessions

**For Claude Code / Codex Servers:**
- Use "Select All" / "Deselect All" buttons
- Individual server checkboxes enable/disable specific servers

### 4.2 Removing Spectra MCP Servers

Currently, server removal must be done manually:

1. Open your Spectra configuration file
2. Locate the MCP servers section
3. Remove the unwanted server entry
4. Restart Spectra

**Configuration location:**
- **macOS/Linux:** `~/.spectra/config.json`
- **Windows:** `%USERPROFILE%\.spectra\config.json`

---

## 5. MCP Server Configuration

### 5.1 Filesystem Server Example

**Server Name:** `filesystem-local`
**Command:** `npx`
**Arguments:** `-y @modelcontextprotocol/server-filesystem`
**Environment:** `ALLOWED_PATHS=/tmp,/home/user/projects,/Users/user/Desktop`

**What it does:** Allows Spectra to read and write files in specified directories.

### 5.2 PostgreSQL Server Example

**Server Name:** `postgres-prod`
**Command:** `uvx`
**Arguments:** `--from mcp-server-postgres mcp_server_postgres.server`
**Environment:** `POSTGRES_CONNECTION_STRING=postgresql://user:pass@localhost:5432/dbname`

**What it does:** Enables Spectra to query your PostgreSQL databases.

### 5.3 Web Scraper Server Example

**Server Name:** `web-fetcher`
**Command:** `python`
**Arguments:** `-m mcp_server_web`
**Environment:** `USER_AGENT=Spectra-Analysis/1.0`

**What it does:** Allows Spectra to fetch and analyze web content during analysis.

---

## 6. Popular MCP Servers

### 6.1 Official MCP Servers

| Server | Installation | Use Case |
|--------|--------------|----------|
| **@modelcontextprotocol/server-filesystem** | Built-in with Node.js | File system operations |
| **@modelcontextprotocol/server-github** | `npx @modelcontextprotocol/server-github` | GitHub repository integration |
| **@modelcontextprotocol/server-postgres** | `pip install mcp-server-postgres` | PostgreSQL database queries |
| **@modelcontextprotocol/server-puppeteer** | `npx @modelcontextprotocol/server-puppeteer` | Web automation and scraping |
| **@modelcontextprotocol/server-brave-search** | `npx @modelcontextprotocol/server-brave-search` | Web search capabilities |

### 6.2 Community MCP Servers

- **mcp-server-sqlite** - SQLite database integration
- **mcp-server-kubernetes** - Kubernetes cluster management
- **mcp-server-aws** - AWS service integration
- **mcp-server-git** - Git repository operations

---

## 7. Troubleshooting

### 7.1 Server Not Starting

**Problem:** Added MCP server doesn't appear in tools list

**Solutions:**
1. Check the command is installed on your system
2. Verify arguments are correctly formatted
3. Check environment variables are set correctly
4. Increase timeout value for slow servers
5. Check Spectra logs for error messages

### 7.2 Permission Errors

**Problem:** Server starts but can't access resources

**Solutions:**
1. Check environment variables for access controls
2. Verify file system permissions
3. Ensure database credentials are correct
4. Check network connectivity for remote servers

### 7.3 Timeout Issues

**Problem:** Server times out during operations

**Solutions:**
1. Increase timeout value in server configuration
2. Optimize server-side operations
3. Check for network latency
4. Reduce query complexity

### 7.4 Claude Code/Codex Servers Not Appearing

**Problem:** No external MCP servers detected

**Solutions:**
1. Verify Claude Code/Codex is properly configured
2. Check MCP configuration in those tools
3. Restart Spectra after configuring external tools
4. Ensure MCP servers are enabled in source tool

---

## 8. Security Considerations

### 8.1 File System Access

⚠️ **Warning:** MCP servers with filesystem access can read/write sensitive data

**Best Practices:**
- Always use `ALLOWED_PATHS` to restrict access
- Never allow access to system directories
- Use dedicated project directories
- Review server permissions regularly

### 8.2 Database Credentials

⚠️ **Warning:** Database passwords stored in configuration

**Best Practices:**
- Use read-only database users when possible
- Rotate credentials regularly
- Use environment variables instead of hardcoded values
- Consider using secrets management tools

### 8.3 Network Access

⚠️ **Warning:** MCP servers may make network requests

**Best Practices:**
- Review server code before installation
- Use firewalls to restrict access
- Monitor network traffic
- Only install from trusted sources

### 8.4 Code Execution

⚠️ **Warning:** Some MCP servers can execute arbitrary code

**Best Practices:**
- Only install servers from trusted sources
- Review server implementation
- Use sandboxed environments when possible
- Disable servers when not in use

---

## 9. Quick Reference

### 9.1 Common Commands

```bash
# Install Node.js based MCP server
npx -y @modelcontextprotocol/server-filesystem

# Install Python based MCP server
pip install mcp-server-postgres

# Install UV based MCP server
uvx mcp-server-postgres
```

### 9.2 Environment Variable Examples

```bash
# File server with path restrictions
ALLOWED_PATHS=/home/user/projects,/tmp

# Database connection
POSTGRES_CONNECTION_STRING=postgresql://user:pass@localhost/db

# Custom configuration
CUSTOM_VAR=value,ANOTHER_VAR=value2
```

### 9.3 Configuration File Format

```json
{
  "name": "my-server",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem"],
  "env": {
    "ALLOWED_PATHS": "/tmp,/home/user"
  },
  "timeout": 30.0,
  "enabled": true
}
```

---

## 10. Getting Help

### 10.1 Resources

- **Official MCP Documentation:** https://modelcontextprotocol.io
- **Spectra GitHub:** https://github.com/alicangnll/Spectra
- **MCP Server Repository:** https://github.com/modelcontextprotocol/servers

### 10.2 Community Support

- **GitHub Issues:** Report bugs and request features
- **Discussions:** Ask questions and share knowledge
- **Pull Requests:** Contribute improvements

---

## 11. Changelog

### Version 1.0 (2025-08-15)
- Initial MCP server guide
- Support for Spectra, Claude Code, and Codex MCP categories
- Detailed configuration examples
- Security best practices

---

**Last Updated:** August 15, 2026
