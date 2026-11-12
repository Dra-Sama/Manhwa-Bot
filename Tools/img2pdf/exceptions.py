# Code By @V_Sbotmaker (on Telegram)
"""
Exceptions for the img2pdf pipeline.
"""

from __future__ import annotations

class PipelineError(Exception):
    """Base exception for all pipeline errors."""
    pass

class DownloadError(PipelineError):
    """Raised when a download fails."""
    pass

class ConversionError(PipelineError):
    """Raised when PDF conversion fails."""
    pass

class ValidationError(PipelineError):
    """Raised when validation of inputs or outputs fails."""
    pass

class SecurityError(PipelineError):
    """Raised for security-related issues (e.g., path traversal)."""
    pass

class ImageDownloadError(DownloadError):
    """Specific error for backward compatibility."""
    pass

__all__ = [
    "PipelineError",
    "DownloadError",
    "ConversionError",
    "ValidationError",
    "SecurityError",
]
