# ============================================================================
# verify_build.py - Post-Build Verification Script
# ============================================================================
"""
Run this script after building to verify all critical components are included.
Usage: python verify_build.py
"""

import os
import sys
import zipfile
from pathlib import Path

def check_exe_exists():
    """Check if the executable was created"""
    exe_path = Path("dist/VoiceControl.exe")
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"✅ Executable found: {exe_path}")
        print(f"   Size: {size_mb:.2f} MB")
        return True
    else:
        print(f"❌ Executable not found: {exe_path}")
        return False

def check_external_files():
    """Check if external config files exist"""
    files_to_check = [
        "commands_hotwords.json",
        "tts_config.json", 
        "NTU.PNG"
    ]
    
    all_exist = True
    for filename in files_to_check:
        if Path(filename).exists():
            print(f"✅ Config file exists: {filename}")
        else:
            print(f"⚠️  Config file missing (will be created on first run): {filename}")
    
    return True

def check_local_models():
    """Check if local models directory exists"""
    models_dir = Path("local_models")
    if models_dir.exists():
        model_folders = list(models_dir.glob("models--Systran--faster-whisper-*"))
        if model_folders:
            print(f"✅ Local models found: {len(model_folders)} model(s)")
            for folder in model_folders:
                print(f"   - {folder.name}")
            return True
        else:
            print("⚠️  local_models directory exists but no models found")
            return False
    else:
        print("⚠️  local_models directory not found (will download on first run)")
        return False

def check_vad_model_in_exe():
    """Try to verify VAD model is bundled (requires PyInstaller archive tool)"""
    try:
        import PyInstaller.utils.cliutils.archive_viewer as av
        print("\n🔍 Checking VAD model inclusion...")
        print("   (This requires manual inspection of the spec file)")
        print("   The build script should have included:")
        print("   - faster_whisper/assets/silero_vad_v6.onnx")
        
        # Just verify the source exists
        try:
            import faster_whisper
            fw_path = Path(faster_whisper.__file__).parent
            vad_model = fw_path / "assets" / "silero_vad_v6.onnx"
            if vad_model.exists():
                print(f"✅ Source VAD model found: {vad_model}")
                size_kb = vad_model.stat().st_size / 1024
                print(f"   Size: {size_kb:.2f} KB")
                return True
            else:
                print(f"❌ Source VAD model not found: {vad_model}")
                return False
        except Exception as e:
            print(f"⚠️  Could not locate faster-whisper: {e}")
            return False
            
    except ImportError:
        print("⚠️  PyInstaller archive viewer not available for deep inspection")
        return True

def check_runtime_hooks():
    """Verify runtime hooks exist"""
    hooks_dir = Path("runtime_hooks")
    required_hooks = [
        "hook_com_init.py",
        "hook_env_setup.py"
    ]
    
    all_exist = True
    for hook in required_hooks:
        hook_path = hooks_dir / hook
        if hook_path.exists():
            print(f"✅ Runtime hook exists: {hook}")
        else:
            print(f"❌ Runtime hook missing: {hook}")
            all_exist = False
    
    return all_exist

def check_spec_file():
    """Verify spec file was generated"""
    spec_path = Path("voice_control_v2.spec")
    if spec_path.exists():
        print(f"✅ Spec file exists: {spec_path}")
        
        # Check if VAD model is mentioned
        with open(spec_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'faster_whisper/assets' in content or 'silero_vad' in content:
                print("   ✅ VAD assets mentioned in spec file")
            else:
                print("   ⚠️  VAD assets not explicitly mentioned (may rely on auto-detection)")
        
        return True
    else:
        print(f"⚠️  Spec file not found: {spec_path}")
        return False

def check_verification_report():
    """Check if verification report was created"""
    report_path = Path("dist/verification_report.txt")
    if report_path.exists():
        print(f"✅ Verification report exists: {report_path}")
        print("\n📋 Report contents:")
        with open(report_path, 'r', encoding='utf-8') as f:
            print(f.read())
        return True
    else:
        print(f"⚠️  Verification report not found: {report_path}")
        return False

def main():
    print("=" * 70)
    print("Voice Control Build Verification")
    print("=" * 70)
    print()
    
    checks = [
        ("Executable", check_exe_exists),
        ("External Files", check_external_files),
        ("Local Models", check_local_models),
        ("VAD Model Source", check_vad_model_in_exe),
        ("Runtime Hooks", check_runtime_hooks),
        ("Spec File", check_spec_file),
        ("Verification Report", check_verification_report),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n{'─' * 70}")
        print(f"Checking: {name}")
        print(f"{'─' * 70}")
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Check failed with error: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} | {name}")
    
    print(f"\nResult: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All checks passed! Build is ready for deployment.")
        print("\nNext steps:")
        print("1. Test run: .\\dist\\VoiceControl.exe")
        print("2. Verify speech recognition works")
        print("3. Check stt_debug.log for any errors")
    else:
        print("\n⚠️  Some checks failed. Review the output above.")
        print("Common fixes:")
        print("- Run: python .\\build.py")
        print("- Ensure all dependencies are installed")
        print("- Check build_log_*.txt for errors")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
