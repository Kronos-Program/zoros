"""Routine Registry for high-level routine management and agent awareness.

This implements the Routine Registry vision where agents can discover and understand
available routines through a centralized registry that links to documentation and
execution capabilities.

Specification: Based on recovered transcript about routine registry architecture
Architecture: Extends existing RoutineRunner/TurnRegistry foundation
Tests: tests/test_routine_registry.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import yaml

from zoros.logger import get_logger
from .routine_runner import RoutineRunner
from .turn_registry import TurnRegistry

logger = get_logger(__name__)


@dataclass
class RoutineStep:
    """Individual step within a routine."""
    step_id: str
    description: str
    type: str  # 'manual', 'automated', 'hybrid', 'decision', 'merge'
    turn_id: Optional[str] = None  # Link to TurnRegistry
    code_path: Optional[str] = None  # Python automation path
    manual_instructions: Optional[str] = None
    estimated_duration_minutes: Optional[int] = None
    
    # Graph structure support
    branches: Optional[Dict[str, str]] = None  # condition -> next_step_id
    next_step_id: Optional[str] = None  # Simple linear progression
    merge_point: Optional[str] = None  # Step ID where branches reconverge
    condition_handler: Optional[str] = None  # Handler to evaluate conditions
    parallel_execution: bool = False  # Can run in parallel with other steps


@dataclass
class RoutineMetadata:
    """High-level metadata about a routine."""
    routine_id: str
    name: str
    description: str
    category: str  # 'daily', 'weekly', 'maintenance', 'development', 'co-weaving', 'deployment', etc.
    routine_type: str  # 'embodied', 'agent', 'computer', 'hybrid'
    tags: List[str]
    difficulty: str  # 'beginner', 'intermediate', 'advanced'
    estimated_duration_minutes: int
    prerequisites: List[str]
    created_date: str
    last_updated: str
    version: str
    
    # Enhanced categorization
    execution_context: str = "user"  # 'user', 'agent', 'system', 'collaborative'
    automation_level: str = "manual"  # 'manual', 'semi-automated', 'automated'


@dataclass
class RoutineDefinition:
    """Complete definition of a routine."""
    metadata: RoutineMetadata
    steps: List[RoutineStep]
    documentation_path: Optional[str] = None
    notes: Optional[str] = None


class RoutineRegistry:
    """Central registry for routine discovery, documentation, and execution.
    
    Provides agents with high-level awareness of available routines and their
    capabilities, linking to both manual documentation and automated execution.
    """

    def __init__(self, routines_dir: Union[str, Path] = "routines"):
        """Initialize the routine registry.
        
        Args:
            routines_dir: Directory containing routine definitions and documentation
        """
        self.routines_dir = Path(routines_dir)
        self.routines: Dict[str, RoutineDefinition] = {}
        self.turn_registry = TurnRegistry()
        self.routine_runner = RoutineRunner(self.turn_registry)
        
        # Ensure directories exist
        self.routines_dir.mkdir(exist_ok=True)
        (self.routines_dir / "definitions").mkdir(exist_ok=True)
        (self.routines_dir / "docs").mkdir(exist_ok=True)
        
        self._load_routines()

    def _load_routines(self) -> None:
        """Load all routine definitions from the routines directory."""
        definitions_dir = self.routines_dir / "definitions"
        
        for manifest_path in definitions_dir.glob("*.yml"):
            try:
                with open(manifest_path, 'r') as f:
                    data = yaml.safe_load(f)
                
                routine_def = self._parse_routine_definition(data)
                self.routines[routine_def.metadata.routine_id] = routine_def
                logger.info(f"Loaded routine: {routine_def.metadata.name}")
                
            except Exception as e:
                logger.error(f"Failed to load routine from {manifest_path}: {e}")

    def _parse_routine_definition(self, data: Dict[str, Any]) -> RoutineDefinition:
        """Parse routine definition from YAML data."""
        metadata = RoutineMetadata(**data['metadata'])
        
        steps = []
        for step_data in data.get('steps', []):
            steps.append(RoutineStep(**step_data))
        
        return RoutineDefinition(
            metadata=metadata,
            steps=steps,
            documentation_path=data.get('documentation_path'),
            notes=data.get('notes')
        )

    def list_routines(self, category: Optional[str] = None, 
                     tags: Optional[List[str]] = None) -> List[RoutineMetadata]:
        """List available routines with optional filtering.
        
        Args:
            category: Filter by routine category
            tags: Filter by tags (routine must have all specified tags)
            
        Returns:
            List of routine metadata matching filters
        """
        routines = []
        
        for routine_def in self.routines.values():
            # Filter by category
            if category and routine_def.metadata.category != category:
                continue
                
            # Filter by tags
            if tags and not all(tag in routine_def.metadata.tags for tag in tags):
                continue
                
            routines.append(routine_def.metadata)
        
        return sorted(routines, key=lambda x: x.name)

    def get_routine(self, routine_id: str) -> Optional[RoutineDefinition]:
        """Get a complete routine definition by ID."""
        return self.routines.get(routine_id)

    def get_routine_documentation(self, routine_id: str) -> Optional[str]:
        """Get the documentation content for a routine."""
        routine = self.get_routine(routine_id)
        if not routine or not routine.documentation_path:
            return None
            
        doc_path = self.routines_dir / "docs" / routine.documentation_path
        if doc_path.exists():
            return doc_path.read_text()
        return None

    def execute_routine(self, routine_id: str, 
                       context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a routine using the RoutineRunner.
        
        Args:
            routine_id: ID of the routine to execute
            context: Optional context data for execution
            
        Returns:
            Execution results from RoutineRunner
            
        Raises:
            KeyError: If routine_id not found
            ValueError: If routine has no executable steps
        """
        routine = self.get_routine(routine_id)
        if not routine:
            raise KeyError(f"Routine not found: {routine_id}")
        
        # Convert routine steps to RoutineRunner format
        executable_steps = []
        for step in routine.steps:
            if step.turn_id:  # Has executable turn
                step_data = {
                    "turn_id": step.turn_id,
                    "input": context or {}
                }
                executable_steps.append(step_data)
        
        if not executable_steps:
            raise ValueError(f"Routine {routine_id} has no executable steps")
        
        logger.info(f"Executing routine: {routine.metadata.name}")
        return self.routine_runner.run(executable_steps)

    def register_routine(self, routine_def: RoutineDefinition) -> None:
        """Register a new routine in the registry.
        
        Args:
            routine_def: Complete routine definition to register
        """
        routine_id = routine_def.metadata.routine_id
        self.routines[routine_id] = routine_def
        
        # Save to disk
        self._save_routine_definition(routine_def)
        logger.info(f"Registered routine: {routine_def.metadata.name}")

    def _save_routine_definition(self, routine_def: RoutineDefinition) -> None:
        """Save routine definition to disk."""
        definitions_dir = self.routines_dir / "definitions"
        manifest_path = definitions_dir / f"{routine_def.metadata.routine_id}.yml"
        
        # Convert to dict for YAML serialization
        data = {
            'metadata': asdict(routine_def.metadata),
            'steps': [asdict(step) for step in routine_def.steps],
            'documentation_path': routine_def.documentation_path,
            'notes': routine_def.notes
        }
        
        with open(manifest_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def get_agent_summary(self) -> Dict[str, Any]:
        """Get a summary of all routines formatted for agent consumption.
        
        Returns:
            Dictionary containing routine summaries optimized for AI agent understanding
        """
        summary = {
            "total_routines": len(self.routines),
            "categories": {},
            "routines": []
        }
        
        # Categorize routines
        for routine_def in self.routines.values():
            category = routine_def.metadata.category
            if category not in summary["categories"]:
                summary["categories"][category] = 0
            summary["categories"][category] += 1
            
            # Add routine info for agents
            routine_info = {
                "id": routine_def.metadata.routine_id,
                "name": routine_def.metadata.name,
                "description": routine_def.metadata.description,
                "category": routine_def.metadata.category,
                "tags": routine_def.metadata.tags,
                "difficulty": routine_def.metadata.difficulty,
                "duration_minutes": routine_def.metadata.estimated_duration_minutes,
                "step_count": len(routine_def.steps),
                "executable_steps": sum(1 for step in routine_def.steps if step.turn_id),
                "manual_steps": sum(1 for step in routine_def.steps if step.type == "manual"),
                "has_documentation": routine_def.documentation_path is not None
            }
            summary["routines"].append(routine_info)
        
        return summary

    def search_routines(self, query: str) -> List[RoutineMetadata]:
        """Search routines by name, description, or tags.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching routine metadata
        """
        query = query.lower()
        matches = []
        
        for routine_def in self.routines.values():
            metadata = routine_def.metadata
            
            # Search in name, description, and tags
            searchable_text = (
                metadata.name.lower() + " " +
                metadata.description.lower() + " " +
                " ".join(metadata.tags).lower()
            )
            
            if query in searchable_text:
                matches.append(metadata)
        
        return sorted(matches, key=lambda x: x.name)