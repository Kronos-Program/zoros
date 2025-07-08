"""Tests for the RoutineRegistry system."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from source.orchestration.routine_registry import (
    RoutineRegistry, 
    RoutineDefinition, 
    RoutineMetadata, 
    RoutineStep
)
from source.orchestration.agent_routine_integration import AgentRoutineInterface


class TestRoutineRegistry:
    """Test suite for RoutineRegistry functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.routines_dir = self.temp_dir / "routines"
        self.routines_dir.mkdir()
        (self.routines_dir / "definitions").mkdir()
        (self.routines_dir / "docs").mkdir()

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)

    def test_routine_registry_initialization(self):
        """Test RoutineRegistry initializes correctly."""
        registry = RoutineRegistry(self.routines_dir)
        
        assert registry.routines_dir == self.routines_dir
        assert isinstance(registry.routines, dict)
        assert len(registry.routines) == 0

    def test_register_and_retrieve_routine(self):
        """Test registering and retrieving a routine."""
        registry = RoutineRegistry(self.routines_dir)
        
        # Create test routine
        metadata = RoutineMetadata(
            routine_id="test_routine",
            name="Test Routine",
            description="A test routine",
            category="test",
            tags=["testing", "demo"],
            difficulty="beginner",
            estimated_duration_minutes=10,
            prerequisites=[],
            created_date="2025-07-06",
            last_updated="2025-07-06",
            version="1.0"
        )
        
        steps = [
            RoutineStep(
                step_id="step1",
                description="First step",
                type="manual",
                manual_instructions="Do something manually",
                estimated_duration_minutes=5
            ),
            RoutineStep(
                step_id="step2",
                description="Second step",
                type="automated",
                turn_id="test_turn",
                estimated_duration_minutes=5
            )
        ]
        
        routine = RoutineDefinition(metadata=metadata, steps=steps)
        
        # Register routine
        registry.register_routine(routine)
        
        # Verify registration
        assert "test_routine" in registry.routines
        retrieved = registry.get_routine("test_routine")
        assert retrieved is not None
        assert retrieved.metadata.name == "Test Routine"
        assert len(retrieved.steps) == 2

    def test_list_routines_with_filters(self):
        """Test listing routines with category and tag filters."""
        registry = RoutineRegistry(self.routines_dir)
        
        # Register multiple routines
        routine1 = self._create_test_routine("routine1", "daily", ["wellness", "morning"])
        routine2 = self._create_test_routine("routine2", "weekly", ["maintenance"])
        routine3 = self._create_test_routine("routine3", "daily", ["wellness", "evening"])
        
        registry.register_routine(routine1)
        registry.register_routine(routine2)
        registry.register_routine(routine3)
        
        # Test category filter
        daily_routines = registry.list_routines(category="daily")
        assert len(daily_routines) == 2
        
        # Test tag filter
        wellness_routines = registry.list_routines(tags=["wellness"])
        assert len(wellness_routines) == 2
        
        # Test combined filters
        daily_wellness = registry.list_routines(category="daily", tags=["wellness"])
        assert len(daily_wellness) == 2

    def test_search_routines(self):
        """Test routine search functionality."""
        registry = RoutineRegistry(self.routines_dir)
        
        routine = self._create_test_routine("test", "daily", ["wellness"], 
                                          name="Morning Wellness", 
                                          description="A comprehensive morning routine")
        registry.register_routine(routine)
        
        # Test search by name
        results = registry.search_routines("morning")
        assert len(results) == 1
        assert results[0].routine_id == "test"
        
        # Test search by tag
        results = registry.search_routines("wellness")
        assert len(results) == 1
        
        # Test search by description
        results = registry.search_routines("comprehensive")
        assert len(results) == 1

    def test_agent_summary(self):
        """Test agent summary generation."""
        registry = RoutineRegistry(self.routines_dir)
        
        routine1 = self._create_test_routine("routine1", "daily", ["wellness"])
        routine2 = self._create_test_routine("routine2", "daily", ["maintenance"])
        
        registry.register_routine(routine1)
        registry.register_routine(routine2)
        
        summary = registry.get_agent_summary()
        
        assert summary["total_routines"] == 2
        assert "daily" in summary["categories"]
        assert summary["categories"]["daily"] == 2
        assert len(summary["routines"]) == 2

    @patch('source.orchestration.routine_registry.RoutineRunner')
    def test_execute_routine(self, mock_runner_class):
        """Test routine execution."""
        mock_runner = Mock()
        mock_runner.run.return_value = {"step1": "result1"}
        mock_runner_class.return_value = mock_runner
        
        registry = RoutineRegistry(self.routines_dir)
        
        # Create routine with executable step
        routine = self._create_test_routine("test", "daily", ["test"])
        routine.steps[0].turn_id = "test_turn"
        registry.register_routine(routine)
        
        # Execute routine
        results = registry.execute_routine("test")
        
        assert results == {"step1": "result1"}
        mock_runner.run.assert_called_once()

    def _create_test_routine(self, routine_id: str, category: str, tags: list, 
                           name: str = None, description: str = None) -> RoutineDefinition:
        """Helper to create test routine."""
        metadata = RoutineMetadata(
            routine_id=routine_id,
            name=name or f"Test Routine {routine_id}",
            description=description or f"Test routine for {routine_id}",
            category=category,
            tags=tags,
            difficulty="beginner",
            estimated_duration_minutes=10,
            prerequisites=[],
            created_date="2025-07-06",
            last_updated="2025-07-06",
            version="1.0"
        )
        
        steps = [
            RoutineStep(
                step_id="step1",
                description="Test step",
                type="manual",
                manual_instructions="Do something",
                estimated_duration_minutes=10
            )
        ]
        
        return RoutineDefinition(metadata=metadata, steps=steps)


