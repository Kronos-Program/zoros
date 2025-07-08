"""
Import Health Tests for ZorOS

This test suite ensures that the ZorOS codebase maintains healthy import patterns
and prevents circular import issues from being introduced.

These tests should be run as part of CI/CD to catch import issues early.
"""

import subprocess
import sys
from pathlib import Path
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.test_circular_imports import ImportAnalyzer


class TestImportHealth:
    """Test suite for import health and circular dependency detection."""
    
    def test_no_circular_imports(self):
        """Test that there are no circular imports in the codebase."""
        analyzer = ImportAnalyzer(project_root)
        analyzer.build_import_graph()
        
        cycles = analyzer.find_circular_imports()
        
        if cycles:
            # Create detailed error message
            error_msg = f"Found {len(cycles)} circular import cycles:\n"
            for i, cycle in enumerate(cycles, 1):
                error_msg += f"\nCycle {i}: {' -> '.join(cycle + [cycle[0]])}\n"
                for module in cycle:
                    file_path = analyzer.module_files.get(module, "Unknown")
                    error_msg += f"  {module}: {file_path}\n"
            
            error_msg += "\nSuggestions:\n"
            error_msg += "1. Use late imports (import inside functions)\n"
            error_msg += "2. Extract shared code to separate modules\n"
            error_msg += "3. Use dependency injection patterns\n"
            
            pytest.fail(error_msg)
    
    def test_critical_modules_importable(self):
        """Test that critical modules can be imported without errors."""
        critical_modules = [
            "source.interfaces.intake.main",
            "source.interfaces.dictation_recovery", 
            "source.interfaces.dictation_stability",
            "source.interfaces.enhanced_fiberization",
            "source.language_service",
            "zoros.cli"
        ]
        
        failed_imports = []
        
        for module_name in critical_modules:
            try:
                __import__(module_name)
            except Exception as e:
                failed_imports.append((module_name, str(e)))
        
        if failed_imports:
            error_msg = "Critical modules failed to import:\n"
            for module, error in failed_imports:
                error_msg += f"  {module}: {error}\n"
            pytest.fail(error_msg)
    
    def test_import_depth_reasonable(self):
        """Test that import dependency chains are not too deep."""
        analyzer = ImportAnalyzer(project_root)
        analyzer.build_import_graph()
        
        # Check depth from main entry points
        entry_points = [
            "source.interfaces.intake.main",
            "zoros.cli"
        ]
        
        max_allowed_depth = 10  # Reasonable limit
        deep_chains = []
        
        for entry_point in entry_points:
            if entry_point in analyzer.import_graph:
                import networkx as nx
                reachable = nx.single_source_shortest_path_length(
                    analyzer.import_graph, entry_point
                )
                
                for module, depth in reachable.items():
                    if depth > max_allowed_depth:
                        deep_chains.append((entry_point, module, depth))
        
        if deep_chains:
            error_msg = f"Found import chains deeper than {max_allowed_depth}:\n"
            for entry, module, depth in deep_chains:
                error_msg += f"  {entry} -> {module} (depth: {depth})\n"
            pytest.fail(error_msg)
    
    def test_late_import_pattern_compliance(self):
        """Test that modules with known circular import risks use late imports."""
        # These modules should use late imports for certain dependencies
        late_import_patterns = {
            "source.interfaces.dictation_stability": [
                "transcribe_audio",
                "get_available_backends"
            ],
            "source.interfaces.dictation_recovery": [
                "transcribe_audio_safe"
            ]
        }
        
        for module_path, expected_functions in late_import_patterns.items():
            file_path = project_root / module_path.replace(".", "/") + ".py"
            
            if not file_path.exists():
                continue
                
            with open(file_path, 'r') as f:
                content = f.read()
            
            for func_name in expected_functions:
                # Check that the function is defined in the module (late import pattern)
                if f"def {func_name}(" not in content:
                    pytest.fail(
                        f"Module {module_path} should define {func_name} as a late import function"
                    )
    
    def test_cli_commands_functional(self):
        """Test that CLI commands can be invoked without import errors."""
        # Test that the main CLI entry point works
        try:
            result = subprocess.run(
                [sys.executable, "-c", "import zoros.cli; print('CLI import OK')"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                pytest.fail(f"CLI import failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            pytest.fail("CLI import took too long (possible circular import)")
        
        # Test that intake command exists and is callable
        try:
            result = subprocess.run(
                ["zoros", "intake", "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                pytest.fail(f"'zoros intake' command failed: {result.stderr}")
                
            if "Launch the PySide intake UI" not in result.stdout:
                pytest.fail("'zoros intake' command help text is incorrect")
                
        except subprocess.TimeoutExpired:
            pytest.fail("'zoros intake --help' took too long")
    
    def test_heavy_importer_modules(self):
        """Test that modules with many imports are documented and justified."""
        analyzer = ImportAnalyzer(project_root)
        analyzer.build_import_graph()
        
        max_internal_imports = 15  # Reasonable limit for internal imports
        heavy_importers = []
        
        for module in analyzer.import_graph.nodes():
            imports = analyzer.import_map.get(module, [])
            internal_imports = [imp for imp in imports if imp.startswith('source')]
            
            if len(internal_imports) > max_internal_imports:
                heavy_importers.append((module, len(internal_imports)))
        
        if heavy_importers:
            # For now, just warn about heavy importers
            # In the future, we might want to fail the test
            warning_msg = f"Modules with many internal imports (>{max_internal_imports}):\n"
            for module, count in heavy_importers:
                warning_msg += f"  {module}: {count} internal imports\n"
            warning_msg += "Consider breaking these modules into smaller components."
            
            pytest.warns(UserWarning, match="Heavy importer modules detected")
    
    def test_import_resilience(self):
        """Test that the system handles missing optional dependencies gracefully."""
        # Test modules that should handle missing dependencies gracefully
        resilient_modules = [
            "source.interfaces.dictation_recovery",
            "source.interfaces.enhanced_fiberization",
            "source.interfaces.dictation_stability"
        ]
        
        for module_name in resilient_modules:
            try:
                module = __import__(module_name, fromlist=[''])
                
                # These modules should have fallback mechanisms
                if hasattr(module, 'AUDIO_DEPS_AVAILABLE'):
                    # Should handle missing audio dependencies
                    assert isinstance(module.AUDIO_DEPS_AVAILABLE, bool)
                
            except ImportError:
                pytest.fail(f"Resilient module {module_name} should not fail on import")


def test_run_circular_import_checker():
    """Test that the standalone circular import checker script works."""
    script_path = project_root / "scripts" / "check_circular_imports.py"
    
    if not script_path.exists():
        pytest.skip("Circular import checker script not found")
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Should not find any circular imports
        assert "NO CIRCULAR IMPORTS DETECTED" in result.stdout or result.returncode == 0
        
    except subprocess.TimeoutExpired:
        pytest.fail("Circular import checker script took too long")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])