#!/usr/bin/env python3
"""
CLI for diagnosing dictation backend availability and status.

This script provides commands to check which backends are available,
why specific backends failed to load, and general system health for
dictation functionality.
"""

import argparse
import json
import sys
from typing import Dict, Any

from .registry import get_backend_registry


def print_backend_status(status: Dict[str, Any], verbose: bool = False) -> None:
    """Print a formatted backend status report."""
    print(f"Backend Status Report")
    print(f"{'=' * 50}")
    print(f"Total backends defined: {status['total_defined']}")
    print(f"Available backends: {status['total_available']}")
    print(f"Failed backends: {status['total_failed']}")
    print()
    
    if status['available']:
        print("✓ Available Backends:")
        for backend in status['available']:
            print(f"  • {backend['name']}: {backend['description']}")
            if verbose:
                print(f"    Dependencies: {', '.join(backend['dependencies']) if backend['dependencies'] else 'None'}")
                if backend['platform_requirements']:
                    print(f"    Platform requirements: {', '.join(backend['platform_requirements'])}")
        print()
    
    if status['failed']:
        print("✗ Failed Backends:")
        for backend in status['failed']:
            print(f"  • {backend['name']}: {backend['description']}")
            print(f"    Error: {backend['error']}")
            if verbose:
                print(f"    Dependencies: {', '.join(backend['dependencies']) if backend['dependencies'] else 'None'}")
                if backend['platform_requirements']:
                    print(f"    Platform requirements: {', '.join(backend['platform_requirements'])}")
        print()


def cmd_status(args) -> None:
    """Show backend status."""
    registry = get_backend_registry()
    status = registry.get_backend_status()
    
    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print_backend_status(status, verbose=args.verbose)


def cmd_list(args) -> None:
    """List available backends."""
    registry = get_backend_registry()
    available = registry.list_available_backends()
    
    if args.json:
        print(json.dumps(available, indent=2))
    else:
        if available:
            print("Available backends:")
            for backend in available:
                print(f"  • {backend}")
        else:
            print("No backends are available.")


def cmd_check(args) -> None:
    """Check if a specific backend is available."""
    registry = get_backend_registry()
    backend_name = args.backend
    
    is_available = registry.is_backend_available(backend_name)
    info = registry.get_backend_info(backend_name)
    
    if args.json:
        result = {
            "backend": backend_name,
            "available": is_available,
            "info": info.__dict__ if info else None
        }
        if not is_available:
            failed_backends = registry.get_failed_backends()
            result["error"] = failed_backends.get(backend_name, "Unknown backend")
        print(json.dumps(result, indent=2))
    else:
        if is_available:
            print(f"✓ Backend '{backend_name}' is available")
            if info and args.verbose:
                print(f"  Description: {info.description}")
                print(f"  Dependencies: {', '.join(info.dependencies) if info.dependencies else 'None'}")
                if info.platform_requirements:
                    print(f"  Platform requirements: {', '.join(info.platform_requirements)}")
        else:
            print(f"✗ Backend '{backend_name}' is not available")
            if info:
                failed_backends = registry.get_failed_backends()
                error = failed_backends.get(backend_name, "Unknown error")
                print(f"  Error: {error}")
                if args.verbose:
                    print(f"  Description: {info.description}")
                    print(f"  Dependencies: {', '.join(info.dependencies) if info.dependencies else 'None'}")
                    if info.platform_requirements:
                        print(f"  Platform requirements: {', '.join(info.platform_requirements)}")
            else:
                print(f"  Unknown backend: {backend_name}")


def cmd_test(args) -> None:
    """Test loading a specific backend."""
    registry = get_backend_registry()
    backend_name = args.backend
    
    try:
        backend_class = registry.get_backend_class(backend_name)
        print(f"✓ Successfully loaded backend '{backend_name}'")
        print(f"  Class: {backend_class.__name__}")
        print(f"  Module: {backend_class.__module__}")
        
        if args.instantiate:
            try:
                # Try to instantiate with a default model
                backend_instance = backend_class("tiny")
                print(f"  ✓ Successfully instantiated backend")
                print(f"  Instance: {backend_instance}")
            except Exception as e:
                print(f"  ✗ Failed to instantiate backend: {e}")
                
    except Exception as e:
        print(f"✗ Failed to load backend '{backend_name}': {e}")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Diagnose dictation backend availability and status"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output in JSON format"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show verbose output"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show overall backend status")
    status_parser.set_defaults(func=cmd_status)
    
    # List command
    list_parser = subparsers.add_parser("list", help="List available backends")
    list_parser.set_defaults(func=cmd_list)
    
    # Check command
    check_parser = subparsers.add_parser("check", help="Check if a backend is available")
    check_parser.add_argument("backend", help="Backend name to check")
    check_parser.set_defaults(func=cmd_check)
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test loading a backend")
    test_parser.add_argument("backend", help="Backend name to test")
    test_parser.add_argument(
        "--instantiate", action="store_true", 
        help="Also try to instantiate the backend"
    )
    test_parser.set_defaults(func=cmd_test)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()