class TestAgentRoutineIntegration:
    """Test suite for agent routine integration."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.routines_dir = self.temp_dir / "routines"
        self.routines_dir.mkdir()
        (self.routines_dir / "definitions").mkdir()
        (self.routines_dir / "docs").mkdir()

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)

    def test_agent_interface_initialization(self):
        """Test AgentRoutineInterface initializes correctly."""
        registry = RoutineRegistry(self.routines_dir)
        interface = AgentRoutineInterface(registry)
        
        assert interface.registry == registry

    def test_get_routine_awareness_context(self):
        """Test generation of routine awareness context."""
        registry = RoutineRegistry(self.routines_dir)
        
        # Add test routine
        metadata = RoutineMetadata(
            routine_id="test",
            name="Test Routine",
            description="A test routine",
            category="daily",
            tags=["wellness"],
            difficulty="beginner",
            estimated_duration_minutes=10,
            prerequisites=[],
            created_date="2025-07-06",
            last_updated="2025-07-06",
            version="1.0"
        )
        
        steps = [RoutineStep(
            step_id="step1",
            description="Test step",
            type="manual",
            estimated_duration_minutes=10
        )]
        
        routine = RoutineDefinition(metadata=metadata, steps=steps)
        registry.register_routine(routine)
        
        interface = AgentRoutineInterface(registry)
        context = interface.get_routine_awareness_context()
        
        assert "Routine Registry System" in context
        assert "Test Routine" in context
        assert "daily" in context
        assert "wellness" in context

    def test_search_routines_for_agent(self):
        """Test agent-optimized routine search."""
        registry = RoutineRegistry(self.routines_dir)
        interface = AgentRoutineInterface(registry)
        
        # Add test routine
        routine = self._create_test_routine("morning", "daily", ["wellness"], 
                                          "Morning Routine")
        registry.register_routine(routine)
        
        # Test search
        result = interface.search_routines_for_agent("morning")
        
        assert result["query"] == "morning"
        assert result["match_count"] == 1
        assert len(result["matches"]) == 1
        assert result["matches"][0]["id"] == "morning"

    def test_get_routine_execution_plan(self):
        """Test execution plan generation."""
        registry = RoutineRegistry(self.routines_dir)
        interface = AgentRoutineInterface(registry)
        
        # Create routine with multiple steps
        metadata = RoutineMetadata(
            routine_id="test",
            name="Test Routine",
            description="A test routine",
            category="daily",
            tags=["test"],
            difficulty="beginner",
            estimated_duration_minutes=20,
            prerequisites=[],
            created_date="2025-07-06",
            last_updated="2025-07-06",
            version="1.0"
        )
        
        steps = [
            RoutineStep(
                step_id="step1",
                description="Manual step",
                type="manual",
                manual_instructions="Do manually",
                estimated_duration_minutes=10
            ),
            RoutineStep(
                step_id="step2",
                description="Automated step",
                type="automated",
                turn_id="test_turn",
                estimated_duration_minutes=10
            )
        ]
        
        routine = RoutineDefinition(metadata=metadata, steps=steps)
        registry.register_routine(routine)
        
        plan = interface.get_routine_execution_plan("test")
        
        assert plan["routine_id"] == "test"
        assert plan["total_duration_minutes"] == 20
        assert len(plan["execution_phases"]) == 2
        assert plan["execution_phases"][0]["execution_method"] == "user_guided"
        assert plan["execution_phases"][1]["execution_method"] == "automated"

    def _create_test_routine(self, routine_id: str, category: str, tags: list, 
                           name: str = None) -> RoutineDefinition:
        """Helper to create test routine."""
        metadata = RoutineMetadata(
            routine_id=routine_id,
            name=name or f"Test Routine {routine_id}",
            description=f"Test routine for {routine_id}",
            category=category,
            tags=tags,
            difficulty="beginner",
            estimated_duration_minutes=10,
            prerequisites=[],
            created_date="2025-07-06",
            last_updated="2025-07-06",
            version="1.0"
        )
        
        steps = [
            RoutineStep(
                step_id="step1",
                description="Test step",
                type="manual",
                estimated_duration_minutes=10
            )
        ]
        
        return RoutineDefinition(metadata=metadata, steps=steps)