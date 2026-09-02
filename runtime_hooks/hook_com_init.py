# ============================================================================
# Runtime Hook: COM Initialization for Windows SAPI TTS
# ============================================================================
"""
CRITICAL: This hook ensures proper COM initialization in the packaged environment.
Without this, Windows TTS (SAPI) will fail with COM errors.
"""

import sys
import os

def _init_com():
    """Initialize COM for the application"""
    try:
        import pythoncom
        
        # Initialize COM for main thread
        pythoncom.CoInitialize()
        print("[HOOK] COM initialized successfully")
        
        # Register cleanup at exit
        import atexit
        def _cleanup_com():
            try:
                pythoncom.CoUninitialize()
                print("[HOOK] COM uninitialized")
            except:
                pass
        
        atexit.register(_cleanup_com)
        
    except Exception as e:
        print(f"[HOOK] WARNING: COM initialization failed: {e}")

# Execute initialization
_init_com()
