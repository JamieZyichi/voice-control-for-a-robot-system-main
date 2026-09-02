# ============================================================================
# tts_engine_v2.py - Enhanced Windows System TTS Engine
# ============================================================================
"""
Enhanced Windows SAPI TTS Engine with:
- Proper COM initialization and cleanup
- Graceful shutdown mechanism (no daemon threads)
- Thread-safe queue processing with error recovery
- Unicode text support with smart preprocessing
- Asynchronous priority-based TTS processing
- PyInstaller compatibility
"""

import threading
import queue
import time
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import traceback

# TTS Status Messages (FIX #2: Minimized to essential keywords, max 3 words)
# Removed redundant messages like "Processing" to reduce latency
TTS_MESSAGES = {
    "ready": "Ready",
    "start": "Started",
    "listening": "Listening",
    "please speak": "Speak now",
    "processing": "",  # REMOVED: Redundant, causes latency
    "not match": "Unknown",
    "stop": "Stopped",
    "stand by": "Standby",
    "error": "Error"
}

class TTSEngine:
    """
    Enhanced Windows System TTS engine with proper lifecycle management.
    
    Key Improvements:
    - COM initialization per thread (pythoncom.CoInitialize)
    - Non-daemon worker thread with graceful shutdown
    - Enhanced error recovery with engine reinitialization
    - Unicode-aware text preprocessing
    - Thread-safe operations with proper locking
    - Clean resource cleanup on exit
    - TTS completion callbacks for STT synchronization
    """
    
    def __init__(self, config_file: str = "tts_config.json"):
        self.config_file = Path(config_file)
        
        # Configuration
        self.config = self._load_config()
        
        # TTS engine state
        self.engine = None
        self.available_voices = []
        self.current_voice_index = 0
        
        # Thread management (non-daemon)
        self.tts_queue = queue.Queue(maxsize=20)
        self.is_running = False
        self.worker_thread = None
        self.shutdown_event = threading.Event()
        self._engine_lock = threading.RLock()
        
        # Performance tracking
        self._speaking = False
        self._queue_stats = {"processed": 0, "dropped": 0, "errors": 0}
        
        # TTS-STT synchronization (FIX #1)
        self._completion_event = threading.Event()
        self._completion_event.set()  # Initially not speaking
        self._speaking_start_time = 0
        
        # Error recovery
        self._consecutive_errors = 0
        self._max_consecutive_errors = 3
        self._last_reinit_time = 0
        self._reinit_cooldown = 5.0  # seconds
        
        # Initialize engine (lazy initialization in worker thread)
        print("[TTS] TTSEngine initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load TTS configuration with proper error handling"""
        default_config = {
            "voice_index": 0,
            "rate": 0,  # Default rate for SAPI (range: -10 to 10)
            "volume": 100,  # Volume for SAPI (range: 0 to 100)
            "enabled": True,
            "queue_timeout": 0.5,  # Shorter timeout for responsiveness
            "max_text_length": 300,  # Increased for better message support
            "unicode_support": True  # Enable unicode character handling
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    default_config.update(loaded)
                print(f"[TTS] Config loaded from {self.config_file}")
            except Exception as e:
                print(f"[TTS] Config load error: {e}")
        
        return default_config
    
    def _save_config(self):
        """Save configuration asynchronously with proper error handling"""
        def _save():
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[TTS] Config save error: {e}")
        
        # Save in background daemon thread (non-critical operation)
        threading.Thread(target=_save, daemon=True, name="TTS-ConfigSave").start()
    
    def _init_engine(self) -> bool:
        """
        Initialize Windows SAPI TTS engine with proper COM initialization.
        Must be called from the worker thread for proper COM apartment threading.
        """
        try:
            # CRITICAL: Initialize COM for this thread
            import pythoncom
            pythoncom.CoInitialize()
            
            import win32com.client
            
            with self._engine_lock:
                # Create SAPI voice object
                self.engine = win32com.client.Dispatch("SAPI.SpVoice")
                
                # Get available voices
                voices = self.engine.GetVoices()
                self.available_voices = []
                
                for i in range(voices.Count):
                    voice = voices.Item(i)
                    voice_info = {
                        "index": i,
                        "name": voice.GetDescription(),
                        "id": voice.Id,
                        "gender": self._detect_gender(voice.GetDescription())
                    }
                    self.available_voices.append(voice_info)
                
                # Apply saved settings
                self._apply_settings()
                
                print(f"[TTS] Windows SAPI initialized - {len(self.available_voices)} voices available")
                self._consecutive_errors = 0  # Reset error counter
                return True
                
        except ImportError as e:
            print(f"[TTS] CRITICAL: pywin32 not available - {e}")
            print("[TTS] Install with: pip install pywin32")
            return False
        except Exception as e:
            print(f"[TTS] Engine initialization error: {e}")
            traceback.print_exc()
            return False
    
    def _detect_gender(self, name: str) -> str:
        """Simple gender detection from voice name"""
        name_lower = name.lower()
        if any(word in name_lower for word in ['david', 'mark', 'ryan', 'male', 'man', 'george', 'james']):
            return "male"
        elif any(word in name_lower for word in ['zira', 'hazel', 'female', 'eva', 'woman', 'susan', 'helen']):
            return "female"
        return "unknown"
    
    def _apply_settings(self):
        """Apply voice settings to engine"""
        if not self.engine:
            return
        
        try:
            with self._engine_lock:
                # Set voice
                voice_index = self.config.get("voice_index", 0)
                if 0 <= voice_index < len(self.available_voices):
                    voices = self.engine.GetVoices()
                    if voice_index < voices.Count:
                        self.engine.Voice = voices.Item(voice_index)
                        self.current_voice_index = voice_index
                
                # Set rate (-10 to 10)
                rate = max(-10, min(10, self.config.get("rate", 0)))
                self.engine.Rate = rate
                
                # Set volume (0 to 100)
                volume = max(0, min(100, self.config.get("volume", 100)))
                self.engine.Volume = volume
            
        except Exception as e:
            print(f"[TTS] Settings apply error: {e}")
    
    def get_available_voices(self) -> List[Dict[str, Any]]:
        """Get list of available voices"""
        return self.available_voices.copy()
    
    def set_voice_by_index(self, voice_index: int) -> bool:
        """Set voice by index"""
        if not self.engine or not (0 <= voice_index < len(self.available_voices)):
            return False
        
        try:
            with self._engine_lock:
                voices = self.engine.GetVoices()
                if voice_index < voices.Count:
                    self.engine.Voice = voices.Item(voice_index)
                    self.current_voice_index = voice_index
                    self.config["voice_index"] = voice_index
                    
                    # Save config asynchronously
                    self._save_config()
                    print(f"[TTS] Voice changed to: {self.available_voices[voice_index]['name']}")
                    return True
                    
        except Exception as e:
            print(f"[TTS] Voice setting error: {e}")
        
        return False
    
    def set_rate(self, rate: int) -> bool:
        """Set speech rate (-10 to 10)"""
        if not self.engine:
            return False
        
        try:
            rate = max(-10, min(10, rate))
            with self._engine_lock:
                self.engine.Rate = rate
                self.config["rate"] = rate
                self._save_config()
                return True
        except Exception as e:
            print(f"[TTS] Rate setting error: {e}")
            return False
    
    def set_volume(self, volume: int) -> bool:
        """Set speech volume (0 to 100)"""
        if not self.engine:
            return False
        
        try:
            volume = max(0, min(100, volume))
            with self._engine_lock:
                self.engine.Volume = volume
                self.config["volume"] = volume
                self._save_config()
                return True
        except Exception as e:
            print(f"[TTS] Volume setting error: {e}")
            return False
    
    def preview_voice(self, voice_index: int):
        """Preview a voice (non-blocking)"""
        if not (0 <= voice_index < len(self.available_voices)):
            return
        
        def _preview():
            original_index = self.current_voice_index
            if self.set_voice_by_index(voice_index):
                self.speak_text_sync("This is a voice preview test")
                self.set_voice_by_index(original_index)
        
        # Use daemon thread for preview (non-critical)
        threading.Thread(target=_preview, daemon=True, name="TTS-Preview").start()
    
    def start(self):
        """Start TTS worker thread with proper lifecycle management"""
        if self.is_running:
            print("[TTS] Already running")
            return
        
        self.is_running = True
        self.shutdown_event.clear()
        
        # CRITICAL: Use non-daemon thread for proper cleanup
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=False,  # Non-daemon to allow graceful shutdown
            name="TTS-Worker"
        )
        self.worker_thread.start()
        print("[TTS] Worker thread started")
    
    def stop(self, timeout: float = 5.0):
        """
        Stop TTS worker thread gracefully.
        This is the critical fix for GUI freezing issues.
        """
        if not self.is_running:
            return
        
        print("[TTS] Stopping worker thread...")
        
        # Signal shutdown
        self.is_running = False
        self.shutdown_event.set()
        
        # Clear queue and send shutdown signal
        try:
            self.clear_queue()
            self.tts_queue.put(None, timeout=0.5)
        except queue.Full:
            pass
        
        # Interrupt any ongoing speech
        try:
            with self._engine_lock:
                if self.engine:
                    try:
                        self.engine.Skip("Sentence", 999999)
                    except:
                        pass
        except:
            pass
        
        # Wait for worker thread to finish (non-blocking with timeout)
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=timeout)
            if self.worker_thread.is_alive():
                print("[TTS] WARNING: Worker thread did not stop gracefully")
            else:
                print("[TTS] Worker thread stopped successfully")
        
        self.worker_thread = None
    
    def _worker_loop(self):
        """
        Enhanced TTS worker loop with proper COM initialization and cleanup.
        This runs in a separate thread with its own COM apartment.
        """
        print("[TTS] Worker loop starting...")
        
        # CRITICAL: Initialize COM for this worker thread
        try:
            import pythoncom
            pythoncom.CoInitialize()
            print("[TTS] COM initialized for worker thread")
        except Exception as e:
            print(f"[TTS] CRITICAL: COM initialization failed: {e}")
            return
        
        # Initialize TTS engine
        if not self._init_engine():
            print("[TTS] CRITICAL: Engine initialization failed")
            pythoncom.CoUninitialize()
            return
        
        # Main processing loop
        try:
            while self.is_running and not self.shutdown_event.is_set():
                try:
                    # Get task with timeout for responsiveness
                    try:
                        task = self.tts_queue.get(
                            timeout=self.config.get("queue_timeout", 0.5)
                        )
                    except queue.Empty:
                        continue
                    
                    # Check for shutdown signal
                    if task is None or not self.is_running:
                        break
                    
                    text = task.get("text", "")
                    priority = task.get("priority", False)
                    
                    if not text:
                        self.tts_queue.task_done()
                        continue
                    
                    # Process text
                    clean_text = self._clean_text(text)
                    if not clean_text:
                        self.tts_queue.task_done()
                        continue
                    
                    # Speak using Windows SAPI
                    try:
                        with self._engine_lock:
                            if self.engine and self.config.get("enabled", True):
                                # Signal TTS start (FIX #1: TTS-STT synchronization)
                                self._completion_event.clear()
                                self._speaking = True
                                self._speaking_start_time = time.time()
                                
                                # Use synchronous speaking for queue processing
                                self.engine.Speak(clean_text, 0)  # 0 = synchronous
                                
                                # Signal TTS completion (FIX #1)
                                self._speaking = False
                                self._completion_event.set()
                                
                                self._queue_stats["processed"] += 1
                                self._consecutive_errors = 0  # Reset on success
                                
                    except Exception as e:
                        print(f"[TTS] Speak error: {e}")
                        self._queue_stats["errors"] += 1
                        self._speaking = False
                        self._consecutive_errors += 1
                        
                        # Reinitialize engine after consecutive failures
                        if self._consecutive_errors >= self._max_consecutive_errors:
                            current_time = time.time()
                            if current_time - self._last_reinit_time > self._reinit_cooldown:
                                print("[TTS] Attempting engine reinitialization...")
                                try:
                                    with self._engine_lock:
                                        self.engine = None
                                    self._init_engine()
                                    self._last_reinit_time = current_time
                                    print("[TTS] Engine reinitialized successfully")
                                except Exception as reinit_error:
                                    print(f"[TTS] Reinit failed: {reinit_error}")
                    
                    finally:
                        try:
                            self.tts_queue.task_done()
                        except:
                            pass
                            
                except Exception as e:
                    print(f"[TTS] Worker loop error: {e}")
                    traceback.print_exc()
                    time.sleep(0.5)
        
        finally:
            # CRITICAL: Cleanup COM and engine
            print("[TTS] Worker loop ending, cleaning up...")
            try:
                with self._engine_lock:
                    if self.engine:
                        try:
                            self.engine.Skip("Sentence", 999999)
                        except:
                            pass
                        self.engine = None
            except:
                pass
            
            try:
                import pythoncom
                pythoncom.CoUninitialize()
                print("[TTS] COM uninitialized")
            except:
                pass
            
            print("[TTS] Worker loop ended")
    
    def _clean_text(self, text: str) -> str:
        """
        Enhanced text cleaning with Unicode support.
        Converts non-ASCII characters intelligently instead of dropping them.
        """
        if not text:
            return ""
        
        # Limit length
        max_len = self.config.get("max_text_length", 300)
        if len(text) > max_len:
            text = text[:max_len] + "..."
        
        if self.config.get("unicode_support", True):
            # Smart Unicode handling - transliterate common characters
            replacements = {
                # Common Chinese characters (you can expand this)
                '打开': 'open',
                '关闭': 'close',
                '播放': 'play',
                '停止': 'stop',
                # Punctuation normalization
                '"': '"',
                '"': '"',
                ''': "'",
                ''': "'",
                '…': '...',
                '—': '-',
                '–': '-',
            }
            
            for old, new in replacements.items():
                text = text.replace(old, new)
            
            # Try to keep alphanumeric and basic punctuation
            # Allow extended ASCII for better compatibility
            clean = ''.join(c for c in text if ord(c) < 256 and (c.isalnum() or c in ' .,!?-\'":;()'))
        else:
            # Strict ASCII-only mode
            clean = ''.join(c for c in text if ord(c) < 128 and (c.isalnum() or c in ' .,!?-'))
        
        # Clean whitespace
        clean = ' '.join(clean.split()).strip()
        
        return clean if len(clean) > 0 else ""
    
    def speak_text(self, text: str, priority: bool = False) -> bool:
        """Queue text for speaking (non-blocking)"""
        if not self.config.get("enabled", True) or not text:
            return False
        
        try:
            task = {"text": text, "priority": priority}
            
            if priority:
                # Clear queue for high priority
                try:
                    while not self.tts_queue.empty():
                        try:
                            self.tts_queue.get_nowait()
                            self.tts_queue.task_done()
                        except queue.Empty:
                            break
                except:
                    pass
            
            self.tts_queue.put(task, timeout=0.1)
            return True
            
        except queue.Full:
            self._queue_stats["dropped"] += 1
            print(f"[TTS] Queue full, message dropped")
            return False
        except Exception as e:
            print(f"[TTS] Queue error: {e}")
            return False
    
    def speak_text_sync(self, text: str) -> bool:
        """Speak text synchronously (blocking) - use sparingly"""
        if not self.config.get("enabled", True) or not text:
            return False
        
        clean_text = self._clean_text(text)
        if not clean_text:
            return False
        
        try:
            with self._engine_lock:
                if self.engine:
                    self._speaking = True
                    self.engine.Speak(clean_text, 0)  # 0 = synchronous
                    self._speaking = False
                    return True
        except Exception as e:
            print(f"[TTS] Sync speak error: {e}")
            self._speaking = False
            return False
        
        return False
    
    def _limit_to_five_words(self, text: str) -> str:
        """Limit text to maximum 5 English words for interactive responses"""
        words = text.split()
        if len(words) > 5:
            return ' '.join(words[:5])
        return text
    
    def speak_status(self, status: str):
        """Speak status message with priority (limited to 5 words)"""
        message = TTS_MESSAGES.get(status, status)
        # Ensure status messages are limited to 5 words
        message = self._limit_to_five_words(message)
        self.speak_text(message, priority=True)
    
    def speak_command(self, command: str):
        """Speak command confirmation (limited to 5 words)"""
        # Limit command confirmation to 5 words
        limited_command = self._limit_to_five_words(command)
        self.speak_text(limited_command, priority=False)
    
    def is_speaking(self) -> bool:
        """Check if currently speaking"""
        return self._speaking
    
    def wait_for_completion(self, timeout: float = 5.0) -> bool:
        """
        Wait for TTS to complete speaking (FIX #1: TTS-STT synchronization).
        Returns True if TTS completed, False if timeout occurred.
        """
        return self._completion_event.wait(timeout=timeout)
    
    def get_estimated_duration(self, text: str) -> float:
        """
        Estimate TTS duration based on word count and rate.
        Used as fallback when completion polling is not available.
        """
        if not text:
            return 0.0
        
        words = len(text.split())
        # Base rate: ~150 words per minute (2.5 words per second)
        # Adjust for engine rate setting (-10 to +10)
        rate_factor = 1.0 + (self.config.get("rate", 0) * 0.1)  # ±100% adjustment
        duration = words / (2.5 * rate_factor)
        
        # Add buffer for processing
        return duration + 0.5
    
    def clear_queue(self):
        """Clear pending TTS queue"""
        try:
            while not self.tts_queue.empty():
                try:
                    self.tts_queue.get_nowait()
                    self.tts_queue.task_done()
                except queue.Empty:
                    break
            print("[TTS] Queue cleared")
        except Exception as e:
            print(f"[TTS] Queue clear error: {e}")
    
    def get_engine_info(self) -> Dict[str, Any]:
        """Get engine information for status display"""
        return {
            "engine_type": "Windows SAPI" if self.engine else "none",
            "enabled": self.config.get("enabled", True),
            "running": self.is_running,
            "speaking": self.is_speaking(),
            "voices_available": len(self.available_voices),
            "queue_size": self.tts_queue.qsize(),
            "stats": self._queue_stats.copy(),
            "current_voice": (
                self.available_voices[self.current_voice_index]["name"]
                if self.available_voices and 0 <= self.current_voice_index < len(self.available_voices)
                else "Unknown"
            ),
            "error_count": self._consecutive_errors,
            "status": "OK" if self.engine and self._consecutive_errors == 0 else "ERROR"
        }
    
    def shutdown(self):
        """
        Clean shutdown with proper resource cleanup.
        CRITICAL for preventing application hang on exit.
        """
        print("[TTS] Shutting down...")
        
        # Stop worker thread
        self.stop(timeout=5.0)
        
        # Final cleanup
        with self._engine_lock:
            if self.engine:
                try:
                    self.engine.Skip("Sentence", 999999)
                except:
                    pass
                self.engine = None
        
        print("[TTS] Shutdown complete")


# Test the enhanced TTS engine
if __name__ == "__main__":
    print("=" * 60)
    print("Testing Enhanced Windows TTS Engine v2")
    print("=" * 60)
    
    tts = TTSEngine()
    tts.start()
    
    # Wait for initialization
    time.sleep(1)
    
    # Test voices
    voices = tts.get_available_voices()
    print(f"\nAvailable voices: {len(voices)}")
    for i, voice in enumerate(voices[:5]):
        print(f"  {i}: {voice['name']} ({voice['gender']})")
    
    # Test speaking
    print("\nTesting speech...")
    tts.speak_text("Windows TTS engine version 2 test successful")
    time.sleep(3)
    
    # Test status messages
    print("\nTesting status messages...")
    tts.speak_status("ready")
    time.sleep(2)
    
    # Test engine info
    info = tts.get_engine_info()
    print(f"\nEngine info:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    # Shutdown
    print("\nShutting down...")
    tts.shutdown()
    print("Test complete!")
