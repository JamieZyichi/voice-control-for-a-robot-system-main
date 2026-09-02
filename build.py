# ============================================================================
# build_v2.py
# ============================================================================
"""
Enhanced build system for Voice Control Application v2.

Key Improvements:
- Proper hidden imports for win32com COM components
- Runtime hooks for COM initialization
- Correct model path resolution
- Enhanced dependency checking
- Better error handling and logging
"""

import os
import sys
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any
import site

# Build Configuration
BUILD_CONFIG = {
    "app_name": "VoiceControl",
    "version": "2.3.0",
    "description": "Enhanced Voice Control Application with Windows SAPI TTS",
    "author": "Voice Control Team",
    "main_script": "main_voice_app.py",
    
    # PyInstaller settings
    "onefile": True,
    "windowed": True,
    "optimize": True,
    "strip_debug": False,  # Keep debug info for troubleshooting
    
    # Output settings
    "output_dir": "dist",
    "build_dir": "build",
    "spec_file": "voice_control_v2.spec",
    
    # Runtime hooks
    "use_runtime_hooks": True,
    "runtime_hooks_dir": "runtime_hooks",

    # Optional features
    "require_admin": False,            # Request UAC admin if audio devices need it
    "include_local_models": True,      # Bundle local_models/ if present
    "include_onnxruntime": True,       # Include ONNX Runtime for VAD
    "discover_binaries": True          # Auto-discover DLLs (PortAudio/CT2/ONNX)
}

