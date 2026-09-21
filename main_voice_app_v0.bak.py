# ============================================================================
# main_voice_app.py - Enhanced Voice Control Application (FIXED & DECOUPLED)
# ============================================================================

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import tkinter.font as tkfont
import os
import sys
import threading
import time
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List

# Import optimized core modules
try:
    from audio_engine_v2 import AudioEngine
    print("[INIT] Using enhanced AudioEngine")
except ImportError:
    from audio_engine import AudioEngine
    print("[INIT] Using standard AudioEngine")
    
from model_manager import SUPPORTED_MODELS

# ============================================================================
# UI Configuration
# ============================================================================

COLORS = {
    "bg": "#F8F9FA",
    "bg_dark": "#2C3E50", 
    "primary": "#4A90E2",
    "success": "#50C878",
    "danger": "#E74C3C",
    "warning": "#FF9800",
    "secondary": "#6C757D",
    "light": "#F8F9FA",
    "dark": "#343A40",
    "border": "#DEE2E6",
    "text": "#2C3E50"
}

FONTS = {
    "title": ("Segoe UI", 16, "bold"),  # Increased by 2pt for importance
    "body": ("Segoe UI", 11),  # Increased by 1pt
    "small": ("Segoe UI", 10),  # Increased by 1pt
    "mono": ("Consolas", 10)  # Increased by 1pt
}

# ============================================================================
# System Health Monitor (New Component for Error Isolation)
# ============================================================================

class SystemHealthMonitor:
    """
    Independent system health monitor
    Used to quickly locate issues and isolate errors
    """
    def __init__(self):
        self.components = {
            "audio_engine": {"status": "pending", "error": None},
            "model_manager": {"status": "pending", "error": None},
            "command_manager": {"status": "pending", "error": None},
            "tts_engine": {"status": "pending", "error": None},
            "model_loaded": {"status": "pending", "error": None}
        }
        self.init_start_time = time.time()
        self.init_complete = False
        
    def update_component(self, component: str, status: str, error: str = None):
        """Update component status"""
        if component in self.components:
            self.components[component]["status"] = status
            self.components[component]["error"] = error
            print(f"[HEALTH] {component}: {status}" + (f" - {error}" if error else ""))
    
    def get_failed_components(self) -> List[str]:
        """Get list of failed components"""
        return [name for name, info in self.components.items() 
                if info["status"] == "failed"]
    
    def is_system_ready(self) -> bool:
        """Check if system is fully ready"""
        critical = ["audio_engine", "model_manager", "model_loaded"]
        for comp in critical:
            if self.components[comp]["status"] != "ready":
                return False
        return True
    
    def get_status_report(self) -> str:
        """Generate detailed status report"""
        elapsed = time.time() - self.init_start_time
        report = f"=== SYSTEM INITIALIZATION REPORT ===\n"
        report += f"Elapsed Time: {elapsed:.2f}s\n"
        report += f"System Ready: {self.is_system_ready()}\n\n"
        
        for component, info in self.components.items():
            status = info["status"].upper()
            report += f"{component}: {status}\n"
            if info["error"]:
                report += f"  Error: {info["error"]}\n"
        
        failed = self.get_failed_components()
        if failed:
            report += f"\nFailed Components: {', '.join(failed)}\n"
        
        return report


# ============================================================================
# Main Application Class
# ============================================================================

