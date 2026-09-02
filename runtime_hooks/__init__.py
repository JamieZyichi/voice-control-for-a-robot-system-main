# ============================================================================
# Runtime Hooks for Voice Control System
# ============================================================================
"""
Runtime hooks for PyInstaller packaging.

These hooks are executed at application startup, before any user code runs.
They ensure proper environment setup for the packaged application.

Hooks:
1. hook_com_init.py - Initializes Windows COM for SAPI TTS
2. hook_env_setup.py - Sets up environment variables and paths

Usage in .spec file:
    runtime_hooks=['runtime_hooks/hook_com_init.py',
                   'runtime_hooks/hook_env_setup.py']
"""

__all__ = ['hook_com_init', 'hook_env_setup']