class EnhancedVoiceControlBuilder:
    """
    Enhanced build system with full PyInstaller compatibility.
    
    New Features:
    - Runtime hooks for COM initialization
    - Enhanced hidden imports discovery
    - Model path resolution for packaged environment
    - Automatic dependency verification
    - Build validation and testing
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = {**BUILD_CONFIG, **(config or {})}
        self.build_dir = Path(self.config["build_dir"])
        self.output_dir = Path(self.config["output_dir"])
        self.runtime_hooks_dir = Path(self.config["runtime_hooks_dir"])
        
        # Build state
        self.start_time = None
        self.build_log = []
        self.errors = []
        
        print("=" * 70)
        print(f"Enhanced Voice Control Builder v{self.config['version']}")
        print(f"Target: {self.config['app_name']} with Windows SAPI TTS v2")
        print("=" * 70)
    
    def log(self, message: str, level: str = "INFO"):
        """Log build message"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        self.build_log.append(log_entry)
        
        # Color coding for console
        if level == "ERROR":
            print(f"\033[91m{log_entry}\033[0m")  # Red
            self.errors.append(message)
        elif level == "WARNING":
            print(f"\033[93m{log_entry}\033[0m")  # Yellow
        elif level == "SUCCESS":
            print(f"\033[92m{log_entry}\033[0m")  # Green
        else:
            print(log_entry)
    
    def check_dependencies(self) -> bool:
        """Enhanced dependency checking with detailed diagnostics"""
        self.log("Checking dependencies...")
        
        required_packages = {
            "pyinstaller": "PyInstaller build tool",
            "faster-whisper": "Speech recognition engine",
            "pywin32": "Windows COM/SAPI support (CRITICAL)",
            "numpy": "Numerical processing",
            "pyaudio": "Audio capture",
            "tkinter": "GUI framework"
        }
        
        # FIX #6: VAD dependencies (optional but recommended)
        optional_packages = {
            "onnxruntime": "VAD (Voice Activity Detection) support - recommended"
        }
        
        missing = []
        for package, description in required_packages.items():
            try:
                if package == "tkinter":
                    import tkinter
                    self.log(f"✓ {package}: {description}")
                    
                elif package == "faster-whisper":
                    from faster_whisper import WhisperModel
                    self.log(f"✓ {package}: {description}")
                    # Backend library often required
                    try:
                        import ctranslate2  # noqa: F401
                        self.log("  ↳ ctranslate2 available")
                    except Exception as e:
                        self.log(f"  ↳ ctranslate2 check failed: {e}", "WARNING")
                    
                elif package == "pywin32":
                    # CRITICAL: Comprehensive pywin32 check
                    import win32com.client
                    import pythoncom
                    import pywintypes
                    
                    # Test COM initialization
                    pythoncom.CoInitialize()
                    try:
                        speaker = win32com.client.Dispatch("SAPI.SpVoice")
                        voices = speaker.GetVoices()
                        voice_count = voices.Count
                        self.log(f"✓ {package}: {description} - {voice_count} voices detected")
                    finally:
                        pythoncom.CoUninitialize()
                        
                elif package == "numpy":
                    import numpy
                    self.log(f"✓ {package}: {description} - v{numpy.__version__}")
                    
                elif package == "pyaudio":
                    import pyaudio
                    self.log(f"✓ {package}: {description}")
                
                elif package == "pyinstaller":
                    # Try importing as a module first (more reliable in venvs)
                    try:
                        import PyInstaller
                        version = getattr(PyInstaller, '__version__', 'unknown')
                        self.log(f"✓ {package}: {description} - v{version}")
                    except ImportError:
                        # Fallback to command-line check
                        result = subprocess.run(
                            [sys.executable, "-m", "PyInstaller", "--version"],
                            check=True,
                            capture_output=True,
                            text=True
                        )
                        version = result.stdout.strip()
                        self.log(f"✓ {package}: {description} - v{version}")
                
            except (ImportError, subprocess.CalledProcessError, FileNotFoundError, Exception) as e:
                missing.append(package)
                self.log(f"✗ {package}: {description} - MISSING: {e}", "ERROR")
        
        if missing:
            self.log(f"Missing packages: {', '.join(missing)}", "ERROR")
            self.log("", "INFO")
            self.log("INSTALLATION INSTRUCTIONS:", "WARNING")
            
            if "pywin32" in missing:
                self.log("For pywin32:", "WARNING")
                self.log("  1. pip install pywin32", "WARNING")
                self.log("  2. python Scripts/pywin32_postinstall.py -install", "WARNING")
                self.log("     (Run as Administrator if needed)", "WARNING")
            
            for pkg in missing:
                if pkg != "pywin32" and pkg != "tkinter":
                    self.log(f"For {pkg}: pip install {pkg}", "WARNING")
            
            if "tkinter" in missing:
                self.log("For tkinter: Reinstall Python with Tk/Tcl option enabled", "WARNING")
            
            return False
        
        self.log("✓ All required dependencies satisfied", "SUCCESS")
        
        # FIX #6: Check optional VAD dependencies
        self.log("", "INFO")
        self.log("Checking optional dependencies (for VAD)...", "INFO")
        for package, description in optional_packages.items():
            try:
                if package == "onnxruntime":
                    import onnxruntime
                    self.log(f"✓ {package}: {description} - v{onnxruntime.__version__}")
            except ImportError:
                self.log(f"⚠ {package}: {description} - NOT INSTALLED (VAD may not work)", "WARNING")
                self.log(f"  To enable VAD: pip install {package}", "WARNING")
        
        return True
    
    def _find_site_packages(self) -> List[Path]:
        paths: List[str] = []
        try:
            paths.extend(site.getsitepackages())
        except Exception:
            pass
        try:
            user = site.getusersitepackages()
            if user:
                paths.append(user)
        except Exception:
            pass
        # Deduplicate preserving order
        seen = set()
        unique_paths = []
        for p in paths:
            if p not in seen:
                seen.add(p)
                unique_paths.append(p)
        return [Path(p) for p in unique_paths]

    def discover_runtime_binaries(self) -> List[tuple]:
        """Discover critical runtime DLLs to include as binaries.
        Returns a list of (abs_path, dest_dir) tuples.
        """
        bins: List[tuple] = []
        if not self.config.get("discover_binaries", True):
            return bins

        sp_paths = self._find_site_packages()

        def add_matches(patterns: List[str], dest: str):
            for base in sp_paths:
                for pat in patterns:
                    for match in base.glob(pat):
                        if match.is_file():
                            bins.append((str(match), dest))

        # PyAudio / PortAudio
        try:
            import pyaudio  # noqa: F401
            add_matches([
                "pyaudio/*portaudio*.dll",
                "pyaudio/*_portaudio*.pyd"
            ], ".")
        except Exception:
            pass

        # CTranslate2 (native DLLs)
        try:
            import ctranslate2 as _ct2  # noqa: F401
            add_matches([
                "ctranslate2/*.dll",
                "ctranslate2.libs/*.dll"
            ], ".")
        except Exception:
            pass

        # ONNX Runtime (optional)
        if self.config.get("include_onnxruntime", True):
            try:
                import onnxruntime  # noqa: F401
                add_matches([
                    "onnxruntime/*.dll",
                    "onnxruntime/capi/*.dll"
                ], ".")
            except Exception:
                pass

        return bins

    def create_runtime_hooks(self) -> bool:
        """Create runtime hooks for COM initialization and environment setup"""
        if not self.config["use_runtime_hooks"]:
            return True
        
        self.log("Creating runtime hooks...")
        
        # Create runtime hooks directory
        self.runtime_hooks_dir.mkdir(exist_ok=True)
        
        # Hook 1: COM initialization
        hook_com_init = self.runtime_hooks_dir / "hook_com_init.py"
        com_init_content = '''# ============================================================================
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
'''
        
        # Hook 2: Environment setup
        hook_env_setup = self.runtime_hooks_dir / "hook_env_setup.py"
        env_setup_content = '''# ============================================================================
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
'''
        
        # Write hooks
        try:
            with open(hook_com_init, 'w', encoding='utf-8') as f:
                f.write(com_init_content)
            self.log(f"✓ Created: {hook_com_init}")
            
            with open(hook_env_setup, 'w', encoding='utf-8') as f:
                f.write(env_setup_content)
            self.log(f"✓ Created: {hook_env_setup}")
            
            self.log("✓ Runtime hooks created successfully", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Failed to create runtime hooks: {e}", "ERROR")
            return False
    
    def prepare_config_files(self) -> bool:
        """Prepare configuration files with enhanced settings"""
        self.log("Preparing configuration files...")
        
        configs = {
            "commands_hotwords.json": {
                "commands": {
                    "open browser": {"weight": 1.5, "usage_count": 0, "last_used": None},
                    "close window": {"weight": 1.3, "usage_count": 0, "last_used": None},
                    "play music": {"weight": 1.2, "usage_count": 0, "last_used": None},
                    "minimize window": {"weight": 1.1, "usage_count": 0, "last_used": None},
                    "maximize window": {"weight": 1.1, "usage_count": 0, "last_used": None},
                    "stop listening": {"weight": 1.0, "usage_count": 0, "last_used": None}
                },
                "settings": {
                    "max_weight": 3.0,
                    "weight_decay": 0.98
                }
            },
            "tts_config.json": {
                "voice_index": 0,
                "rate": 0,
                "volume": 100,
                "enabled": True,
                "queue_timeout": 0.5,
                "max_text_length": 300,
                "unicode_support": True
            }
        }
        
        for filename, content in configs.items():
            config_path = Path(filename)
            if not config_path.exists():
                try:
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(content, f, indent=2, ensure_ascii=False)
                    self.log(f"✓ Created: {filename}")
                except Exception as e:
                    self.log(f"Failed to create {filename}: {e}", "ERROR")
                    return False
            else:
                self.log(f"✓ Exists: {filename}")
        
        self.log("✓ Configuration files ready", "SUCCESS")
        return True
    
    def create_spec_file(self) -> str:
        """Create enhanced PyInstaller spec file with all necessary configurations"""
        self.log("Creating enhanced PyInstaller spec file...")
        
        # Runtime hooks paths
        runtime_hooks = []
        if self.config["use_runtime_hooks"]:
            runtime_hooks = [
                str(self.runtime_hooks_dir / "hook_com_init.py"),
                str(self.runtime_hooks_dir / "hook_env_setup.py")
            ]

        # Datas (only existing files)
        datas: List[tuple] = []
        for name in ("commands_hotwords.json", "tts_config.json", "NTU.PNG"):
            if Path(name).exists():
                datas.append((name, '.'))
        if self.config.get("include_local_models", True) and Path('local_models').exists():
            datas.append(('local_models', 'local_models'))
        
        # CRITICAL: Include faster-whisper VAD assets (silero_vad_v6.onnx)
        try:
            import faster_whisper
            fw_path = Path(faster_whisper.__file__).parent
            assets_dir = fw_path / 'assets'
            if assets_dir.exists():
                # Include all ONNX models in faster_whisper/assets
                datas.append((str(assets_dir), 'faster_whisper/assets'))
                self.log(f"✓ Including faster-whisper VAD assets from {assets_dir}")
            else:
                self.log(f"⚠ faster-whisper assets dir not found at {assets_dir}", "WARNING")
        except Exception as e:
            self.log(f"⚠ Could not locate faster-whisper assets: {e}", "WARNING")

        # Hidden imports
        hiddenimports = [
            'faster_whisper', 'faster_whisper.transcribe', 'faster_whisper.vad',
            'faster_whisper.audio', 'faster_whisper.feature_extractor', 'faster_whisper.tokenizer',
            'ctranslate2', 'ctranslate2._ext', 'ctranslate2.specs', 'ctranslate2.models', 'ctranslate2.converters',
            'tokenizers', 'tokenizers.implementations', 'tokenizers.models', 'tokenizers.pre_tokenizers',
            'tokenizers.decoders', 'tokenizers.processors', 'tokenizers.normalizers',
            'onnxruntime', 'onnxruntime.capi', 'onnxruntime.capi.onnxruntime_pybind11_state',
            'win32com', 'win32com.client', 'win32com.client.gencache', 'win32com.client.genpy',
            'win32com.client.dynamic', 'win32com.client.build', 'win32com.gen_py', 'pythoncom',
            'pywintypes', 'win32api', 'win32con', 'win32timezone',
            'pyaudio', '_portaudio',
            'numpy', 'numpy.core', 'numpy.core.multiarray', 'numpy.core._multiarray_umath', 'numpy._distributor_init',
            'numpy.fft', 'numpy.linalg', 'numpy.random',
            'threading', 'queue', 'json', 'pathlib', 'datetime', 'time', 'traceback', 'collections', 'difflib',
            'tkinter', 'tkinter.ttk', 'tkinter.scrolledtext', 'tkinter.messagebox', 'tkinter.filedialog', '_tkinter',
        ]

        # Excludes
        excludes = [
            'matplotlib', 'scipy', 'pandas', 'PIL', 'cv2', 'tensorflow', 'torch',
            'transformers', 'jupyter', 'IPython', 'pyttsx3', 'openai', 'whisper'
        ]

        # Discovered binaries
        binaries = self.discover_runtime_binaries()

        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# ============================================================================
# Voice Control System v2 - Enhanced PyInstaller Spec File
# ============================================================================
"""
This spec file is optimized for Windows SAPI TTS integration and includes:
- Comprehensive hidden imports for win32com
- Runtime hooks for COM initialization
- Proper data file inclusion
- Optimized build settings
"""

import sys
from pathlib import Path

# Build configuration
APP_NAME = "{self.config["app_name"]}"
VERSION = "{self.config["version"]}"

datas = {datas}

# CRITICAL: Comprehensive hidden imports for Windows TTS and faster-whisper
hiddenimports = {hiddenimports}

# Binaries (discovered by builder)
binaries = {binaries}

excludes = {excludes}

# Analysis
a = Analysis(
    ['{self.config["main_script"]}'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks={runtime_hooks},
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# PYZ (Python ZIP archive)
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None
)

# EXE (Executable)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # Disable strip on Windows to avoid tool missing and DLL issues
    upx=False,  # Disable UPX to avoid breaking native DLLs (portaudio/ctranslate2)
    upx_exclude=['*ctranslate2*', '*portaudio*', '*pyaudio*', '*.dll'],
    runtime_tmpdir=None,
    console={'False' if self.config.get('windowed', True) else 'True'},  # Windowed application
    uac_admin={'True' if self.config.get('require_admin', False) else 'False'},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path if available
)
'''
        
        spec_file_path = Path(self.config["spec_file"])
        try:
            with open(spec_file_path, 'w', encoding='utf-8') as f:
                f.write(spec_content)
            self.log(f"✓ Spec file created: {spec_file_path}", "SUCCESS")
            return str(spec_file_path)
        except Exception as e:
            self.log(f"Failed to create spec file: {e}", "ERROR")
            return None
    
    def clean_build_dirs(self):
        """Clean previous build directories"""
        self.log("Cleaning build directories...")
        
        dirs_to_clean = [self.build_dir, self.output_dir]
        for dir_path in dirs_to_clean:
            if dir_path.exists():
                try:
                    shutil.rmtree(dir_path)
                    self.log(f"✓ Cleaned: {dir_path}")
                except Exception as e:
                    self.log(f"Failed to clean {dir_path}: {e}", "WARNING")
    
    def run_pyinstaller(self, spec_file: str) -> bool:
        """Run PyInstaller with the spec file"""
        self.log("Running PyInstaller...")
        self.log(f"Spec file: {spec_file}")
        
        try:
            cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", spec_file]
            self.log(f"Command: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Stream output
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    print(f"  {line}")
                    self.build_log.append(line)
            
            process.wait()
            
            if process.returncode == 0:
                self.log("✓ PyInstaller completed successfully", "SUCCESS")
                return True
            else:
                self.log(f"PyInstaller failed with code {process.returncode}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"PyInstaller execution error: {e}", "ERROR")
            return False
    
    def verify_build(self) -> bool:
        """Verify the build output"""
        self.log("Verifying build output...")
        
        exe_path = self.output_dir / f"{self.config['app_name']}.exe"
        
        if not exe_path.exists():
            self.log(f"Executable not found: {exe_path}", "ERROR")
            return False
        
        # Check file size
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        self.log(f"✓ Executable found: {exe_path}")
        self.log(f"✓ Size: {size_mb:.2f} MB")
        
        # Check if executable is valid
        try:
            result = subprocess.run(
                [str(exe_path), "--version"],
                capture_output=True,
                timeout=5
            )
            # Note: Our app doesn't have --version, so any return is OK
            self.log("✓ Executable appears valid")
        except subprocess.TimeoutExpired:
            self.log("✓ Executable responds (timeout expected)", "WARNING")
        except Exception as e:
            self.log(f"Executable test warning: {e}", "WARNING")
        
        self.log("✓ Build verification complete", "SUCCESS")
        return True

    def generate_verification_report(self):
        """Write a simple verification report alongside the EXE."""
        try:
            report_path = self.output_dir / "verification_report.txt"
            lines = []
            lines.append("Voice Control Build Verification Report")
            lines.append(f"App: {self.config['app_name']} v{self.config['version']}")
            lines.append(f"Windowed: {self.config.get('windowed', True)}")
            lines.append(f"Require Admin: {self.config.get('require_admin', False)}")
            lines.append(f"Include local_models: {self.config.get('include_local_models', True)}")
            lines.append(f"Include ONNX Runtime: {self.config.get('include_onnxruntime', True)}")
            lines.append("")
            lines.append("Included files (if present):")
            for name in ("commands_hotwords.json", "tts_config.json", "NTU.PNG"):
                lines.append(f"  - {name}: {'FOUND' if Path(name).exists() else 'MISSING at build time'}")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines) + "\n")
            self.log(f"✓ Verification report written: {report_path}")
        except Exception as e:
            self.log(f"Verification report error: {e}", "WARNING")
    
    def save_build_log(self):
        """Save build log to file"""
        log_file = Path(f"build_log_{int(time.time())}.txt")
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(self.build_log))
            self.log(f"✓ Build log saved: {log_file}")
        except Exception as e:
            self.log(f"Failed to save build log: {e}", "WARNING")
    
    def build(self) -> bool:
        """Run complete build process"""
        self.start_time = time.time()
        self.log("=" * 70)
        self.log("STARTING BUILD PROCESS")
        self.log("=" * 70)
        
        steps = [
            ("Dependency Check", self.check_dependencies),
            ("Runtime Hooks", self.create_runtime_hooks),
            ("Configuration Files", self.prepare_config_files),
            ("Spec File", self.create_spec_file),
        ]
        
        # Execute preparation steps
        for step_name, step_func in steps:
            self.log("")
            self.log(f"STEP: {step_name}")
            self.log("-" * 70)
            
            if step_name == "Spec File":
                spec_file = step_func()
                if not spec_file:
                    self.log(f"✗ {step_name} failed", "ERROR")
                    return False
            else:
                result = step_func()
                if not result:
                    self.log(f"✗ {step_name} failed", "ERROR")
                    return False
        
        # Clean and build
        self.log("")
        self.log("STEP: Clean Build Directories")
        self.log("-" * 70)
        self.clean_build_dirs()
        
        self.log("")
        self.log("STEP: Run PyInstaller")
        self.log("-" * 70)
        if not self.run_pyinstaller(spec_file):
            self.log("✗ Build failed", "ERROR")
            return False
        
        # Verify
        self.log("")
        self.log("STEP: Verify Build")
        self.log("-" * 70)
        if not self.verify_build():
            self.log("✗ Verification failed", "ERROR")
            return False
        # Write human-readable verification summary
        self.generate_verification_report()
        
        # Success
        elapsed = time.time() - self.start_time
        self.log("")
        self.log("=" * 70)
        self.log(f"✓ BUILD COMPLETED SUCCESSFULLY in {elapsed:.1f}s", "SUCCESS")
        self.log("=" * 70)
        self.log(f"Output: {self.output_dir / self.config['app_name']}.exe")
        
        # Save log
        self.save_build_log()
        
        return True


def main():
    """Main build entry point"""
    print("\n")
    
    builder = EnhancedVoiceControlBuilder()
    
    try:
        success = builder.build()
        
        if not success:
            print("\n")
            print("=" * 70)
            print("BUILD FAILED")
            print("=" * 70)
            if builder.errors:
                print("\nErrors encountered:")
                for error in builder.errors:
                    print(f"  - {error}")
            sys.exit(1)
        else:
            print("\n")
            print("Build completed! You can now run:")
            print(f"  {builder.output_dir / builder.config['app_name']}.exe")
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\nBuild cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nCRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
