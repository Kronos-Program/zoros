"""
Test for detecting circular imports in the ZorOS codebase.

This test systematically analyzes the import structure to identify potential
circular dependencies that could cause import failures.
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
import pytest
import networkx as nx


class ImportAnalyzer:
    """Analyzes Python files for import dependencies."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.import_graph = nx.DiGraph()
        self.module_files = {}
        self.import_map = {}
        
    def find_python_files(self) -> List[Path]:
        """Find all Python files in the project."""
        python_files = []
        for path in self.project_root.rglob("*.py"):
            # Skip test files and __pycache__
            if "__pycache__" in str(path) or path.name.startswith("test_"):
                continue
            python_files.append(path)
        return python_files
    
    def get_module_name(self, file_path: Path) -> str:
        """Convert file path to module name."""
        relative_path = file_path.relative_to(self.project_root)
        module_parts = []
        
        for part in relative_path.parts:
            if part.endswith(".py"):
                if part == "__init__.py":
                    continue
                module_parts.append(part[:-3])  # Remove .py extension
            else:
                module_parts.append(part)
        
        return ".".join(module_parts)
    
    def extract_imports(self, file_path: Path) -> List[str]:
        """Extract import statements from a Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module
                        # Handle relative imports
                        if module_name.startswith('.'):
                            # Convert relative import to absolute
                            current_module = self.get_module_name(file_path)
                            current_parts = current_module.split('.')
                            
                            # Count leading dots
                            level = 0
                            for char in module_name:
                                if char == '.':
                                    level += 1
                                else:
                                    break
                            
                            if level > 0:
                                # Remove the relative part
                                relative_module = module_name[level:]
                                if level == 1:
                                    # Same package
                                    base_parts = current_parts[:-1]
                                else:
                                    # Go up multiple levels
                                    base_parts = current_parts[:-level]
                                
                                if relative_module:
                                    absolute_module = ".".join(base_parts + [relative_module])
                                else:
                                    absolute_module = ".".join(base_parts)
                                imports.append(absolute_module)
                        else:
                            imports.append(module_name)
            
            return imports
            
        except (SyntaxError, UnicodeDecodeError) as e:
            print(f"Warning: Could not parse {file_path}: {e}")
            return []
    
    def build_import_graph(self):
        """Build a directed graph of module dependencies."""
        python_files = self.find_python_files()
        
        # Map module names to file paths
        for file_path in python_files:
            module_name = self.get_module_name(file_path)
            self.module_files[module_name] = file_path
            self.import_graph.add_node(module_name)
        
        # Add edges for imports
        for file_path in python_files:
            module_name = self.get_module_name(file_path)
            imports = self.extract_imports(file_path)
            self.import_map[module_name] = imports
            
            for imported_module in imports:
                # Only consider internal modules
                if imported_module.startswith('source'):
                    # Handle submodule imports (e.g., source.interfaces.intake.main)
                    parts = imported_module.split('.')
                    for i in range(len(parts)):
                        potential_module = '.'.join(parts[:i+1])
                        if potential_module in self.module_files:
                            self.import_graph.add_edge(module_name, potential_module)
                            break
    
    def find_circular_imports(self) -> List[List[str]]:
        """Find all circular import chains."""
        try:
            cycles = list(nx.simple_cycles(self.import_graph))
            return cycles
        except nx.NetworkXError:
            return []
    
    def find_strongly_connected_components(self) -> List[Set[str]]:
        """Find strongly connected components (potential circular import groups)."""
        return [scc for scc in nx.strongly_connected_components(self.import_graph) if len(scc) > 1]
    
    def analyze_specific_module(self, module_name: str) -> Dict[str, any]:
        """Analyze a specific module for circular import issues."""
        if module_name not in self.import_graph:
            return {"error": f"Module {module_name} not found"}
        
        # Find all paths that could lead back to this module
        potential_cycles = []
        for target in self.import_graph.successors(module_name):
            try:
                if nx.has_path(self.import_graph, target, module_name):
                    path = nx.shortest_path(self.import_graph, target, module_name)
                    cycle = [module_name] + path
                    potential_cycles.append(cycle)
            except nx.NetworkXNoPath:
                continue
        
        return {
            "module": module_name,
            "file_path": self.module_files.get(module_name),
            "direct_imports": self.import_map.get(module_name, []),
            "potential_cycles": potential_cycles,
            "in_cycles": any(module_name in cycle for cycle in self.find_circular_imports())
        }


def test_no_circular_imports():
    """Test that there are no circular imports in the ZorOS codebase."""
    project_root = Path(__file__).parent.parent
    analyzer = ImportAnalyzer(project_root)
    analyzer.build_import_graph()
    
    cycles = analyzer.find_circular_imports()
    
    if cycles:
        print("\n🔄 CIRCULAR IMPORTS DETECTED:")
        for i, cycle in enumerate(cycles, 1):
            print(f"\nCycle {i}: {' -> '.join(cycle + [cycle[0]])}")
            
            # Show file paths for better debugging
            for module in cycle:
                file_path = analyzer.module_files.get(module, "Unknown")
                print(f"  {module}: {file_path}")
        
        # Provide suggestions for fixing
        print("\n💡 SUGGESTIONS FOR FIXING CIRCULAR IMPORTS:")
        print("1. Move shared code to a separate module")
        print("2. Use late imports (import inside functions)")
        print("3. Restructure code to remove bidirectional dependencies")
        print("4. Use dependency injection instead of direct imports")
        
        pytest.fail(f"Found {len(cycles)} circular import cycles")


def test_analyze_problematic_modules():
    """Analyze specific modules that are known to have import issues."""
    project_root = Path(__file__).parent.parent
    analyzer = ImportAnalyzer(project_root)
    analyzer.build_import_graph()
    
    # Known problematic modules from the error
    problematic_modules = [
        "source.interfaces.intake.main",
        "source.interfaces.dictation_recovery",
        "source.interfaces.enhanced_fiberization",
        "source.interfaces.dictation_stability"
    ]
    
    print("\n🔍 ANALYZING PROBLEMATIC MODULES:")
    
    for module_name in problematic_modules:
        analysis = analyzer.analyze_specific_module(module_name)
        
        print(f"\n📄 Module: {module_name}")
        print(f"   File: {analysis.get('file_path', 'Not found')}")
        print(f"   In cycles: {analysis.get('in_cycles', False)}")
        
        direct_imports = analysis.get('direct_imports', [])
        internal_imports = [imp for imp in direct_imports if imp.startswith('source')]
        
        print(f"   Internal imports ({len(internal_imports)}):")
        for imp in internal_imports[:5]:  # Show first 5
            print(f"     - {imp}")
        if len(internal_imports) > 5:
            print(f"     ... and {len(internal_imports) - 5} more")
        
        potential_cycles = analysis.get('potential_cycles', [])
        if potential_cycles:
            print(f"   ⚠️  Potential cycles: {len(potential_cycles)}")
            for cycle in potential_cycles[:2]:  # Show first 2
                print(f"     - {' -> '.join(cycle)}")


def test_import_depth_analysis():
    """Analyze import depth to identify complex dependency chains."""
    project_root = Path(__file__).parent.parent
    analyzer = ImportAnalyzer(project_root)
    analyzer.build_import_graph()
    
    print("\n📊 IMPORT DEPTH ANALYSIS:")
    
    # Calculate shortest paths from main modules
    entry_points = [
        "source.interfaces.intake.main",
        "scripts.zoros_cli"
    ]
    
    for entry_point in entry_points:
        if entry_point in analyzer.import_graph:
            print(f"\n🚀 Entry point: {entry_point}")
            
            # Find all reachable modules
            reachable = nx.single_source_shortest_path_length(analyzer.import_graph, entry_point)
            
            # Group by depth
            depth_groups = {}
            for module, depth in reachable.items():
                if depth not in depth_groups:
                    depth_groups[depth] = []
                depth_groups[depth].append(module)
            
            for depth in sorted(depth_groups.keys()):
                modules = depth_groups[depth]
                print(f"   Depth {depth}: {len(modules)} modules")
                if depth > 3:  # Show potentially problematic deep imports
                    for module in modules[:3]:
                        print(f"     - {module}")


def test_suggest_import_fixes():
    """Suggest specific fixes for import issues."""
    project_root = Path(__file__).parent.parent
    analyzer = ImportAnalyzer(project_root)
    analyzer.build_import_graph()
    
    print("\n🔧 IMPORT FIX SUGGESTIONS:")
    
    # Look for common patterns that cause circular imports
    suggestions = []
    
    # Pattern 1: Modules that import each other
    for module in analyzer.import_graph.nodes():
        imports = analyzer.import_map.get(module, [])
        for imported in imports:
            if imported in analyzer.import_map:
                imported_imports = analyzer.import_map[imported]
                if module in [imp for imp in imported_imports if imp.startswith('source')]:
                    suggestions.append({
                        "type": "bidirectional",
                        "modules": [module, imported],
                        "suggestion": "Consider extracting shared functionality to a separate module"
                    })
    
    # Pattern 2: Modules with many dependencies
    heavy_importers = []
    for module in analyzer.import_graph.nodes():
        imports = analyzer.import_map.get(module, [])
        internal_imports = [imp for imp in imports if imp.startswith('source')]
        if len(internal_imports) > 10:
            heavy_importers.append((module, len(internal_imports)))
    
    heavy_importers.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n📦 MODULES WITH MANY DEPENDENCIES:")
    for module, count in heavy_importers[:5]:
        print(f"   {module}: {count} internal imports")
        suggestions.append({
            "type": "heavy_importer",
            "module": module,
            "count": count,
            "suggestion": "Consider breaking this module into smaller components"
        })
    
    # Pattern 3: Central modules (imported by many others)
    import_counts = {}
    for module in analyzer.import_graph.nodes():
        import_counts[module] = 0
    
    for imports in analyzer.import_map.values():
        for imported in imports:
            if imported in import_counts:
                import_counts[imported] += 1
    
    central_modules = sorted(import_counts.items(), key=lambda x: x[1], reverse=True)
    
    print(f"\n🌟 CENTRAL MODULES (imported by many):")
    for module, count in central_modules[:5]:
        if count > 0:
            print(f"   {module}: imported by {count} modules")
    
    return suggestions


if __name__ == "__main__":
    # Run tests directly for debugging
    test_no_circular_imports()
    test_analyze_problematic_modules()
    test_import_depth_analysis()
    test_suggest_import_fixes()