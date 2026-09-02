# ============================================================================
# command_manager.py
# ============================================================================

import json
import os
import shutil
import threading
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher
import sys

class CommandManager:
    """
    Optimized command management system with fast matching and minimal overhead.
    
    Key Features:
    - Fast command matching with fuzzy search
    - Thread-safe operations
    - Lightweight storage
    - Performance optimizations
    """
    
    def __init__(self, data_file: str = "commands_hotwords.json"):
        # Prefer external, user-editable JSON next to the executable
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            bundled_dir = getattr(sys, '_MEIPASS', None)
        else:
            base_dir = os.getcwd()
            bundled_dir = None
        external_path = os.path.abspath(os.path.join(base_dir, data_file))

        # If missing externally but available in bundle, copy it out once
        if not os.path.exists(external_path) and bundled_dir:
            try:
                src = os.path.join(bundled_dir, data_file)
                if os.path.exists(src):
                    os.makedirs(os.path.dirname(external_path), exist_ok=True)
                    shutil.copy2(src, external_path)
            except Exception as e:
                print(f"[CommandMgr] Warning: failed to copy default JSON: {e}")

        self.data_file = external_path
        self._lock = threading.Lock()
        
        # Load data
        self.data = self._load_data()
        
        # Performance settings
        self.min_similarity = 0.6  # Lower threshold for better matches
        self.max_boost_phrases = 10  # Limit for performance
        
        print(f"CommandManager initialized - {len(self.data.get('commands', {}))} commands loaded")
    
    def _load_data(self) -> Dict[str, Any]:
        """
        ENHANCED: Load command data with improved error handling and Unicode support.
        """
        default_data = {
            "commands": {
                "open browser": {"weight": 1.5, "usage_count": 0, "last_used": None},
                "close window": {"weight": 1.3, "usage_count": 0, "last_used": None},
                "play music": {"weight": 1.2, "usage_count": 0, "last_used": None},
                "minimize window": {"weight": 1.1, "usage_count": 0, "last_used": None},
                "maximize window": {"weight": 1.1, "usage_count": 0, "last_used": None}
            },
            "settings": {
                "max_weight": 3.0,
                "weight_decay": 0.98
            }
        }
        
        if os.path.exists(self.data_file):
            try:
                # ENHANCED: Explicit UTF-8 encoding with error handling
                with open(self.data_file, 'r', encoding='utf-8', errors='replace') as f:
                    loaded_data = json.load(f)
                    
                    # Validate data structure
                    if not isinstance(loaded_data, dict):
                        print(f"[CommandMgr] Invalid data format, using defaults")
                        return default_data
                    
                    # Merge with defaults (preserve existing data)
                    for key, value in default_data.items():
                        if key not in loaded_data:
                            loaded_data[key] = value
                    
                    print(f"[CommandMgr] Loaded {len(loaded_data.get('commands', {}))} commands from {self.data_file}")
                    return loaded_data
                    
            except json.JSONDecodeError as e:
                print(f"[CommandMgr] JSON decode error: {e}")
                print(f"[CommandMgr] Creating backup and using defaults")
                self._create_backup()
            except Exception as e:
                print(f"[CommandMgr] Data load error: {e}")
        else:
            print(f"[CommandMgr] Data file not found, using defaults")
        
        return default_data
    
    def _save_data(self):
        """
        ENHANCED: Save data with improved error handling and atomic write.
        FIX #3: Prevent contamination by filtering out unwanted fields.
        """
        def _save():
            temp_file = None
            try:
                with self._lock:
                    # FIX #3: Filter data to prevent contamination
                    filtered_data = self._filter_save_data(self.data)
                    
                    # ENHANCED: Use atomic write pattern (write to temp, then rename)
                    temp_file = f"{self.data_file}.tmp"
                    
                    with open(temp_file, 'w', encoding='utf-8', errors='replace') as f:
                        # CRITICAL: ensure_ascii=False for Unicode support
                        json.dump(filtered_data, f, indent=2, ensure_ascii=False)
                    
                    # Atomic replace (on Windows, need to remove first)
                    if os.path.exists(self.data_file):
                        # Create backup before overwrite
                        backup_file = f"{self.data_file}.bak"
                        try:
                            if os.path.exists(backup_file):
                                os.remove(backup_file)
                            os.rename(self.data_file, backup_file)
                        except:
                            pass
                    
                    os.rename(temp_file, self.data_file)
                    
            except Exception as e:
                print(f"[CommandMgr] Save error: {e}")
                # Clean up temp file on error
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
        
        # Save in background thread to avoid blocking
        threading.Thread(target=_save, daemon=True, name="CommandMgr-Save").start()
    
    def _filter_save_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        FIX #3: Filter data to prevent contamination of commands_hotwords.json.
        Remove unauthorized entries like 'global_settings', 'analytics', etc.
        Only save valid command entries and settings.
        """
        # Whitelist of allowed top-level keys
        allowed_top_keys = {"commands", "settings"}
        
        # Whitelist of allowed command metadata fields
        allowed_cmd_fields = {
            "text", "weight", "usage_count", "success_count", "training_count",
            "created_at", "last_used", "created", "success_rate", "alternatives",
            "category", "confidence_scores", "training_iterations"
        }
        
        filtered = {}
        
        # Filter top-level keys
        for key in allowed_top_keys:
            if key in data:
                if key == "commands":
                    # Filter command entries
                    filtered_commands = {}
                    for cmd_name, cmd_data in data["commands"].items():
                        if isinstance(cmd_data, dict):
                            # Filter command metadata
                            filtered_cmd = {
                                k: v for k, v in cmd_data.items()
                                if k in allowed_cmd_fields
                            }
                            filtered_commands[cmd_name] = filtered_cmd
                    filtered["commands"] = filtered_commands
                else:
                    # Copy settings as-is (already validated structure)
                    filtered[key] = data[key]
        
        return filtered
    
    def _create_backup(self):
        """Create backup of corrupted data file"""
        if os.path.exists(self.data_file):
            try:
                backup_file = f"{self.data_file}.corrupted_{int(time.time())}"
                os.rename(self.data_file, backup_file)
                print(f"[CommandMgr] Corrupted file backed up to: {backup_file}")
            except Exception as e:
                print(f"[CommandMgr] Backup creation error: {e}")
    
    def add_command(self, command: str) -> bool:
        """Add a new command"""
        if not command or not command.strip():
            return False
        
        command = command.strip().lower()
        
        with self._lock:
            if command in self.data["commands"]:
                return False  # Already exists
            
            self.data["commands"][command] = {
                "weight": 1.0,
                "usage_count": 0,
                "last_used": None,
                "created": datetime.now().isoformat()
            }
        
        self._save_data()
        print(f"Command added: '{command}'")
        return True
    
    def remove_command(self, command: str) -> bool:
        """Remove a command"""
        command = command.strip().lower()
        
        with self._lock:
            if command in self.data["commands"]:
                del self.data["commands"][command]
                self._save_data()
                print(f"Command removed: '{command}'")
                return True
        
        return False
    
    def get_all_commands(self) -> List[str]:
        """Get all command names"""
        with self._lock:
            return list(self.data["commands"].keys())
    
    def find_best_match(self, text: str) -> Optional[str]:
        """
        Find best matching command using enhanced disambiguation logic.
        IMPROVED: Prioritizes longer, more specific commands over shorter prefixes.
        Prevents truncation issues like "open robot cell" -> "open robot".
        """
        if not text or not text.strip():
            return None
        
        text = text.strip().lower()
        
        with self._lock:
            commands = self.data["commands"]
            if not commands:
                return None
            
            # SPECIAL-CASE: Disambiguate "open one" vs "open main"
            # If the user says "open one" (or "open 1"), force it to map to "open 1" when available.
            if text in ("open one", "open 1"):
                if "open 1" in commands:
                    print("Command matched (special): '" + text + "' -> 'open 1'")
                    return "open 1"
            
            # STEP 1: Quick exact match check first (highest priority)
            if text in commands:
                print(f"Command matched (exact): '{text}'")
                return text
            
            # STEP 2: Contextual lookahead - Check for longer commands that contain text
            # This prevents premature truncation (e.g., "open robot cell" vs "open robot")
            longer_matches = []
            for cmd in commands:
                if cmd.startswith(text) and len(cmd) > len(text):
                    # Found a longer, more specific command
                    longer_matches.append(cmd)
            
            if longer_matches:
                # Prefer the longest match (most specific)
                best_longer = max(longer_matches, key=len)
                print(f"Command matched (contextual): '{text}' -> '{best_longer}' (longer variant)")
                return best_longer
            
            # STEP 3: Substring containment check (for numbered commands)
            # e.g., "open camera 1", "template 8" should match exactly even with noise
            exact_substring_matches = []
            for cmd in commands:
                # Check if command words are all present in transcribed text
                cmd_words = cmd.split()
                text_words = text.split()
                
                # For numbered/lettered commands, check exact word-level containment
                if len(cmd_words) <= 3:  # Our max word limit
                    if all(word in text_words for word in cmd_words):
                        # Calculate position-aware score
                        positions = [text_words.index(word) for word in cmd_words if word in text_words]
                        if positions == sorted(positions):  # Words in order
                            exact_substring_matches.append((cmd, len(cmd_words)))
            
            if exact_substring_matches:
                # Prefer the match with most words (most specific)
                best_substring = max(exact_substring_matches, key=lambda x: x[1])[0]
                print(f"Command matched (substring): '{text}' -> '{best_substring}'")
                return best_substring
            
            # STEP 4: Prefix-based disambiguation
            # Group commands by prefix and prefer longer matches
            prefix_groups = {}
            for cmd in commands:
                words = cmd.split()
                if len(words) >= 2:
                    prefix = ' '.join(words[:2])  # First 2 words as prefix
                    if prefix not in prefix_groups:
                        prefix_groups[prefix] = []
                    prefix_groups[prefix].append(cmd)
            
            # Check if text matches a prefix group
            text_words = text.split()
            if len(text_words) >= 2:
                text_prefix = ' '.join(text_words[:2])
                if text_prefix in prefix_groups:
                    candidates = prefix_groups[text_prefix]
                    # Among candidates, find best match
                    best_candidate = None
                    best_candidate_score = 0.0
                    
                    for candidate in candidates:
                        similarity = SequenceMatcher(None, text, candidate).ratio()
                        if similarity > best_candidate_score:
                            best_candidate_score = similarity
                            best_candidate = candidate
                    
                    if best_candidate and best_candidate_score >= self.min_similarity:
                        print(f"Command matched (prefix-disambiguated): '{text}' -> '{best_candidate}' (score: {best_candidate_score:.3f})")
                        return best_candidate
            
            # STEP 5: Standard fuzzy matching (last resort)
            best_match = None
            best_score = 0.0
            
            for cmd in commands:
                # Calculate similarity
                similarity = SequenceMatcher(None, text, cmd).ratio()
                
                # Weight-adjusted score
                cmd_data = commands[cmd]
                weight_bonus = (cmd_data.get("weight", 1.0) - 1.0) * 0.1
                score = similarity + weight_bonus
                
                # CRITICAL: Add penalty for shorter commands when text is longer
                # Prevents "open robot" from matching "open robot cell"
                length_diff = len(text.split()) - len(cmd.split())
                if length_diff > 0:
                    score -= length_diff * 0.15  # Penalty for each missing word

                # Additional micro-penalty: avoid mapping "open one" to "open main"
                if text in ("open one", "open 1") and cmd == "open main":
                    score -= 0.25
                
                if score > best_score and similarity >= self.min_similarity:
                    best_score = score
                    best_match = cmd
            
            if best_match:
                print(f"Command matched (fuzzy): '{text}' -> '{best_match}' (score: {best_score:.3f})")
                return best_match
            else:
                print(f"No command match for: '{text}'")
                return None
    
    def record_usage(self, command: str, success: bool = True):
        """Record command usage for weight optimization"""
        command = command.strip().lower()
        
        with self._lock:
            if command in self.data["commands"]:
                cmd_data = self.data["commands"][command]
                cmd_data["usage_count"] = cmd_data.get("usage_count", 0) + 1
                cmd_data["last_used"] = datetime.now().isoformat()
                
                if success:
                    # Increase weight for successful matches
                    current_weight = cmd_data.get("weight", 1.0)
                    max_weight = self.data["settings"].get("max_weight", 3.0)
                    if current_weight < max_weight:
                        cmd_data["weight"] = min(max_weight, current_weight + 0.1)
                
                # Save periodically (every 5 uses)
                if cmd_data["usage_count"] % 5 == 0:
                    self._save_data()
    
    def get_boost_phrases(self, max_count: Optional[int] = None) -> List[str]:
        """
        Get top weighted commands for hotword boosting.
        Performance optimized with caching.
        """
        if max_count is None:
            max_count = self.max_boost_phrases
        
        with self._lock:
            commands = self.data.get("commands", {})
            if not commands:
                return []
            
            # Sort by weight and usage
            sorted_commands = sorted(
                commands.items(),
                key=lambda x: (x[1].get("weight", 1.0), x[1].get("usage_count", 0)),
                reverse=True
            )
            
            return [cmd for cmd, _ in sorted_commands[:max_count]]
    
    def train_command(self, command: str) -> float:
        """Train/boost a command's weight"""
        command = command.strip().lower()
        
        with self._lock:
            if command in self.data["commands"]:
                cmd_data = self.data["commands"][command]
                current_weight = cmd_data.get("weight", 1.0) 
                max_weight = self.data["settings"].get("max_weight", 3.0)
                
                new_weight = min(max_weight, current_weight + 0.2)
                cmd_data["weight"] = new_weight
                
                self._save_data()
                print(f"Command trained: '{command}' weight: {new_weight:.2f}")
                return new_weight
        
        return 1.0
    
    def get_training_count(self, command: str) -> int:
        """Get training/usage count for a command"""
        command = command.strip().lower()
        
        with self._lock:
            cmd_data = self.data.get("commands", {}).get(command, {})
            return cmd_data.get("usage_count", 0)
    
    def get_command_info(self, command: str) -> Dict[str, Any]:
        """Get detailed command information"""
        command = command.strip().lower()
        
        with self._lock:
            return self.data.get("commands", {}).get(command, {})
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get system statistics"""
        with self._lock:
            commands = self.data.get("commands", {})
            if not commands:
                return {"total": 0, "most_used": [], "highest_weight": []}
            
            # Most used commands
            most_used = sorted(
                commands.items(),
                key=lambda x: x[1].get("usage_count", 0),
                reverse=True
            )[:5]
            
            # Highest weight commands
            highest_weight = sorted(
                commands.items(), 
                key=lambda x: x[1].get("weight", 1.0),
                reverse=True
            )[:3]
            
            return {
                "total": len(commands),
                "most_used": [(cmd, data.get("usage_count", 0)) for cmd, data in most_used],
                "highest_weight": [(cmd, data.get("weight", 1.0)) for cmd, data in highest_weight]
            }
    
    def optimize_weights(self):
        """Optimize command weights based on usage patterns"""
        with self._lock:
            commands = self.data.get("commands", {})
            if not commands:
                return
            
            # Apply weight decay to unused commands
            decay_rate = self.data["settings"].get("weight_decay", 0.98)
            current_time = time.time()
            week_seconds = 7 * 24 * 3600
            
            for cmd, data in commands.items():
                last_used = data.get("last_used")
                if last_used:
                    try:
                        last_time = datetime.fromisoformat(last_used).timestamp()
                        if current_time - last_time > week_seconds:
                            # Apply decay to unused commands
                            current_weight = data.get("weight", 1.0)
                            if current_weight > 1.0:
                                data["weight"] = max(1.0, current_weight * decay_rate)
                    except:
                        pass
            
            self._save_data()
            print("Command weights optimized")

    def load_commands_from_json(self) -> bool:
        """Reload commands from JSON file into memory"""
        try:
            with self._lock:
                self.data = self._load_data()
            print("Commands reloaded from JSON")
            return True
        except Exception as e:
            print(f"Reload commands error: {e}")
            return False
    
    def shutdown(self):
        """Clean shutdown"""
        print("Shutting down CommandManager...")
        self._save_data()
        print("CommandManager shutdown complete")


# Test the command manager
if __name__ == "__main__":
    print("Testing CommandManager...")
    
    manager = CommandManager()
    
    # Test commands
    commands = manager.get_all_commands()
    print(f"Commands loaded: {len(commands)}")
    for cmd in commands[:3]:
        print(f"  {cmd}")
    
    # Test matching
    test_queries = ["open main", "open camera", "open report", "open lamp", "open robot", "open robot cell", "open 1", "open 2", "open alarm", "open trend", "open record", "open user admin", "open user logging", "open user log", "open camera 1", "open camera 2", "open camera 3", "open camera 4", "close camera 1", "close camera 2", "close camera 3", "close camera 4", "template A", "template B", "template C", "template 8", "template 9", "template 10", "1 day", "2 day", "3 day", "4 day", "5 day", "6 day", "7 day", "8 day", "9 day", "10 day", "1 week", "2 week", "3 week", "4 week", "5 week", "6 week", "7 week", "8 week", "9 week", "10 week"]
    for query in test_queries:
        match = manager.find_best_match(query)
        print(f"'{query}' -> '{match}'")
    
    # Test boost phrases
    boost = manager.get_boost_phrases(5)
    print(f"Boost phrases: {boost}")
    
    manager.shutdown()
    print("Test complete!")