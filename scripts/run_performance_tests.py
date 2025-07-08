#!/usr/bin/env python3
"""Run performance tests for the transcription pipeline.

This script runs comprehensive performance tests on the transcription
pipeline and generates detailed reports for analysis.

Usage:
    python scripts/run_performance_tests.py [mode]
    
Modes:
    test_all  - Test all available backends with different models
    test_main - Test main production configuration (default)
"""
import sys
import os
import json
import argparse
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Also add the current directory to handle relative imports
current_dir = Path.cwd()
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

try:
    from tests.test_transcription_performance import run_performance_tests, TestTranscriptionPerformance
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    print(f"Project root: {project_root}")
    print(f"Test file exists: {(project_root / 'tests' / 'test_transcription_performance.py').exists()}")
    sys.exit(1)


def load_test_config() -> dict:
    """Load the testing configuration from config/testing_config.json."""
    config_path = project_root / "config" / "testing_config.json"
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in configuration file: {e}")
        sys.exit(1)


def load_intake_settings(settings_file: str) -> dict:
    """Load intake settings from the specified file."""
    settings_path = project_root / settings_file
    if not settings_path.exists():
        print(f"Warning: Intake settings file not found: {settings_path}")
        return {}
    
    try:
        with open(settings_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON in intake settings file: {e}")
        return {}


def run_configured_tests(mode: str, config: dict) -> bool:
    """Run tests based on the specified mode and configuration."""
    print(f"Running ZorOS Transcription Performance Tests - Mode: {mode}")
    print("=" * 60)
    
    if mode not in config["test_modes"]:
        print(f"Error: Unknown test mode '{mode}'")
        print(f"Available modes: {list(config['test_modes'].keys())}")
        return False
    
    mode_config = config["test_modes"][mode]
    print(f"Mode: {mode}")
    print(f"Description: {mode_config['description']}")
    print(f"Backends: {', '.join(mode_config['backends'])}")
    print(f"Models: {', '.join(mode_config['models'])}")
    print(f"Default Model: {mode_config['default_model']}")
    
    # Load intake settings if specified
    intake_settings = {}
    if "settings_file" in mode_config:
        intake_settings = load_intake_settings(mode_config["settings_file"])
        if intake_settings:
            print(f"Loaded intake settings from: {mode_config['settings_file']}")
            print(f"  Backend: {intake_settings.get('WhisperBackend', 'Not specified')}")
            print(f"  Model: {intake_settings.get('WhisperModel', 'Not specified')}")
    
    # Create artifacts directory
    artifacts_dir = Path(config["test_parameters"]["artifacts_directory"])
    artifacts_dir.mkdir(exist_ok=True)
    
    # Run the performance tests with mode-specific configuration
    success = run_performance_tests_with_config(mode, mode_config, config, intake_settings)
    
    if success:
        print(f"\n✅ Performance tests completed successfully for mode: {mode}")
        print(f"📊 Results saved to: {artifacts_dir}")
        print("\nGenerated files:")
        for file in artifacts_dir.glob("*.json"):
            print(f"  - {file.name}")
    else:
        print(f"\n❌ Some performance tests failed for mode: {mode}")
        print("Check the output above for details.")
    
    return success


def run_performance_tests_with_config(mode: str, mode_config: dict, config: dict, intake_settings: dict) -> bool:
    """Run performance tests with specific configuration."""
    import unittest
    from unittest import TextTestRunner, TestLoader
    
    # Create test instance
    test_instance = TestTranscriptionPerformance()
    
    # Set configuration attributes
    test_instance.mode_config = mode_config
    test_instance.global_config = config
    test_instance.intake_settings = intake_settings
    
    # Initialize test environment
    test_instance.setUp()
    
    success = True
    tests_run = 0
    tests_failed = 0
    tests_errored = 0
    
    try:
        if mode == "test_all":
            # Run all tests
            print("Running all performance tests...")
            test_instance.test_transcription_backend_performance()
            tests_run += 1
            
            test_instance.test_complete_pipeline_performance()
            tests_run += 1
            
            test_instance.test_memory_usage_over_multiple_transcriptions()
            tests_run += 1
            
            test_instance.test_backend_availability()
            tests_run += 1
            
        elif mode == "test_main":
            # Run only main configuration test
            print("Running main configuration test...")
            test_instance.test_main_configuration_performance()
            tests_run += 1
            
    except Exception as e:
        print(f"Test failed: {e}")
        tests_failed += 1
        success = False
    
    finally:
        # Clean up
        test_instance.tearDown()
    
    # Generate summary report
    report = {
        'timestamp': __import__('datetime').datetime.now().isoformat(),
        'mode': mode,
        'mode_config': mode_config,
        'tests_run': tests_run,
        'tests_failed': tests_failed,
        'tests_errored': tests_errored,
        'success_rate': (tests_run - tests_failed - tests_errored) / tests_run if tests_run > 0 else 0,
        'intake_settings': intake_settings
    }
    
    # Save mode-specific report
    artifacts_dir = Path(config["test_parameters"]["artifacts_directory"])
    report_file = artifacts_dir / f"{mode}_performance_report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n{mode.capitalize()} performance test report saved to: {report_file}")
    print(f"Success rate: {report['success_rate']:.1%}")
    
    return success


def main():
    """Run performance tests and generate reports."""
    parser = argparse.ArgumentParser(description="Run ZorOS transcription performance tests")
    parser.add_argument("mode", nargs="?", default=None, 
                       choices=["test_all", "test_main"],
                       help="Test mode to run (default: from config)")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_test_config()
    
    # Determine mode
    mode = args.mode or config.get("default_mode", "test_main")
    
    print("ZorOS Transcription Performance Test Suite")
    print("=" * 50)
    print(f"Configuration loaded from: config/testing_config.json")
    print(f"Mode: {mode}")
    
    # Run the configured tests
    success = run_configured_tests(mode, config)
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main()) 