class VoiceControlApp:
    
    def __init__(self, root):
        self.root = root
        self.root.title("Voice Control System")
        self.root.geometry("1000x750")
        self.root.configure(bg=COLORS["bg"])
        self.root.minsize(900, 650)
        
        # Health monitor (for error isolation)
        self.health_monitor = SystemHealthMonitor()
        
        # Application state
        self.audio_engine: Optional[AudioEngine] = None
        self.is_listening = False
        self.is_processing = False
        self.current_state = "Initializing"
        self.system_ready = False
        
        # Selected options
        self.selected_model = tk.StringVar(value="base")
        self.selected_voice = tk.StringVar(value="Default")
        self.available_voices = []
        
        # Logo state for dynamic height-based scaling
        self._logo_original = None  # PIL.Image.Image if available
        self.logo_photo = None      # Tk-compatible PhotoImage
        self.logo_label = None
        self._last_logo_height = 0

        # External config tracking (for JSON hot reload)
        self._commands_json_path = None
        self._commands_json_mtime = None
        
        # Thread management 
        self.recognition_thread = None
        self.stop_event = threading.Event()
        self.ui_update_thread = None
        
        # UI update queue (thread-safe)
        self.ui_updates = []
        self.ui_lock = threading.Lock()
        
        # Auto-refresh settings (FIX #4: Disable JSON monitoring in packaged builds)
        # JSON hot-reload should only work in development mode
        is_packaged = getattr(sys, 'frozen', False)
        self.auto_refresh_enabled = True
        self.enable_json_hot_reload = not is_packaged  # Disabled for .exe builds
        self.auto_refresh_interval = 5000  # 5 seconds
        
        # Build UI first
        print("[INIT] Building user interface...")
        self._build_ui()
        
        # Initialize system asynchronously
        print("[INIT] Starting asynchronous system initialization...")
        self._init_system_async()
        
        # Start UI update loop
        self._start_ui_updates()
        
        # Start auto-refresh timer
        if self.auto_refresh_enabled:
            self._start_auto_refresh()
        
        print("[INIT] VoiceControlApp initialized")
    
    def _build_ui(self):
        """Build the user interface"""
        
        # Header with logo (left), centered title (middle), status (right)
        header = tk.Frame(self.root, bg=COLORS["primary"])  # dynamic height based on content
        header.pack(fill=tk.X)

        # Use a 3-column grid to keep the title centered regardless of logo/status width
        header.grid_columnconfigure(0, weight=1)  # left spacer grows
        header.grid_columnconfigure(1, weight=0)  # center content
        header.grid_columnconfigure(2, weight=1)  # right spacer grows

        left_area = tk.Frame(header, bg=COLORS["primary"])
        center_area = tk.Frame(header, bg=COLORS["primary"])
        right_area = tk.Frame(header, bg=COLORS["primary"])

        left_area.grid(row=0, column=0, sticky="w", padx=10, pady=6)
        center_area.grid(row=0, column=1, pady=6)
        right_area.grid(row=0, column=2, sticky="e", padx=10, pady=6)

        # Compute target logo height based on title font height (1.3x)
        title_font = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        title_linespace = max(1, int(title_font.metrics("linespace")))
        target_logo_h = max(12, int(title_linespace * 1.3))

        # Initialize NTU logo with proportional scaling to target height
        self._init_logo_static(left_area, target_logo_h)

        # Title label (centered)
        title_label = tk.Label(center_area, text="Voice Control System",
                               font=title_font,
                               bg=COLORS["primary"], fg="white")
        title_label.pack()

        # Status indicator (right side)
        self.status_var = tk.StringVar(value="Initializing...")
        status_label = tk.Label(right_area, textvariable=self.status_var,
                                font=FONTS["body"], bg=COLORS["primary"], fg="white")
        status_label.pack(anchor="e")
        
        # Main content with tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.tab_listen = tk.Frame(notebook, bg=COLORS["bg"])
        notebook.add(self.tab_listen, text="Listen")
        
        self.tab_commands = tk.Frame(notebook, bg=COLORS["bg"])
        notebook.add(self.tab_commands, text="Commands")
        
        self.tab_training = tk.Frame(notebook, bg=COLORS["bg"])
        notebook.add(self.tab_training, text="Training")
        
        self.tab_system = tk.Frame(notebook, bg=COLORS["bg"])
        notebook.add(self.tab_system, text="System")
        
        # Build each tab
        self._build_listen_tab()
        self._build_commands_tab()
        self._build_training_tab()
        self._build_system_tab()

    def _init_logo(self, header: tk.Frame, left_area: tk.Frame):
        """Load the NTU logo and bind height-based scaling to the header size."""
        # Resolve logo file (case variations)
        logo_file = None
        for candidate in ["NTU.PNG", "NTU.png"]:
            if os.path.exists(candidate):
                logo_file = candidate
                break

        if not logo_file:
            print("[WARNING] NTU logo not found (NTU.PNG/NTU.png)")
            return

        # Try to load with PIL for high-quality scaling; fall back to Tk PhotoImage
        pil_image = None
        try:
            from PIL import Image  # type: ignore
            pil_image = Image.open(logo_file)
            self._logo_original = pil_image
        except Exception:
            self._logo_original = None
            try:
                self.logo_photo = tk.PhotoImage(file=logo_file)
            except Exception as e:
                print(f"[WARNING] Failed to load logo '{logo_file}': {e}")
                return

        # Create label now; actual sizing will occur on first <Configure>
        if self.logo_label is None:
            self.logo_label = tk.Label(left_area, bg=COLORS["primary"])
            self.logo_label.pack(anchor="w")

        # Bind to header size changes for dynamic height-based scaling
        def on_configure(event):
            self._resize_logo_to_height(event.height)

        # Ensure we don't bind multiple times
        header.bind("<Configure>", on_configure, add="+")

        # Trigger initial sizing after Tk lays out widgets
        self.root.after(0, lambda: self._resize_logo_to_height(header.winfo_height()))

    def _resize_logo_to_height(self, container_height: int):
        """Resize logo to match container height while preserving aspect ratio."""
        if container_height <= 0:
            return

        # Provide some vertical padding
        target_h = max(24, container_height - 12)
        if abs(target_h - self._last_logo_height) < 2:
            return  # skip trivial changes

        # If PIL is available and we have original image, do high-quality scale
        if self._logo_original is not None:
            try:
                from PIL import ImageTk, Image  # type: ignore
                orig_w, orig_h = self._logo_original.width, self._logo_original.height
                if orig_h <= 0:
                    return
                scale = target_h / float(orig_h)
                target_w = max(1, int(orig_w * scale))
                resized = self._logo_original.resize((target_w, target_h), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(resized)
                if self.logo_label:
                    self.logo_label.configure(image=self.logo_photo)
                self._last_logo_height = target_h
                return
            except Exception as e:
                print(f"[WARNING] PIL resize failed, falling back to Tk scaling: {e}")

        # Fallback: Tk PhotoImage with integer subsampling (downscale only)
        if isinstance(self.logo_photo, tk.PhotoImage):
            try:
                # Re-load original to avoid cumulative subsampling
                img = tk.PhotoImage(file="NTU.PNG") if os.path.exists("NTU.PNG") else tk.PhotoImage(file="NTU.png")
                h = img.height()
                if h > target_h:
                    factor = max(1, h // target_h)
                    img = img.subsample(factor)
                # If smaller than target, keep original size (no integer upscale to avoid distortion)
                self.logo_photo = img
                if self.logo_label:
                    self.logo_label.configure(image=self.logo_photo)
                self._last_logo_height = img.height()
            except Exception as e:
                print(f"[WARNING] Tk PhotoImage resize failed: {e}")

    def _init_logo_static(self, left_area: tk.Frame, target_h: int):
        """Load and place the NTU logo at a fixed target height, preserving aspect ratio.

        This avoids dynamic resizing and uses the precomputed target height
        (e.g., 1.3x the title font height).
        """
        # Resolve logo file
        logo_file = None
        for candidate in ["NTU.PNG", "NTU.png"]:
            if os.path.exists(candidate):
                logo_file = candidate
                break
        if not logo_file:
            print("[WARNING] NTU logo not found (NTU.PNG/NTU.png)")
            return

        # Try PIL for precise scaling
        try:
            from PIL import Image, ImageTk  # type: ignore
            img = Image.open(logo_file)
            orig_w, orig_h = img.width, img.height
            if orig_h <= 0:
                raise ValueError("Invalid image height")
            scale = float(target_h) / float(orig_h)
            target_w = max(1, int(orig_w * scale))
            resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(resized)
        except Exception:
            # Fallback to Tk PhotoImage (integer subsample only)
            try:
                base = tk.PhotoImage(file=logo_file)
                h = base.height()
                if h > target_h:
                    factor = max(1, h // max(1, target_h))
                    base = base.subsample(factor)
                # No good integer upscale available; keep as-is if smaller
                self.logo_photo = base
            except Exception as e:
                print(f"[WARNING] Failed to load logo statically: {e}")
                return

        # Create or update label
        if self.logo_label is None:
            self.logo_label = tk.Label(left_area, image=self.logo_photo, bg=COLORS["primary"])
            self.logo_label.pack(anchor="w")
        else:
            self.logo_label.configure(image=self.logo_photo)
    
    def _build_listen_tab(self):
        """Build the listening/recognition tab"""
        
        # Title
        tk.Label(self.tab_listen, text="Voice Recognition",
                font=("Segoe UI", 18, "bold"), bg=COLORS["bg"]).pack(pady=15)
        
        # Status display
        status_frame = tk.Frame(self.tab_listen, bg=COLORS["bg_dark"], relief=tk.RAISED, bd=2)
        status_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.detailed_status_var = tk.StringVar(value="System starting up...")
        status_label = tk.Label(status_frame, textvariable=self.detailed_status_var,
                               font=("Segoe UI", 12), bg=COLORS["bg_dark"], fg="white",
                               justify=tk.LEFT, wraplength=700, pady=15, padx=15)
        status_label.pack(fill=tk.X)
        
        # Control buttons
        btn_frame = tk.Frame(self.tab_listen, bg=COLORS["bg"])
        btn_frame.pack(pady=20)
        
        self.btn_start = tk.Button(btn_frame, text="Start Listening",
                                  font=("Segoe UI", 13, "bold"),
                                  bg=COLORS["success"], fg="white",
                                  width=15, height=2,
                                  command=self._start_listening,
                                  state=tk.DISABLED,
                                  relief=tk.FLAT, bd=0, cursor="hand2")
        self.btn_start.pack(side=tk.LEFT, padx=10)
        
        self.btn_stop = tk.Button(btn_frame, text="Stop Listening",
                                 font=("Segoe UI", 13, "bold"),
                                 bg=COLORS["danger"], fg="white",
                                 width=15, height=2,
                                 command=self._stop_listening,
                                 state=tk.DISABLED,
                                 relief=tk.FLAT, bd=0, cursor="hand2")
        self.btn_stop.pack(side=tk.LEFT, padx=10)
        
        # Results area
        result_frame = tk.LabelFrame(self.tab_listen, text="Activity Log",
                                    font=FONTS["body"], bg=COLORS["bg"])
        result_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.result_text = scrolledtext.ScrolledText(result_frame,
                                                    font=FONTS["mono"],
                                                    bg="white", height=15,
                                                    wrap=tk.WORD)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Clear button
        clear_btn = tk.Button(result_frame, text="Clear Log",
                             bg=COLORS["secondary"], fg="white",
                             relief=tk.FLAT, bd=0,
                             command=lambda: self.result_text.delete("1.0", tk.END))
        clear_btn.pack(pady=5)
    
    def _build_commands_tab(self):
        """Build the commands management tab"""
        
        tk.Label(self.tab_commands, text="Command Management",
                font=("Segoe UI", 18, "bold"), bg=COLORS["bg"]).pack(pady=15)
        
        # Add command section
        add_frame = tk.Frame(self.tab_commands, bg=COLORS["bg"])
        add_frame.pack(pady=10)
        
        tk.Label(add_frame, text="New Command:",
                font=FONTS["body"], bg=COLORS["bg"]).pack(side=tk.LEFT, padx=5)
        
        self.cmd_entry = tk.Entry(add_frame, font=FONTS["body"], width=30)
        self.cmd_entry.pack(side=tk.LEFT, padx=5)
        self.cmd_entry.bind("<Return>", lambda e: self._add_command())
        
        tk.Button(add_frame, text="Add Command",
                 bg=COLORS["success"], fg="white",
                 relief=tk.FLAT, bd=0,
                 command=self._add_command).pack(side=tk.LEFT, padx=5)
        
        # Commands list
        list_frame = tk.LabelFrame(self.tab_commands, text="Commands",
                                  font=FONTS["body"], bg=COLORS["bg"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Treeview for commands
        self.cmd_tree = ttk.Treeview(list_frame, columns=("Command", "Weight", "Usage"), 
                                    show="headings", height=15)
        self.cmd_tree.heading("Command", text="Command")
        self.cmd_tree.heading("Weight", text="Weight")
        self.cmd_tree.heading("Usage", text="Usage Count")
        
        self.cmd_tree.column("Command", width=300)
        self.cmd_tree.column("Weight", width=100)
        self.cmd_tree.column("Usage", width=100)
        
        self.cmd_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Command buttons
        cmd_btn_frame = tk.Frame(list_frame, bg=COLORS["bg"])
        cmd_btn_frame.pack(pady=5)
        
        tk.Button(cmd_btn_frame, text="Refresh",
                 bg=COLORS["primary"], fg="white",
                 relief=tk.FLAT, bd=0,
                 command=self._refresh_commands).pack(side=tk.LEFT, padx=5)
        
        tk.Button(cmd_btn_frame, text="Delete Selected",
                 bg=COLORS["danger"], fg="white",
                 relief=tk.FLAT, bd=0,
                 command=self._delete_command).pack(side=tk.LEFT, padx=5)
        
        tk.Button(cmd_btn_frame, text="Reload JSON",
                 bg=COLORS["warning"], fg="white",
                 relief=tk.FLAT, bd=0,
                 command=self._reload_commands_json).pack(side=tk.LEFT, padx=5)
    
    def _build_training_tab(self):
        """Build the training tab"""
        
        tk.Label(self.tab_training, text="Command Training",
                font=("Segoe UI", 18, "bold"), bg=COLORS["bg"]).pack(pady=15)
        
        # Training list
        train_frame = tk.LabelFrame(self.tab_training, text="Training Progress",
                                   font=FONTS["body"], bg=COLORS["bg"])
        train_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.train_tree = ttk.Treeview(train_frame,
                                      columns=("Command", "Count", "Weight"),
                                      show="headings", height=15)
        self.train_tree.heading("Command", text="Command")
        self.train_tree.heading("Count", text="Usage Count")
        self.train_tree.heading("Weight", text="Weight")
        
        self.train_tree.column("Command", width=300)
        self.train_tree.column("Count", width=120)
        self.train_tree.column("Weight", width=120)
        
        self.train_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Training buttons
        train_btn_frame = tk.Frame(train_frame, bg=COLORS["bg"])
        train_btn_frame.pack(pady=10)
        
        tk.Button(train_btn_frame, text="Refresh",
                 bg=COLORS["primary"], fg="white",
                 relief=tk.FLAT, bd=0,
                 command=self._refresh_training).pack(side=tk.LEFT, padx=5)
        
        tk.Button(train_btn_frame, text="Train Selected",
                 bg=COLORS["warning"], fg="white",
                 relief=tk.FLAT, bd=0,
                 command=self._train_command).pack(side=tk.LEFT, padx=5)
    
    def _build_system_tab(self):
        """Build the system monitoring tab"""
        
        tk.Label(self.tab_system, text="System Configuration",
                font=("Segoe UI", 18, "bold"), bg=COLORS["bg"]).pack(pady=15)
        
        # Configuration panel
        config_frame = tk.Frame(self.tab_system, bg="white", relief=tk.RAISED, bd=1)
        config_frame.pack(fill=tk.X, padx=20, pady=10)
        
        config_inner = tk.Frame(config_frame, bg="white")
        config_inner.pack(fill=tk.X, padx=15, pady=15)
        
        # Model selection
        tk.Label(config_inner, text="STT Model:", font=FONTS["body"], bg="white").grid(row=0, column=0, sticky="w")
        
        self.model_combo = ttk.Combobox(config_inner, textvariable=self.selected_model,
                                       values=list(SUPPORTED_MODELS.keys()),
                                       state="readonly", width=15)
        self.model_combo.grid(row=1, column=0, padx=(0, 15), pady=(5, 0), sticky="w")
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_change)
        
        # Voice selection
        tk.Label(config_inner, text="TTS Voice:", font=FONTS["body"], bg="white").grid(row=0, column=1, sticky="w")
        
        self.voice_combo = ttk.Combobox(config_inner, textvariable=self.selected_voice,
                                       values=["Default"], state="readonly", width=25)
        self.voice_combo.grid(row=1, column=1, padx=(15, 15), pady=(5, 0), sticky="w")
        self.voice_combo.bind("<<ComboboxSelected>>", self._on_voice_change)
        
        # Preview button
        tk.Button(config_inner, text="Test Voice", bg=COLORS["secondary"], fg="white",
                 relief=tk.FLAT, bd=0, command=self._test_voice).grid(row=1, column=2, padx=(15, 0), pady=(5, 0))
        
        # System status
        status_frame = tk.LabelFrame(self.tab_system, text="System Status",
                                    font=FONTS["body"], bg=COLORS["bg"])
        status_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.system_text = tk.Text(status_frame,
                                  font=FONTS["mono"],
                                  height=20, state=tk.DISABLED,
                                  bg="white")
        self.system_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # System buttons
        sys_btn_frame = tk.Frame(status_frame, bg=COLORS["bg"])
        sys_btn_frame.pack(pady=10)
        
        tk.Button(sys_btn_frame, text="Refresh Status",
                 bg=COLORS["primary"], fg="white",
                 relief=tk.FLAT, bd=0,
                 command=self._refresh_system_status).pack(side=tk.LEFT, padx=5)
        
        tk.Button(sys_btn_frame, text="Health Check",
                 bg=COLORS["success"], fg="white",
                 relief=tk.FLAT, bd=0,
                 command=self._show_health_report).pack(side=tk.LEFT, padx=5)
        
        tk.Button(sys_btn_frame, text="Save Log",
                 bg=COLORS["secondary"], fg="white",
                 relief=tk.FLAT, bd=0,
                 command=self._save_log).pack(side=tk.LEFT, padx=5)
    
    # ========================================================================
    # System Initialization (ENHANCED WITH HEALTH MONITORING)
    # ========================================================================
    
    def _init_system_async(self):
        """Enhanced asynchronous system initialization with health monitoring and error isolation"""
        def _init():
            try:
                self._queue_ui_update(lambda: self._update_status("Initializing..."))
                self._queue_ui_update(lambda: self._update_detailed_status("Step 1/5: Initializing audio engine..."))
                self._queue_ui_update(lambda: self._log("[INIT] Starting system initialization..."))
                
                # Step 1: Initialize Audio Engine (with error isolation)
                try:
                    print("[INIT] Step 1: Creating AudioEngine instance...")
                    self.audio_engine = AudioEngine()
                    self.health_monitor.update_component("audio_engine", "ready")
                    self._queue_ui_update(lambda: self._log("[OK] Audio engine created"))
                except Exception as e:
                    error_msg = f"Audio engine initialization failed: {e}"
                    self.health_monitor.update_component("audio_engine", "failed", str(e))
                    self._queue_ui_update(lambda: self._log(f"[ERROR] {error_msg}"))
                    print(f"[ERROR] {error_msg}")
                    traceback.print_exc()
                    self._handle_init_failure("Audio Engine")
                    return
                
                # Step 2: Wait for Model to Load (with timeout)
                self._queue_ui_update(lambda: self._update_detailed_status("Step 2/5: Loading speech recognition model..."))
                self._queue_ui_update(lambda: self._log("[INIT] Waiting for model to load..."))
                
                print("[INIT] Step 2: Waiting for model (30s timeout)...")
                if self.audio_engine.wait_for_model(30):
                    self.health_monitor.update_component("model_loaded", "ready")
                    self._queue_ui_update(lambda: self._log("[OK] Model loaded successfully"))
                    print("[INIT] Model loaded successfully")
                else:
                    self.health_monitor.update_component("model_loaded", "failed", "Timeout waiting for model")
                    self._queue_ui_update(lambda: self._log("[ERROR] Model loading timeout"))
                    print("[ERROR] Model loading failed or timeout")
                    self._handle_init_failure("Model Loading")
                    return
                
                # Step 3: Verify Model Manager
                self._queue_ui_update(lambda: self._update_detailed_status("Step 3/5: Verifying model manager..."))
                try:
                    if hasattr(self.audio_engine, 'model_mgr') and self.audio_engine.model_mgr:
                        self.health_monitor.update_component("model_manager", "ready")
                        self._queue_ui_update(lambda: self._log("[OK] Model manager verified"))
                    else:
                        raise Exception("Model manager not available")
                except Exception as e:
                    err = f"Model manager verification failed: {e}"
                    self.health_monitor.update_component("model_manager", "failed", str(e))
                    self._queue_ui_update(lambda err=err: self._log(f"[ERROR] {err}"))
                
                # Step 4: Verify Command Manager
                self._queue_ui_update(lambda: self._update_detailed_status("Step 4/5: Loading command manager..."))
                try:
                    if hasattr(self.audio_engine, 'cmd_hotword_mgr') and self.audio_engine.cmd_hotword_mgr:
                        # Auto-load commands from JSON
                        self._queue_ui_update(lambda: self._log("[INIT] Auto-loading commands from JSON..."))
                        self.audio_engine.cmd_hotword_mgr.load_commands_from_json()
                        # Track JSON path and modified time for auto-reload
                        try:
                            self._commands_json_path = getattr(self.audio_engine.cmd_hotword_mgr, 'data_file', 'commands_hotwords.json')
                            self._commands_json_mtime = os.path.getmtime(self._commands_json_path) if os.path.exists(self._commands_json_path) else None
                        except Exception:
                            self._commands_json_path = 'commands_hotwords.json'
                            self._commands_json_mtime = None
                        self.health_monitor.update_component("command_manager", "ready")
                        self._queue_ui_update(lambda: self._log("[OK] Command manager ready"))
                    else:
                        raise Exception("Command manager not available")
                except Exception as e:
                    err = f"Command manager verification failed: {e}"
                    self.health_monitor.update_component("command_manager", "failed", str(e))
                    self._queue_ui_update(lambda err=err: self._log(f"[ERROR] {err}"))
                
                # Step 5: Verify TTS Engine
                self._queue_ui_update(lambda: self._update_detailed_status("Step 5/5: Initializing TTS engine..."))
                try:
                    if hasattr(self.audio_engine, 'tts_mgr') and self.audio_engine.tts_mgr:
                        self.health_monitor.update_component("tts_engine", "ready")
                        self._queue_ui_update(lambda: self._log("[OK] TTS engine ready"))
                    else:
                        self.health_monitor.update_component("tts_engine", "warning", "TTS not available")
                        self._queue_ui_update(lambda: self._log("[WARNING] TTS engine not available"))
                except Exception as e:
                    warn = f"TTS engine issue: {e}"
                    self.health_monitor.update_component("tts_engine", "failed", str(e))
                    self._queue_ui_update(lambda warn=warn: self._log(f"[WARNING] {warn}"))
                
                # Check if system is ready
                if self.health_monitor.is_system_ready():
                    self.system_ready = True
                    self._queue_ui_update(lambda: self._update_status("Ready"))
                    self._queue_ui_update(lambda: self._update_detailed_status("System ready! Click 'Start Listening' to begin."))
                    self._queue_ui_update(lambda: self.btn_start.config(state=tk.NORMAL))
                    self._queue_ui_update(lambda: self._log("[SUCCESS] System initialized successfully!"))
                    
                    # Populate UI controls
                    self._queue_ui_update(self._populate_controls)
                    self._queue_ui_update(self._refresh_commands)
                    self._queue_ui_update(self._refresh_training)
                    self._queue_ui_update(self._refresh_system_status)
                    
                    # TTS announcement (ONLY if system is actually ready)
                    if self.audio_engine.tts_mgr:
                        time.sleep(0.5)
                        self.audio_engine.tts_mgr.speak_status("ready")
                    
                    print("[SUCCESS] System initialization complete!")
                else:
                    failed = self.health_monitor.get_failed_components()
                    error_msg = f"System partially initialized. Failed components: {', '.join(failed)}"
                    self._queue_ui_update(lambda: self._update_status("Partially Ready"))
                    self._queue_ui_update(lambda: self._update_detailed_status(error_msg))
                    self._queue_ui_update(lambda: self._log(f"[WARNING] {error_msg}"))
                    print(f"[WARNING] {error_msg}")
                    
            except Exception as e:
                error_msg = f"Critical system initialization error: {e}"
                self._queue_ui_update(lambda: self._update_status("Initialization Failed"))
                self._queue_ui_update(lambda: self._update_detailed_status(error_msg))
                self._queue_ui_update(lambda: self._log(f"[CRITICAL] {error_msg}"))
                print(f"[CRITICAL] {error_msg}")
                traceback.print_exc()
        
        # Start initialization in background
        threading.Thread(target=_init, daemon=True, name="SystemInit").start()
    
    def _handle_init_failure(self, component: str):
        """Handle initialization failure"""
        self._queue_ui_update(lambda: self._update_status(f"{component} Failed"))
        self._queue_ui_update(lambda: self._update_detailed_status(
            f"Failed to initialize {component}. Check console for details."))
        self._queue_ui_update(lambda: self._log(f"[FAILED] {component} initialization failed"))
    
    # ========================================================================
    # UI Update Queue System
    # ========================================================================
    
    def _queue_ui_update(self, update_func):
        """Queue a UI update to be processed in the main thread"""
        with self.ui_lock:
            self.ui_updates.append(update_func)
    
    def _start_ui_updates(self):
        """Start the UI update processing loop"""
        def _process_updates():
            with self.ui_lock:
                updates = self.ui_updates.copy()
                self.ui_updates.clear()
            
            # Process updates in main thread
            for update_func in updates:
                try:
                    update_func()
                except Exception as e:
                    print(f"[ERROR] UI update error: {e}")
            
            # Schedule next update
            self.root.after(50, _process_updates)  # 20 FPS
        
        # Start processing
        self.root.after(50, _process_updates)
    
    # ========================================================================
    # Auto-Refresh System (NEW - for JSON reload and list updates)
    # ========================================================================
    
    def _start_auto_refresh(self):
        """Start auto-refresh timer (also supports JSON hot-reload in dev mode only)"""
        def _auto_refresh():
            if self.auto_refresh_enabled and self.system_ready:
                try:
                    # FIX #4: JSON hot-reload only in development mode, not in packaged builds
                    if self.enable_json_hot_reload and self._commands_json_path and os.path.exists(self._commands_json_path):
                        try:
                            mtime = os.path.getmtime(self._commands_json_path)
                            if self._commands_json_mtime is None or mtime > self._commands_json_mtime:
                                if self.audio_engine and getattr(self.audio_engine, 'cmd_hotword_mgr', None):
                                    if self.audio_engine.cmd_hotword_mgr.load_commands_from_json():
                                        self._commands_json_mtime = mtime
                                        self._log("[INFO] Commands JSON reloaded due to external change")
                                        # Also refresh lists
                                        self._refresh_commands()
                                        self._refresh_training()
                        except Exception as e:
                            print(f"[WARN] JSON hot-reload check failed: {e}")

                    # Regular UI list refresh
                    self._refresh_commands()
                    self._refresh_training()
                except Exception as e:
                    print(f"[ERROR] Auto-refresh failed: {e}")
            
            # Schedule next refresh
            if self.auto_refresh_enabled:
                self.root.after(self.auto_refresh_interval, _auto_refresh)
        
        # Start the timer
        self.root.after(self.auto_refresh_interval, _auto_refresh)
        mode_str = "(with JSON hot-reload)" if self.enable_json_hot_reload else "(packaged mode, no JSON monitoring)"
        print(f"[INFO] Auto-refresh enabled {mode_str} (interval: {self.auto_refresh_interval}ms)")
    
    def _reload_commands_json(self):
        """Manually reload the JSON command file"""
        if not self.audio_engine or not hasattr(self.audio_engine, 'cmd_hotword_mgr'):
            messagebox.showerror("Error", "Command manager not available")
            return
        
        try:
            self._log("[INFO] Reloading commands from JSON...")
            self.audio_engine.cmd_hotword_mgr.load_commands_from_json()
            self._refresh_commands()
            self._refresh_training()
            self._log("[SUCCESS] Commands reloaded from JSON")
            messagebox.showinfo("Success", "Commands reloaded from JSON file")
        except Exception as e:
            error_msg = f"Failed to reload JSON: {e}"
            self._log(f"[ERROR] {error_msg}")
            messagebox.showerror("Error", error_msg)
    
    # ========================================================================
    # Control Population
    # ========================================================================
    
    def _populate_controls(self):
        """Populate model and voice controls"""
        if not self.audio_engine:
            return
        
        # Update voice list
        try:
            if self.audio_engine.tts_mgr:
                voices = self.audio_engine.tts_mgr.get_available_voices()
                self.available_voices = voices
                
                voice_names = [v.get("name", f"Voice {i}") for i, v in enumerate(voices)]
                if not voice_names:
                    voice_names = ["Default"]
                
                self.voice_combo.configure(values=voice_names)
                if voice_names:
                    self.voice_combo.set(voice_names[0])
                    
                self._log(f"[INFO] Loaded {len(voices)} TTS voices")
        except Exception as e:
            print(f"[ERROR] Voice populate error: {e}")
            self._log(f"[ERROR] Failed to load voices: {e}")
    
    # ========================================================================
    # Voice Recognition Control
    # ========================================================================
    
    def _start_listening(self):
        """Start voice recognition"""
        if not self.audio_engine or self.is_listening:
            return
        
        if not self.system_ready:
            messagebox.showwarning("System Not Ready", 
                                 "System is not fully initialized. Please wait.")
            return
        
        self.stop_event.clear()
        self.is_listening = True
        
        # Update UI
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self._update_status("Listening for 'susie'...")
        self._update_detailed_status("System is listening for the wake word 'susie'. Speak clearly.")
        
        # Clear results
        self.result_text.delete("1.0", tk.END)
        
        # Log start
        timestamp = datetime.now().strftime('%H:%M:%S')
        self._log(f"[{timestamp}] Voice recognition started")
        self._log("Say 'susie' to activate command mode")
        
        # TTS feedback
        if self.audio_engine.tts_mgr:
            self.audio_engine.tts_mgr.speak_status("start")
            time.sleep(0.3)
            self.audio_engine.tts_mgr.speak_status("listening")
        
        # CRITICAL FIX: Use non-daemon thread for proper cleanup
        self.recognition_thread = threading.Thread(
            target=self._recognition_loop, 
            daemon=False,  # Non-daemon for graceful shutdown
            name="Recognition"
        )
        self.recognition_thread.start()
        print("[LISTEN] Recognition thread started (non-daemon)")
    
    def _stop_listening(self):
        """ENHANCED: Stop voice recognition with proper thread joining"""
        print("[LISTEN] Stopping recognition...")
        
        # Set stop flags
        self.stop_event.set()
        self.is_listening = False
        
        # Reset audio engine state
        if self.audio_engine:
            self.audio_engine.reset_wake_state()
        
        # Update UI immediately
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self._update_status("Ready")
        self._update_detailed_status("Recognition stopped. System ready to start again.")
        
        # Log stop
        timestamp = datetime.now().strftime('%H:%M:%S')
        self._log(f"[{timestamp}] Voice recognition stopped")
        
        # TTS feedback
        if self.audio_engine and self.audio_engine.tts_mgr:
            self.audio_engine.tts_mgr.speak_status("stop")
        
        # CRITICAL FIX: Wait for thread to finish (with timeout)
        if self.recognition_thread and self.recognition_thread.is_alive():
            print("[LISTEN] Waiting for recognition thread to stop...")
            self.recognition_thread.join(timeout=3.0)
            
            if self.recognition_thread.is_alive():
                print("[LISTEN] WARNING: Recognition thread did not stop gracefully")
            else:
                print("[LISTEN] ✓ Recognition thread stopped")
        
        print("[LISTEN] Recognition stopped successfully")
    
    def _recognition_loop(self):
        """Main recognition loop"""
        state = "wake_word"
        fail_count = 0
        max_failures = 5
        
        try:
            print("[INFO] Recognition loop started")
            
            while self.is_listening and not self.stop_event.is_set():
                try:
                    if state == "wake_word":
                        self._queue_ui_update(lambda: self._update_detailed_status(
                            "Listening for wake word 'susie'..."))
                        
                        audio_data = self.audio_engine.record_audio(duration=3.0)
                        if audio_data is None or self.stop_event.is_set():
                            continue
                        
                        if self.audio_engine.detect_wake_word(audio_data, "susie"):
                            self.audio_engine.set_wake_state(self.audio_engine.WAKE_STATE_ACTIVE)
                            state = "command"
                            fail_count = 0
                            
                            timestamp = datetime.now().strftime("%H:%M:%S")
                            self._queue_ui_update(lambda: self._update_status("Command Mode"))
                            self._queue_ui_update(lambda: self._update_detailed_status(
                                "Wake word detected! Command mode active."))
                            self._queue_ui_update(lambda: self._log(
                                f"[{timestamp}] Wake word detected"))
                            
                            time.sleep(0.5)
                        
                        time.sleep(0.5)
                        
                    elif state == "command":
                        self._queue_ui_update(lambda: self._update_detailed_status(
                            f"Listening for command... (Failures: {fail_count}/{max_failures})"))
                        
                        audio_data = self.audio_engine.record_audio(duration=2.5)
                        if audio_data is None or self.stop_event.is_set():
                            continue
                        
                        text = self.audio_engine.transcribe(audio_data)
                        if not text:
                            time.sleep(0.5)
                            continue
                        
                        print(f"[TRANSCRIBED] '{text}'")
                        
                        # FIX #2: Removed "processing" TTS (redundant, causes latency)
                        
                        commands = self.audio_engine.get_all_commands()
                        matched_cmd = self.audio_engine.match_command(text, commands)
                        
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        
                        if matched_cmd:
                            fail_count = 0
                            
                            if self._write_output(matched_cmd):
                                msg = f"[{timestamp}] Command: '{matched_cmd}' -> output.txt"
                                self._queue_ui_update(lambda: self._update_detailed_status(
                                    f"Success! Command '{matched_cmd}' executed"))
                                
                                # FIX #1: TTS-STT synchronization
                                if self.audio_engine.tts_mgr:
                                    self.audio_engine.tts_mgr.speak_command(matched_cmd)
                                    # Block STT restart until TTS completes
                                    tts_completed = self.audio_engine.tts_mgr.wait_for_completion(timeout=5.0)
                                    if not tts_completed:
                                        # Fallback: Fixed delay if TTS status unavailable
                                        print("[WARN] TTS completion timeout, using fallback delay")
                                        time.sleep(2.5)
                            else:
                                msg = f"[{timestamp}] Command: '{matched_cmd}' (write failed)"
                                if self.audio_engine.tts_mgr:
                                    self.audio_engine.tts_mgr.speak_status("error")
                                    self.audio_engine.tts_mgr.wait_for_completion(timeout=3.0)
                        else:
                            fail_count += 1
                            msg = f"[{timestamp}] '{text}' -> No match ({fail_count}/{max_failures})"
                            self._queue_ui_update(lambda: self._update_detailed_status(
                                f"No matching command: '{text}'"))
                            
                            # FIX #1: TTS-STT synchronization
                            if self.audio_engine.tts_mgr:
                                self.audio_engine.tts_mgr.speak_status("not match")
                                # Block STT restart until TTS completes
                                self.audio_engine.tts_mgr.wait_for_completion(timeout=3.0)
                        
                        self._queue_ui_update(lambda: self._log(msg))
                        
                        if fail_count >= max_failures:
                            print("[INFO] Max failures reached, returning to wake word mode")
                            state = "wake_word"
                            fail_count = 0
                            self.audio_engine.reset_wake_state()
                            
                            self._queue_ui_update(lambda: self._update_status("Listening..."))
                            self._queue_ui_update(lambda: self._update_detailed_status(
                                "Too many failures. Returned to standby."))
                            self._queue_ui_update(lambda: self._log(
                                "Auto-reset: Returned to standby"))
                        
                        time.sleep(1.0)
                    
                except Exception as e:
                    print(f"[ERROR] Recognition loop error: {e}")
                    self._queue_ui_update(lambda: self._log(f"Recognition error: {e}"))
                    time.sleep(1.0)
                    continue
        
        except Exception as e:
            print(f"[CRITICAL] Recognition error: {e}")
            traceback.print_exc()
            self._queue_ui_update(lambda: self._log(f"Critical error: {e}"))
        
        finally:
            print("[INFO] Recognition loop ended")
            if self.is_listening:
                self._queue_ui_update(self._stop_listening)
    
    def _write_output(self, text: str) -> bool:
        """Write command to output file"""
        try:
            # Per specification, write ONLY the core command text (no timestamps or labels)
            content = f"{text}\n"
            
            with open("output.txt", "w", encoding="utf-8") as f:
                f.write(content)
            
            print(f"[OUTPUT] Written: {text}")
            return True
        
        except Exception as e:
            print(f"[ERROR] Write output error: {e}")
            return False
    
    # ========================================================================
    # Event Handlers
    # ========================================================================
    
    def _on_model_change(self, event=None):
        """Handle model selection change"""
        if not self.audio_engine:
            return
        
        new_model = self.model_combo.get()
        if not new_model or new_model == self.audio_engine.get_current_model():
            return
        
        self._update_detailed_status(f"Switching to {new_model} model...")
        self._log(f"[INFO] Switching STT model to: {new_model}")
        
        def _switch():
            success = self.audio_engine.switch_model(new_model)
            if success:
                self._queue_ui_update(lambda: self._log(f"[SUCCESS] Model switched to: {new_model}"))
                if self.audio_engine.tts_mgr:
                    self.audio_engine.tts_mgr.speak_text(f"Model switched to {new_model}", priority=True)
            else:
                self._queue_ui_update(lambda: self._log(f"[ERROR] Failed to switch to: {new_model}"))
        
        threading.Thread(target=_switch, daemon=True).start()
    
    def _on_voice_change(self, event=None):
        """Handle voice selection change"""
        if not self.audio_engine or not self.audio_engine.tts_mgr:
            return
        
        choice = self.voice_combo.get()
        
        voice_index = 0
        for i, voice in enumerate(self.available_voices):
            if voice.get("name") == choice:
                voice_index = i
                break
        
        if self.audio_engine.tts_mgr.set_voice_by_index(voice_index):
            self._log(f"[INFO] TTS voice changed to: {choice}")
        else:
            self._log(f"[ERROR] Failed to change voice to: {choice}")
    
    def _test_voice(self):
        """Test current TTS voice"""
        if self.audio_engine and self.audio_engine.tts_mgr:
            self.audio_engine.tts_mgr.speak_text("This is a voice test. How does this sound?", priority=True)
            self._log("[INFO] Testing TTS voice...")
    
    # ========================================================================
    # Command Management
    # ========================================================================
    
    def _add_command(self):
        """Add new command"""
        command = self.cmd_entry.get().strip()
        if not command:
            return
        
        if self.audio_engine and self.audio_engine.add_command(command):
            self.cmd_entry.delete(0, tk.END)
            self._refresh_commands()
            self._refresh_training()
            self._log(f"[SUCCESS] Command added: '{command}'")
            messagebox.showinfo("Success", f"Command '{command}' added")
        else:
            messagebox.showerror("Error", f"Failed to add command '{command}'")
    
    def _delete_command(self):
        """Delete selected command"""
        selection = self.cmd_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a command to delete.")
            return
        
        item = self.cmd_tree.item(selection[0])
        command = item["values"][0]
        
        if messagebox.askyesno("Confirm", f"Delete command '{command}'?"):
            if self.audio_engine and self.audio_engine.remove_command(command):
                self._refresh_commands()
                self._refresh_training()
                self._log(f"[INFO] Command deleted: '{command}'")
    
    def _refresh_commands(self):
        """Refresh commands list"""
        if not self.audio_engine:
            return
        
        try:
            # Clear tree
            for item in self.cmd_tree.get_children():
                self.cmd_tree.delete(item)
            
            # Get commands
            commands = self.audio_engine.get_all_commands()
            
            # Populate tree
            for cmd in commands:
                cmd_info = self.audio_engine.cmd_hotword_mgr.get_command_info(cmd)
                weight = cmd_info.get("weight", 1.0)
                usage = cmd_info.get("usage_count", 0)
                
                self.cmd_tree.insert("", tk.END, values=(cmd, f"{weight:.2f}", usage))
        except Exception as e:
            print(f"[ERROR] Refresh commands failed: {e}")
    
    def _train_command(self):
        """Train selected command"""
        selection = self.train_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a command to train.")
            return
        
        item = self.train_tree.item(selection[0])
        command = item["values"][0]
        
        if self.audio_engine:
            new_weight = self.audio_engine.train_command(command)
            self._refresh_training()
            self._log(f"[INFO] Command trained: '{command}' -> weight: {new_weight:.2f}")
            messagebox.showinfo("Training", f"Command '{command}' trained. Weight: {new_weight:.2f}")
    
    def _refresh_training(self):
        """Refresh training data"""
        if not self.audio_engine:
            return
        
        try:
            # Clear tree
            for item in self.train_tree.get_children():
                self.train_tree.delete(item)
            
            # Get commands
            commands = self.audio_engine.get_all_commands()
            
            # Populate tree
            for cmd in commands:
                usage_count = self.audio_engine.get_training_count(cmd)
                cmd_info = self.audio_engine.cmd_hotword_mgr.get_command_info(cmd)
                weight = cmd_info.get("weight", 1.0)
                
                self.train_tree.insert("", tk.END, values=(cmd, usage_count, f"{weight:.2f}"))
        except Exception as e:
            print(f"[ERROR] Refresh training failed: {e}")
    
    def _refresh_system_status(self):
        """Refresh system status display"""
        if not self.audio_engine:
            status_text = "Audio engine not initialized.\n\nPlease wait for system initialization to complete."
        else:
            try:
                status = self.audio_engine.get_system_status()
                
                status_text = "=== ENHANCED VOICE CONTROL SYSTEM STATUS ===\n\n"
                status_text += f"System Status: {'Ready' if self.system_ready else 'Initializing'}\n"
                status_text += f"Wake State: {status.get('wake_state', 'UNKNOWN')}\n"
                status_text += f"Processing: {status.get('processing', False)}\n"
                status_text += f"Recording: {self.is_listening}\n"
                status_text += f"Backend: {status.get('backend', 'unknown')}\n"
                status_text += f"Current Model: {status.get('model_size', 'unknown')}\n"
                status_text += f"Model Loaded: {status.get('model_loaded', False)}\n"
                
                # Commands
                commands = status.get('commands', {})
                status_text += f"\nCommands: {commands.get('total', 0)} total\n"
                status_text += f"Total Usage: {commands.get('total_usage', 0)}\n"
                
                most_used = commands.get('most_used', [])
                if most_used:
                    status_text += "\nMost Used Commands:\n"
                    for cmd, count in most_used[:5]:
                        status_text += f"  '{cmd}': {count} times\n"
                
                # TTS
                tts = status.get('tts', {})
                status_text += f"\nTTS Engine: {tts.get('engine_type', 'unknown')}\n"
                status_text += f"TTS Running: {tts.get('running', False)}\n"
                status_text += f"Voice Count: {len(self.available_voices)}\n"
                
                # Features
                features = status.get('features', {})
                status_text += "\nFeatures:\n"
                for feature, enabled in features.items():
                    status_text += f"  {feature}: {'Enabled' if enabled else 'Disabled'}\n"
                
            except Exception as e:
                status_text = f"Error getting system status: {e}\n"
                status_text += traceback.format_exc()
        
        # Update display
        self.system_text.config(state=tk.NORMAL)
        self.system_text.delete("1.0", tk.END)
        self.system_text.insert("1.0", status_text)
        self.system_text.config(state=tk.DISABLED)
    
    def _show_health_report(self):
        """Show system health report"""
        report = self.health_monitor.get_status_report()
        
        # Create popup window
        popup = tk.Toplevel(self.root)
        popup.title("System Health Report")
        popup.geometry("600x400")
        popup.configure(bg=COLORS["bg"])
        
        # Header
        header = tk.Label(popup, text="System Health Report",
                         font=FONTS["title"], bg=COLORS["bg"])
        header.pack(pady=10)
        
        # Report text
        report_text = tk.Text(popup, font=FONTS["mono"], wrap=tk.WORD)
        report_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        report_text.insert("1.0", report)
        report_text.config(state=tk.DISABLED)
        
        # Close button
        tk.Button(popup, text="Close", command=popup.destroy,
                 bg=COLORS["primary"], fg="white",
                 relief=tk.FLAT, bd=0).pack(pady=10)
    
    def _save_log(self):
        """Save activity log"""
        try:
            log_content = self.result_text.get("1.0", tk.END)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"voice_control_log_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(log_content)
            
            messagebox.showinfo("Success", f"Log saved as {filename}")
            self._log(f"[INFO] Log saved: {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save log: {e}")
    
    # ========================================================================
    # UI Helpers
    # ========================================================================
    
    def _update_status(self, status: str):
        """Update main status display"""
        self.status_var.set(status)
        self.current_state = status
    
    def _update_detailed_status(self, status: str):
        """Update detailed status display"""
        self.detailed_status_var.set(status)
    
    def _log(self, message: str):
        """Add message to activity log"""
        self.result_text.insert(tk.END, message + "\n")
        self.result_text.see(tk.END)
    
    def on_closing(self):
        """
        ENHANCED: Handle application closing with proper cleanup.
        CRITICAL FIX for GUI freezing issues.
        """
        print("[SHUTDOWN] Application closing initiated...")
        
        # Set shutdown flags immediately
        self.stop_event.set()
        self.auto_refresh_enabled = False
        
        # Update UI to show shutdown status
        try:
            self._update_status("Shutting down...")
            self._update_detailed_status("Cleaning up resources, please wait...")
        except:
            pass
        
        # CRITICAL: Stop voice recognition first
        if self.is_listening:
            print("[SHUTDOWN] Stopping voice recognition...")
            try:
                self.is_listening = False
                if self.audio_engine:
                    self.audio_engine.reset_wake_state()
            except Exception as e:
                print(f"[SHUTDOWN] Recognition stop error: {e}")
        
        # CRITICAL: Wait for recognition thread to finish (with timeout)
        if hasattr(self, 'recognition_thread') and self.recognition_thread:
            if self.recognition_thread.is_alive():
                print("[SHUTDOWN] Waiting for recognition thread...")
                self.recognition_thread.join(timeout=3.0)
                if self.recognition_thread.is_alive():
                    print("[SHUTDOWN] WARNING: Recognition thread did not stop")
                else:
                    print("[SHUTDOWN] ✓ Recognition thread stopped")
        
        # CRITICAL: Shutdown audio engine (this shutdowns TTS, CommandMgr, etc.)
        if hasattr(self, 'audio_engine') and self.audio_engine:
            print("[SHUTDOWN] Shutting down audio engine...")
            try:
                self.audio_engine.shutdown()
                print("[SHUTDOWN] ✓ Audio engine shut down")
            except Exception as e:
                print(f"[SHUTDOWN] Audio engine shutdown error: {e}")
        
        # CRITICAL: Wait for model init thread if still running
        if hasattr(self, 'audio_engine') and self.audio_engine:
            if hasattr(self.audio_engine, '_model_init_thread'):
                thread = self.audio_engine._model_init_thread
                if thread and thread.is_alive():
                    print("[SHUTDOWN] Waiting for model init thread...")
                    thread.join(timeout=2.0)
        
        # Give a moment for all cleanup to complete
        time.sleep(0.5)
        
        # CRITICAL: Destroy window and quit
        print("[SHUTDOWN] Closing window...")
        try:
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            print(f"[SHUTDOWN] Window close error: {e}")
        
        print("[SHUTDOWN] Application closed successfully")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main application entry point"""
    print("=" * 70)
    print("ENHANCED VOICE CONTROL SYSTEM v2.0")
    print("=" * 70)
    print("[INFO] Starting application...")
    
    try:
        root = tk.Tk()
        app = VoiceControlApp(root)
        
        # Set up window close handler
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        
        # Start the application
        print("[INFO] Entering main loop...")
        root.mainloop()
        
    except Exception as e:
        print(f"[CRITICAL] Application error: {e}")
        traceback.print_exc()
    
    print("[INFO] Application closed")
    print("=" * 70)


if __name__ == "__main__":
    main()
