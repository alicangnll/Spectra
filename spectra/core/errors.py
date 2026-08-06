"""Core error classes for Spectra."""


class SpectraError(Exception):
    """Base exception for all Spectra errors."""

    pass


class ProviderError(SpectraError):
    """Exception raised for LLM provider errors."""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        retryable: bool = False,
        retry_after: float = 0.0,
        status_code: int = 0,
    ):
        self.provider = provider
        self.message = message
        self.retryable = retryable
        self.retry_after = retry_after
        self.status_code = status_code
        super().__init__(f"[{provider}] {message}")


class AuthenticationError(ProviderError):
    """Exception raised for authentication failures."""

    def __init__(self, message: str = "Authentication failed", provider: str = "unknown"):
        super().__init__(message, provider, status_code=401)


class RateLimitError(ProviderError):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", provider: str = "unknown", retry_after: float = 5.0):
        super().__init__(message, provider, status_code=429, retryable=True, retry_after=retry_after)


class ContextLengthError(ProviderError):
    """Exception raised when context length is exceeded."""

    def __init__(self, message: str = "Context length exceeded", provider: str = "unknown"):
        super().__init__(message, provider, status_code=400)


class ConfigurationError(SpectraError):
    """Exception raised for configuration errors."""

    pass


# Alias for backwards compatibility
ConfigError = ConfigurationError


class ToolExecutionError(SpectraError):
    """Exception raised when tool execution fails."""

    pass


class ToolError(SpectraError):
    """Exception raised when a tool encounters an error.

    This is the base class for all tool-related errors.
    """

    def __init__(self, message: str, tool_name: str = "unknown"):
        self.tool_name = tool_name
        self.message = message
        super().__init__(f"[{tool_name}] {message}")


class ToolNotFoundError(ToolError):
    """Exception raised when a tool is not found."""

    pass


class ToolValidationError(ToolError):
    """Exception raised when tool validation fails."""

    pass


class SkillError(SpectraError):
    """Exception raised when a skill encounters an error."""

    pass


class AgentError(SpectraError):
    """Exception raised when the agent encounters an error."""

    pass


class CancellationError(AgentError):
    """Exception raised when agent operation is cancelled."""

    pass


class SessionError(AgentError):
    """Exception raised when session management fails."""

    pass


class UIError(SpectraError):
    """Exception raised when UI operation fails."""

    pass


class MCPError(SpectraError):
    """Exception raised when MCP (Model Context Protocol) operation fails."""

    pass


class MCPConnectionError(MCPError):
    """Exception raised when MCP connection fails."""

    pass


class MCPTimeoutError(MCPError):
    """Exception raised when MCP operation times out."""

    pass
