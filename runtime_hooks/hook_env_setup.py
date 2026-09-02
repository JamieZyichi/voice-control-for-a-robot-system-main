# ============================================================================
# Runtime Hook: Environment Setup for Voice Control
# ============================================================================
"""
Sets up environment variables and paths for the packaged application.
- Chooses a persistent, writable cache directory
- Decides offline/online mode for model downloads based on availability
- Copies default external config/assets (JSON, PNG) next to the executable on first run
"""

import sys
import os
import shutil
from pathlib import Path


def _copy_if_missing(src: Path, dst: Path):
    try:
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"[HOOK] Copied {src.name} -> {dst}")
    except Exception as e:
        print(f"[HOOK] Copy failed for {src} -> {dst}: {e}")


def _setup_environment():
    """Setup runtime environment"""
    try:
        # Determine if running from packaged exe
        if getattr(sys, 'frozen', False):
            # Running from PyInstaller bundle
            bundle_path = Path(sys._MEIPASS)
            exe_dir = Path(sys.executable).parent
            print(f"[HOOK] Running from bundle: {bundle_path}")
            print(f"[HOOK] Executable dir: {exe_dir}")

            # Ensure external, user-editable resources exist next to the EXE
            for name in ("commands_hotwords.json", "tts_config.json", "NTU.PNG"):
                _copy_if_missing(bundle_path / name, exe_dir / name)

            # Set cache directories to a persistent, writable location
            appdata = Path(os.environ.get('APPDATA', exe_dir)) / 'voice_control_cache'
            appdata.mkdir(parents=True, exist_ok=True)
            os.environ['HF_HOME'] = str(appdata)

            # Determine offline/online mode:
            # If local_models folder exists next to the EXE and is non-empty, prefer offline
            local_models = exe_dir / 'local_models'
            offline = local_models.exists() and any(local_models.iterdir())
            if offline:
                os.environ['HF_HUB_OFFLINE'] = '1'
                os.environ['TRANSFORMERS_OFFLINE'] = '1'
                print(f"[HOOK] Offline mode enabled (local_models found)")
            else:
                # Allow online download on first run
                os.environ.pop('HF_HUB_OFFLINE', None)
                os.environ.pop('TRANSFORMERS_OFFLINE', None)
                print("[HOOK] Online mode enabled (models will download if needed)")

            print("[HOOK] Environment configured for packaged execution")
        else:
            print("[HOOK] Running in development mode")
    except Exception as e:
        print(f"[HOOK] WARNING: Environment setup failed: {e}")


# Execute setup
_setup_environment()
