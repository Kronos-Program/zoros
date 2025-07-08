#!/usr/bin/env python3
"""
Standalone Circular Import Checker for ZorOS

This script can be run as part of CI/CD pipeline to detect circular imports
before they cause runtime issues.

Usage:
    python scripts/check_circular_imports.py
    python scripts/check_circular_imports.py --fix-suggestions
    python scripts/check_circular_imports.py --module source.interfaces.intake.main
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.test_circular_imports import ImportAnalyzer


def main():
    parser = argparse.ArgumentParser(description="Check for circular imports in ZorOS")
    parser.add_argument(
        "--fix-suggestions", 
        action="store_true", 
        help="Show suggestions for fixing circular imports"
    )
    parser.add_argument(
        "--module", 
        type=str, 
        help="Analyze a specific module for import issues"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed analysis"
    )
    parser.add_argument(
        "--exit-on-error",
        action="store_true",
        help="Exit with error code if circular imports found"
    )
    
    args = parser.parse_args()
    
    print("🔍 ZorOS Circular Import Checker")
    print("=" * 50)
    
    # Initialize analyzer
    analyzer = ImportAnalyzer(project_root)
    analyzer.build_import_graph()
    
    # Check for circular imports
    cycles = analyzer.find_circular_imports()
    
    if cycles:
        print(f"\n❌ FOUND {len(cycles)} CIRCULAR IMPORT CYCLES:")
        print("=" * 50)
        
        for i, cycle in enumerate(cycles, 1):
            print(f"\n🔄 Cycle {i}: {' → '.join(cycle + [cycle[0]])}")
            
            if args.verbose:
                print("   File paths:")
                for module in cycle:
                    file_path = analyzer.module_files.get(module, "Unknown")
                    print(f"     {module}: {file_path}")
        
        if args.fix_suggestions:
            print("\n💡 SUGGESTIONS FOR FIXING CIRCULAR IMPORTS:")
            print("=" * 50)
            suggestions = analyzer.analyze_specific_module("source.interfaces.intake.main")
            
            print("1. 🔧 Use Late Imports (Recommended)")
            print("   - Move imports inside functions that use them")
            print("   - Example: def my_function(): from module import something")
            print()
            print("2. 🏗️  Restructure Dependencies")
            print("   - Extract shared code to a separate module")
            print("   - Create a common base module for shared functionality")
            print()
            print("3. 🔌 Dependency Injection")
            print("   - Pass dependencies as function parameters")
            print("   - Use factory patterns or dependency injection frameworks")
            print()
            print("4. 🎯 Interface Segregation")
            print("   - Define interfaces/protocols for shared contracts")
            print("   - Implement interfaces in separate modules")
        
        if args.exit_on_error:
            sys.exit(1)
    else:
        print("✅ NO CIRCULAR IMPORTS DETECTED")
    
    # Analyze specific module if requested
    if args.module:
        print(f"\n📊 ANALYZING MODULE: {args.module}")
        print("=" * 50)
        
        analysis = analyzer.analyze_specific_module(args.module)
        
        if "error" in analysis:
            print(f"❌ Error: {analysis['error']}")
        else:
            print(f"📄 Module: {analysis['module']}")
            print(f"📁 File: {analysis['file_path']}")
            print(f"🔄 In cycles: {analysis['in_cycles']}")
            
            direct_imports = analysis.get('direct_imports', [])
            internal_imports = [imp for imp in direct_imports if imp.startswith('source')]
            
            print(f"📦 Internal imports: {len(internal_imports)}")
            if args.verbose and internal_imports:
                for imp in internal_imports:
                    print(f"     - {imp}")
            
            potential_cycles = analysis.get('potential_cycles', [])
            if potential_cycles:
                print(f"⚠️  Potential cycles: {len(potential_cycles)}")
                if args.verbose:
                    for cycle in potential_cycles:
                        print(f"     - {' → '.join(cycle)}")
    
    # Show import statistics
    if args.verbose:
        print(f"\n📊 IMPORT STATISTICS:")
        print("=" * 50)
        
        total_modules = len(analyzer.module_files)
        total_edges = len(analyzer.import_graph.edges())
        
        print(f"Total modules analyzed: {total_modules}")
        print(f"Total import relationships: {total_edges}")
        
        if total_modules > 0:
            avg_imports = total_edges / total_modules
            print(f"Average imports per module: {avg_imports:.2f}")
        
        # Find most connected modules
        import_counts = {}
        for module in analyzer.import_graph.nodes():
            import_counts[module] = len(list(analyzer.import_graph.successors(module)))
        
        if import_counts:
            top_importers = sorted(import_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            print(f"\nTop modules by import count:")
            for module, count in top_importers:
                print(f"  {module}: {count} imports")


if __name__ == "__main__":
    main()