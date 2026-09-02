# ============================================================================
# model_manager.py
# ============================================================================

import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

# Supported Models Configuration
SUPPORTED_MODELS = {
    "tiny": {"size": "39MB", "speed": "fastest", "accuracy": "basic"},
    "base": {"size": "74MB", "speed": "fast", "accuracy": "good"}, 
    "small": {"size": "244MB", "speed": "medium", "accuracy": "high"},
    "medium": {"size": "769MB", "speed": "slow", "accuracy": "very high"},
    "large": {"size": "1550MB", "speed": "slowest", "accuracy": "best"}
}

class ModelManager:
    """
    Lightweight, thread-safe model manager optimized for performance.
    
    Key Features:
    - Non-blocking model loading
    - Thread-safe operations
    - Memory-efficient caching
    - Fast model switching
    """
    
    def __init__(self, models_dir: str = "local_models"):
        # Resolve models directory to be persistent and next to the executable when frozen
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
            print(f"[ModelManager] Running in FROZEN mode, base_dir: {base_dir}")
        else:
            base_dir = Path.cwd()
            print(f"[ModelManager] Running in DEVELOPMENT mode, base_dir: {base_dir}")
        
        self.models_dir = (base_dir / models_dir).resolve()
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Current state
        self._current_model = None
        self._current_model_name = "base"
        self._is_loading = False
        
        # Model cache (disabled by default for memory efficiency)
        self._model_cache = {}
        self._cache_enabled = False
        
        print(f"[ModelManager] Initialized - Models dir: {self.models_dir}")
        print(f"[ModelManager] Models dir exists: {self.models_dir.exists()}")
        if self.models_dir.exists():
            contents = list(self.models_dir.iterdir())
            print(f"[ModelManager] Contents: {[p.name for p in contents[:5]]}")  # Show first 5
    
    def get_available_models(self) -> List[str]:
        """Get list of available model names"""
        return list(SUPPORTED_MODELS.keys())
    
    def get_model_info(self, model_name: str = None) -> Dict[str, Any]:
        """Get information about a model"""
        if model_name is None:
            model_name = self._current_model_name
            
        info = SUPPORTED_MODELS.get(model_name, {}).copy()
        info.update({
            "name": model_name,
            "loaded": model_name == self._current_model_name and self._current_model is not None,
            "loading": self._is_loading,
            "path": str(self.models_dir / model_name) if model_name else "unknown"
        })
        return info
    
    def load_model(self, model_name: str) -> Optional[object]:
        """
        Load a Whisper model. Returns model object or None if failed.
        This is a blocking operation - use switch_model_async for non-blocking.
        """
        if not model_name or model_name not in SUPPORTED_MODELS:
            print(f"Invalid model name: {model_name}")
            return None
        
        with self._lock:
            # Check cache first
            if self._cache_enabled and model_name in self._model_cache:
                print(f"Using cached model: {model_name}")
                return self._model_cache[model_name]
            
            self._is_loading = True
            
            try:
                print(f"Loading model: {model_name}")
                
                # Try faster-whisper first
                try:
                    from faster_whisper import WhisperModel
                    
                    # CRITICAL FIX for frozen EXE: Check if model exists locally first
                    # faster-whisper expects models in HuggingFace cache format
                    local_model_path = None
                    
                    if self.models_dir.exists():
                        # Check for model in HuggingFace cache structure
                        # Format: models--Systran--faster-whisper-{size}
                        model_folder = f"models--Systran--faster-whisper-{model_name}"
                        hf_cache_path = self.models_dir / model_folder
                        
                        if hf_cache_path.exists():
                            # Find the actual model files in snapshots subfolder
                            snapshots_dir = hf_cache_path / "snapshots"
                            if snapshots_dir.exists():
                                snapshot_dirs = list(snapshots_dir.iterdir())
                                if snapshot_dirs:
                                    local_model_path = str(snapshot_dirs[0])
                                    print(f"[ModelManager] Found local model at: {local_model_path}")
                    
                    # Load model - use local path if available, otherwise download
                    if local_model_path:
                        print(f"[ModelManager] Loading from local path: {local_model_path}")
                        model = WhisperModel(
                            local_model_path,
                            device="cpu",
                            compute_type="int8",
                            num_workers=1
                        )
                    else:
                        print(f"[ModelManager] Downloading model to: {self.models_dir}")
                        model = WhisperModel(
                            model_name,
                            device="cpu",
                            compute_type="int8",
                            download_root=str(self.models_dir),
                            num_workers=1
                        )
                    
                    # Cache if enabled
                    if self._cache_enabled:
                        self._model_cache[model_name] = model
                    
                    self._current_model = model
                    self._current_model_name = model_name
                    
                    print(f"Model {model_name} loaded successfully (faster-whisper)")
                    return model
                    
                except ImportError:
                    print("faster-whisper not available, trying openai-whisper")
                    
                    # Fallback to openai-whisper
                    try:
                        import whisper
                        model = whisper.load_model(model_name, download_root=str(self.models_dir))
                        
                        if self._cache_enabled:
                            self._model_cache[model_name] = model
                        
                        self._current_model = model
                        self._current_model_name = model_name
                        
                        print(f"Model {model_name} loaded successfully (openai-whisper)")
                        return model
                        
                    except ImportError:
                        print("No Whisper backend available")
                        return None
            
            except Exception as e:
                print(f"Model loading error: {e}")
                return None
            
            finally:
                self._is_loading = False
    
    def get_current_model(self) -> tuple:
        """Get current model and name"""
        with self._lock:
            return self._current_model, self._current_model_name
    
    def is_loading(self) -> bool:
        """Check if model is currently loading"""
        with self._lock:
            return self._is_loading
    
    def switch_model_async(self, model_name: str, callback=None):
        """
        Switch model asynchronously to avoid blocking UI.
        callback(success: bool, model_name: str) will be called when done.
        """
        def _switch():
            success = False
            try:
                model = self.load_model(model_name)
                success = model is not None
            except Exception as e:
                print(f"Async model switch error: {e}")
            
            if callback:
                callback(success, model_name)
        
        thread = threading.Thread(target=_switch, daemon=True, name=f"ModelSwitch-{model_name}")
        thread.start()
    
    def cleanup_cache(self):
        """Clean up model cache to free memory"""
        with self._lock:
            if self._model_cache:
                print(f"Cleaning up {len(self._model_cache)} cached models")
                self._model_cache.clear()
                
                # Force garbage collection
                import gc
                gc.collect()
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information for status display"""
        with self._lock:
            total_size = 0
            available_models = []
            
            for model_name, info in SUPPORTED_MODELS.items():
                available_models.append(model_name)
                # Extract size number for calculation
                size_str = info["size"].replace("MB", "").replace("GB", "000")
                try:
                    total_size += int(size_str)
                except:
                    pass
            
            return {
                "offline_mode": True,
                "available_models": available_models,
                "total_size": f"{total_size}MB",
                "current_model": self._current_model_name,
                "model_loaded": self._current_model is not None,
                "loading": self._is_loading,
                "cache_enabled": self._cache_enabled,
                "cached_models": len(self._model_cache),
                "error": "None"
            }
    
    def shutdown(self):
        """Clean shutdown"""
        print("Shutting down ModelManager...")
        self.cleanup_cache()
        
        with self._lock:
            self._current_model = None
            self._is_loading = False
        
        print("ModelManager shutdown complete")


# Test the model manager
if __name__ == "__main__":
    print("Testing ModelManager...")
    
    manager = ModelManager()
    
    # Test model info
    for model in manager.get_available_models():
        info = manager.get_model_info(model)
        print(f"{model}: {info['size']} - {info['speed']}")
    
    # Test system info
    sys_info = manager.get_system_info()
    print(f"System info: {sys_info}")
    
    manager.shutdown()
    print("Test complete!")