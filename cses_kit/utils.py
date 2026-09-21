"""CLI and runtime utilities for cses-kit."""
from __future__ import annotations
import sys
import os
from typing import Optional, List, Dict, Any

def get_platform_info() -> Dict[str, Any]:
    """Return runtime platform metadata."""
    return {
        "platform": sys.platform,
        "python_version": sys.version.split()[0],
        "cwd": os.getcwd()
    }

def format_verdict(status: str, execution_time: Optional[float] = None) -> str:
    """Format test verdict string with optional execution duration."""
    time_str = f" ({execution_time:.3f}s)" if execution_time is not None else ""
    return f"[{status.upper()}]{time_str}"
