# ============================================================================
# audio_engine.py
# ============================================================================

import warnings
warnings.filterwarnings("ignore")

import os
import sys
import threading
import time
import numpy as np
import pyaudio
from typing import Optional, List, Dict, Any

# Import optimized modules
from command_manager import CommandManager
from tts_engine import TTSEngine  
from model_manager import ModelManager

# Detect Whisper backend
BACKEND = None
try:
    from faster_whisper import WhisperModel
    BACKEND = "faster-whisper"
    print("Using faster-whisper backend")
except ImportError:
    try:
        import whisper
        BACKEND = "openai-whisper" 
        print("Using openai-whisper backend")
    except ImportError:
        BACKEND = "none"
        print("WARNING: No Whisper backend available")

class AudioEngine:
    """
    High-performance audio processing engine optimized to prevent UI freezing.
    
    Key Features:
    - Asynchronous processing to prevent UI blocking
    - Optimized audio capture and processing
    - Thread-safe state management
    - Memory-efficient operation
    - Fast wake word detection
    """
    
    # State constants
    WAKE_STATE_INACTIVE = 0
    WAKE_STATE_ACTIVE = 1
    
    def __init__(self, model_size="base", language="en", device="cpu"):
        print("Initializing AudioEngine...")
        
        # Configuration
        self.model_size = model_size
        self.language = language
        self.device = device
        
        # State management (thread-safe)
        self._state_lock = threading.RLock()
        self.wake_state = self.WAKE_STATE_INACTIVE
        self._processing = False
        
        # Performance optimizations
        self._last_command_time = 0
        self._command_cooldown = 2.0  # Prevent duplicate processing
        
        # Audio configuration
        self.chunk = 1024
        self.sample_rate = 16000
        self.channels = 1
        self.format = pyaudio.paInt16
        
        # Initialize components asynchronously to prevent blocking
        print("Initializing AudioEngine...")
        self.cmd_hotword_mgr = CommandManager()
        print("Loading command manager...")
        
        self.tts_mgr = TTSEngine()
        print("Loading TTS engine...")
        
        # CRITICAL FIX: Start TTS worker thread
        self.tts_mgr.start()
        print("TTS worker started")
        
        self.model_mgr = ModelManager()
        print("Loading model manager...")
        
        # Model loading state
        self.model = None
        self._model_ready = False
        
        # Error tracking
        self._last_error = None
        self._last_success_time = None
        
        # Initialize model asynchronously
        self._init_model_async()
        
        print("AudioEngine initialized")
    
    def _init_model_async(self):
        """Initialize model asynchronously to prevent UI blocking"""
        def _init():
            try:
                print(f"Loading model: {self.model_size}")
                self.model = self.model_mgr.load_model(self.model_size)
                
                with self._state_lock:
                    self._model_ready = self.model is not None
                
                if self._model_ready:
                    print(f"Model {self.model_size} loaded successfully")
                else:
                    print(f"Failed to load model {self.model_size}")
                    
            except Exception as e:
                print(f"Model initialization error: {e}")
                self._last_error = str(e)
        
        # Start in background thread
        threading.Thread(target=_init, daemon=True, name="ModelInit").start()
    
    def is_model_ready(self) -> bool:
        """Check if model is ready for use"""
        with self._state_lock:
            return self._model_ready
    
    def wait_for_model(self, timeout: float = 30.0) -> bool:
        """Wait for model to be ready"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_model_ready():
                return True
            time.sleep(0.1)
        return False
    
    def set_wake_state(self, state: int):
        """Set wake state (thread-safe)"""
        if state not in [self.WAKE_STATE_INACTIVE, self.WAKE_STATE_ACTIVE]:
            return False
        
        with self._state_lock:
            self.wake_state = state
        
        state_name = "ACTIVE" if state == 1 else "INACTIVE"
        print(f"Wake state: {state_name}")
        return True
    
    def get_wake_state(self) -> int:
        """Get current wake state"""
        with self._state_lock:
            return self.wake_state
    
    def is_active(self) -> bool:
        """Check if in active state"""
        return self.get_wake_state() == self.WAKE_STATE_ACTIVE
    
    def is_processing(self) -> bool:
        """Check if currently processing"""
        with self._state_lock:
            return self._processing
    
    def record_audio(self, duration: float = 3.0) -> Optional[np.ndarray]:
        """
        Record audio with optimized performance and error handling.
        Non-blocking implementation to prevent UI freezing.
        """
        if duration <= 0:
            return None
        
        frames = []
        audio_interface = None
        stream = None
        
        try:
            # Initialize audio interface
            audio_interface = pyaudio.PyAudio()
            
            # Get default input device
            try:
                device_info = audio_interface.get_default_input_device_info()
                device_index = device_info['index']
            except:
                device_index = None
            
            # Open audio stream
            stream = audio_interface.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk,
                input_device_index=device_index
            )
            
            # Calculate frames to read
            frames_to_read = int(self.sample_rate / self.chunk * duration)
            
            # Record audio
            for _ in range(frames_to_read):
                try:
                    data = stream.read(self.chunk, exception_on_overflow=False)
                    frames.append(data)
                except Exception as e:
                    # Continue recording even if some frames fail
                    continue
            
            if not frames:
                return None
            
            # Convert to numpy array
            audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
            audio_data = audio_data.astype(np.float32) / 32768.0
            
            # Basic quality check
            rms = np.sqrt(np.mean(audio_data**2))
            if rms < 0.001:
                print("Audio too quiet")
                return None
            
            return audio_data
        
        except Exception as e:
            print(f"Audio recording error: {e}")
            return None
        
        finally:
            # Clean up resources
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except:
                    pass
            
            if audio_interface:
                try:
                    audio_interface.terminate()
                except:
                    pass
    
    def detect_wake_word(self, audio_data: np.ndarray, wake_word: str = "susie") -> bool:
        """
        Optimized wake word detection with performance improvements.
        """
        if audio_data is None or not self._model_ready:
            return False
        
        # Prevent concurrent processing
        with self._state_lock:
            if self._processing:
                return False
            self._processing = True
        
        try:
            # Get hotword boost
            boost_phrases = [wake_word] + self.cmd_hotword_mgr.get_boost_phrases(3)
            
            # Transcribe with optimized settings
            text = self._transcribe_optimized(audio_data, boost_phrases, fast_mode=True)
            
            if text:
                text = text.strip().lower()
                detected = wake_word.lower() in text
                
                if detected:
                    print(f"Wake word '{wake_word}' detected")
                    # Quick TTS feedback
                    if self.tts_mgr:
                        self.tts_mgr.speak_status("please speak")
                    return True
            
            return False
        
        except Exception as e:
            print(f"Wake word detection error: {e}")
            return False
        
        finally:
            with self._state_lock:
                self._processing = False
    
    def transcribe(self, audio_data: np.ndarray) -> Optional[str]:
        """
        Optimized transcription with performance improvements.
        """
        if not self.is_active() or audio_data is None or not self._model_ready:
            return None
        
        # Prevent concurrent processing
        with self._state_lock:
            if self._processing:
                return None
            self._processing = True
        
        try:
            # Get hotword boost phrases
            boost_phrases = self.cmd_hotword_mgr.get_boost_phrases(10)
            
            # Transcribe with optimization
            text = self._transcribe_optimized(audio_data, boost_phrases, fast_mode=False)
            
            if text:
                text = text.strip()
                # Apply deduplication to prevent repetitive text
                text = self._deduplicate_text(text)
                print(f"Transcription: '{text}'")
                
                # Track success
                self._last_success_time = time.time()
                return text
            
            return None
        
        except Exception as e:
            print(f"Transcription error: {e}")
            self._last_error = str(e)
            return None
        
        finally:
            with self._state_lock:
                self._processing = False
    
    def _transcribe_optimized(self, audio_data: np.ndarray, boost_phrases: List[str], fast_mode: bool = False) -> Optional[str]:
        """
        Optimized transcription with backend-specific optimizations.
        """
        if not self.model:
            return None
        
        try:
            initial_prompt = ", ".join(boost_phrases) if boost_phrases else None
            
            if BACKEND == "faster-whisper":
                # Optimized parameters for performance
                beam_size = 1 if fast_mode else 2  # Reduced for speed
                
                segments, info = self.model.transcribe(
                    audio_data,
                    language=self.language,
                    beam_size=beam_size,
                    vad_filter=True,
                    initial_prompt=initial_prompt,
                    temperature=0.0,  # Deterministic
                    compression_ratio_threshold=2.4,
                    log_prob_threshold=-1.0,
                    no_speech_threshold=0.6,
                    condition_on_previous_text=False,  # CRITICAL: Prevent repetition
                    word_timestamps=False  # Faster processing
                )
                
                # CRITICAL FIX: Convert generator to list ONCE to avoid re-iteration
                # Limit to first 5 segments to prevent excessive repetition
                segments_list = []
                for i, seg in enumerate(segments):
                    if i >= 5:  # Limit to first 5 segments
                        break
                    if seg.text.strip():
                        segments_list.append(seg.text.strip())
                
                text = " ".join(segments_list)
                
            elif BACKEND == "openai-whisper":
                # OpenAI Whisper parameters
                result = self.model.transcribe(
                    audio_data,
                    language=self.language,
                    fp16=False,
                    initial_prompt=initial_prompt
                )
                text = result["text"]
                
            else:
                return None
            
            return text.strip() if text else None
        
        except Exception as e:
            print(f"Transcription backend error: {e}")
            return None
    
    def match_command(self, text: str, commands: List[str]) -> Optional[str]:
        """
        Match command with cooldown and deduplication to prevent duplicate processing.
        """
        if not text or not commands:
            return None
        
        # CRITICAL FIX: Remove repetitive patterns (e.g., "open camera, open camera, open camera")
        text = self._deduplicate_text(text)
        
        # Check cooldown
        current_time = time.time()
        if current_time - self._last_command_time < self._command_cooldown:
            print(f"Command cooldown active ({self._command_cooldown}s)")
            return None
        
        # Find match using command manager
        matched_command = self.cmd_hotword_mgr.find_best_match(text)
        
        if matched_command:
            # Record usage and update cooldown
            self.cmd_hotword_mgr.record_usage(matched_command, success=True)
            self._last_command_time = current_time
            print(f"Command matched: '{text}' -> '{matched_command}'")
        else:
            print(f"No command match for: '{text}'")
        
        return matched_command
    
    def _deduplicate_text(self, text: str) -> str:
        """
        Remove repetitive patterns from transcribed text.
        e.g., "open camera, open camera, open camera" -> "open camera"
        """
        if not text:
            return text
        
        # Split by common delimiters
        parts = [p.strip() for p in text.replace(',', ' ').split()]
        if not parts:
            return text
        
        # Remove consecutive duplicates
        unique_parts = [parts[0]]
        for part in parts[1:]:
            if part.lower() != unique_parts[-1].lower():
                unique_parts.append(part)
        
        # If we have less than 50% unique content, take only first occurrence
        if len(unique_parts) < len(parts) * 0.5:
            # Find the first complete phrase (up to first comma or 5 words)
            words = text.split(',')[0].split()[:5]
            return ' '.join(words).strip()
        
        return ' '.join(unique_parts)
    
    def reset_wake_state(self):
        """Reset to inactive state"""
        with self._state_lock:
            self.wake_state = self.WAKE_STATE_INACTIVE
            self._processing = False
        
        print("Wake state reset to INACTIVE")
        
        # TTS feedback
        if self.tts_mgr:
            self.tts_mgr.speak_status("stand by")
    
    # Command management interface
    def add_command(self, text: str) -> bool:
        """Add new command"""
        return self.cmd_hotword_mgr.add_command(text)
    
    def remove_command(self, text: str) -> bool:
        """Remove command"""
        return self.cmd_hotword_mgr.remove_command(text)
    
    def get_all_commands(self) -> List[str]:
        """Get all commands"""
        return self.cmd_hotword_mgr.get_all_commands()
    
    def train_command(self, text: str) -> float:
        """Train command"""
        return self.cmd_hotword_mgr.train_command(text)
    
    def get_training_count(self, text: str) -> int:
        """Get training count"""
        return self.cmd_hotword_mgr.get_training_count(text)
    
    # Model management interface
    def switch_model(self, model_name: str) -> bool:
        """Switch model asynchronously"""
        if not model_name or model_name == self.model_size:
            return True
        
        print(f"Switching model: {self.model_size} -> {model_name}")
        
        # Switch asynchronously to prevent blocking
        def _switch():
            try:
                with self._state_lock:
                    self._model_ready = False
                    self._processing = True
                
                new_model = self.model_mgr.load_model(model_name)
                
                with self._state_lock:
                    if new_model:
                        self.model = new_model
                        self.model_size = model_name
                        self._model_ready = True
                        print(f"Model switched to {model_name}")
                        return True
                    else:
                        print(f"Failed to switch to {model_name}")
                        return False
            
            except Exception as e:
                print(f"Model switch error: {e}")
                return False
            
            finally:
                with self._state_lock:
                    self._processing = False
        
        # Run in background
        threading.Thread(target=_switch, daemon=True, name=f"ModelSwitch-{model_name}").start()
        return True
    
    def get_current_model(self) -> str:
        """Get current model name"""
        return self.model_size
    
    def get_available_models(self) -> List[str]:
        """Get available model names"""
        return self.model_mgr.get_available_models()
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        with self._state_lock:
            status = {
                "wake_state": "ACTIVE" if self.wake_state == self.WAKE_STATE_ACTIVE else "INACTIVE",
                "wake_state_raw": self.wake_state,
                "processing": self._processing,
                "model_size": self.model_size,
                "backend": BACKEND,
                "model_loaded": self._model_ready,
                "model_path": "Local cache" if self._model_ready else "Not loaded",
                "model_error": self._last_error or "None",
                "features": {
                    "tts_enabled": True,
                    "hotwords_enabled": True,
                    "offline_mode": True
                }
            }
        
        # Add command statistics
        try:
            cmd_stats = self.cmd_hotword_mgr.get_statistics()
            status["commands"] = cmd_stats
        except:
            status["commands"] = {"total": 0, "most_used": [], "highest_weight": []}
        
        # Add TTS info
        try:
            tts_info = self.tts_mgr.get_engine_info()
            status["tts"] = tts_info
        except:
            status["tts"] = {"engine_type": "unknown", "enabled": False}
        
        # Add model info
        try:
            model_info = self.model_mgr.get_system_info()
            status["local_models"] = model_info
        except:
            status["local_models"] = {"available": [], "error": "Unknown"}
        
        # Add timestamps
        status["last_success"] = time.ctime(self._last_success_time) if self._last_success_time else "None"
        status["last_error"] = self._last_error or "None"
        
        return status
    
    def shutdown(self):
        """Clean shutdown"""
        print("Shutting down AudioEngine...")
        
        # Reset state
        with self._state_lock:
            self.wake_state = self.WAKE_STATE_INACTIVE
            self._processing = False
            self._model_ready = False
        
        # Shutdown components
        if hasattr(self, 'tts_mgr'):
            self.tts_mgr.shutdown()
        
        if hasattr(self, 'cmd_hotword_mgr'):
            self.cmd_hotword_mgr.shutdown()
        
        if hasattr(self, 'model_mgr'):
            self.model_mgr.shutdown()
        
        print("AudioEngine shutdown complete")


# Test the audio engine
if __name__ == "__main__":
    print("Testing AudioEngine...")
    
    engine = AudioEngine()
    
    # Wait for model to load
    if engine.wait_for_model(10):
        print("Model loaded successfully")
        
        # Test commands
        commands = engine.get_all_commands()
        print(f"Commands: {len(commands)}")
        
        # Test system status
        status = engine.get_system_status()
        print(f"System status: {status['wake_state']}")
        
    else:
        print("Model loading timed out")
    
    engine.shutdown()
    print("Test complete!")