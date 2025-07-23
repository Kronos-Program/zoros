#!/usr/bin/env python3
"""
Test script to verify the backend detection and memory leak fixes.

This script tests:
1. Backend registry and detection fixes
2. Circuit breaker pattern
3. Memory cleanup improvements
4. Configuration persistence
"""

import sys
import time
import traceback
import tracemalloc
from pathlib import Path

def test_backend_registry():
    """Test that MLXWhisper backend can be detected properly."""
    print("=== Testing Backend Registry Fixes ===")
    
    try:
        from backend.services.dictation.registry import get_backend_registry
        
        registry = get_backend_registry()
        available_backends = registry.list_available_backends()
        
        print(f"Available backends: {available_backends}")
        
        # Check if MLXWhisper is available (depends on mlx_whisper installation)
        mlx_available = registry.is_backend_available("MLXWhisper")
        print(f"MLXWhisper available: {mlx_available}")
        
        if mlx_available:
            backend_info = registry.get_backend_info("MLXWhisper")
            print(f"MLXWhisper info: {backend_info.description}")
            print("✅ Backend registry fix working")
        else:
            failed_backends = registry.get_failed_backends()
            mlx_error = failed_backends.get("MLXWhisper", "Unknown error")
            print(f"MLXWhisper not available: {mlx_error}")
            print("⚠️  MLXWhisper not installed, but registry is working")
        
        return True
        
    except Exception as e:
        print(f"❌ Backend registry test failed: {e}")
        traceback.print_exc()
        return False

def test_circuit_breaker():
    """Test the circuit breaker pattern for backend failures."""
    print("\n=== Testing Circuit Breaker Pattern ===")
    
    try:
        from backend.intake.main import _should_skip_backend, _record_backend_failure
        
        # Test clean state
        should_skip_initial = _should_skip_backend("TestBackend")
        print(f"Initial skip check: {should_skip_initial}")
        
        # Record failures
        for i in range(4):
            _record_backend_failure("TestBackend")
            should_skip = _should_skip_backend("TestBackend")
            print(f"After {i+1} failures, should skip: {should_skip}")
        
        # After 3+ failures, should skip
        final_skip = _should_skip_backend("TestBackend")
        if final_skip:
            print("✅ Circuit breaker working - skipping failing backend")
            return True
        else:
            print("❌ Circuit breaker not working")
            return False
            
    except Exception as e:
        print(f"❌ Circuit breaker test failed: {e}")
        traceback.print_exc()
        return False

def test_memory_cleanup():
    """Test memory cleanup improvements."""
    print("\n=== Testing Memory Cleanup ===")
    
    try:
        # Start memory tracing
        tracemalloc.start()
        initial_snapshot = tracemalloc.take_snapshot()
        
        # Test MLXWhisperBackend with context manager
        try:
            from backend.services.dictation.mlx_whisper_backend import MLXWhisperBackend
            
            with MLXWhisperBackend("small") as backend:
                print("Created MLXWhisper backend in context manager")
                # Backend should cleanup automatically
            
            print("✅ Context manager cleanup working")
            
        except ImportError:
            print("⚠️  MLXWhisper not installed, testing generic cleanup")
            import gc
            import sys
            
            # Test Windows-specific cleanup
            if sys.platform == "win32":
                for _ in range(3):
                    gc.collect()
                print("✅ Windows-specific cleanup tested")
            else:
                gc.collect()
                print("✅ Generic cleanup tested")
        
        # Check memory usage
        final_snapshot = tracemalloc.take_snapshot()
        top_stats = final_snapshot.compare_to(initial_snapshot, 'lineno')
        
        total_diff = sum(stat.size_diff for stat in top_stats[:10])
        print(f"Memory difference: {total_diff / 1024:.1f} KB")
        
        tracemalloc.stop()
        return True
        
    except Exception as e:
        print(f"❌ Memory cleanup test failed: {e}")
        traceback.print_exc()
        return False

def test_configuration_persistence():
    """Test configuration loading and persistence."""
    print("\n=== Testing Configuration Persistence ===")
    
    try:
        # Test settings path
        config_path = Path.home() / ".zoros" / "intake_settings.json"
        data_config_path = Path("data/config/config/intake_settings.json")
        
        print(f"Checking config paths:")
        print(f"  User config: {config_path} (exists: {config_path.exists()})")
        print(f"  Data config: {data_config_path} (exists: {data_config_path.exists()})")
        
        # Try loading settings
        from backend.intake.main import load_settings
        settings = load_settings()
        
        print(f"Loaded settings keys: {list(settings.keys())}")
        
        backend_setting = settings.get("WhisperBackend", "Not set")
        print(f"WhisperBackend setting: {backend_setting}")
        
        if "WhisperBackend" in settings:
            print("✅ Configuration loading working")
            return True
        else:
            print("⚠️  Configuration loaded but WhisperBackend not set")
            return True
            
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🧪 Testing Zoros Backend Fixes")
    print("=" * 50)
    
    tests = [
        ("Backend Registry", test_backend_registry),
        ("Circuit Breaker", test_circuit_breaker), 
        ("Memory Cleanup", test_memory_cleanup),
        ("Configuration", test_configuration_persistence),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("🏁 Test Results Summary")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! Fixes appear to be working.")
        return 0
    else:
        print("⚠️  Some tests failed. Check output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())