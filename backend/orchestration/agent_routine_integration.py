"""Agent integration for routine awareness and execution.

This module provides AI agents with comprehensive awareness of the routine registry,
enabling them to discover, understand, and execute routines as part of their
problem-solving capabilities.

Architecture: Bridges routine registry with agent system
Tests: tests/test_agent_routine_integration.py
"""
from __future__ import annotations

import json
from typing import Dict, List, Any, Optional
from pathlib import Path

from zoros.logger import get_logger
from .routine_registry import RoutineRegistry, RoutineDefinition, RoutineMetadata

logger = get_logger(__name__)


class AgentRoutineInterface:
    """Interface for AI agents to interact with the routine registry.
    
    Provides agents with structured access to routine information,
    execution capabilities, and contextual understanding.
    """

    def __init__(self, registry: Optional[RoutineRegistry] = None):
        """Initialize the agent interface.
        
        Args:
            registry: Optional RoutineRegistry instance. Creates default if None.
        """
        self.registry = registry or RoutineRegistry()
        
    def get_routine_awareness_context(self) -> str:
        """Get formatted routine awareness context for agent prompts.
        
        Returns:
            Formatted string containing routine registry overview for agent context
        """
        summary = self.registry.get_agent_summary()
        
        context = f"""# Routine Registry System

I have access to a comprehensive routine registry with {summary['total_routines']} available routines across the following categories:

"""
        # Add category breakdown
        for category, count in summary['categories'].items():
            context += f"- **{category.title()}**: {count} routine(s)\n"
        
        context += "\n## Available Routines\n\n"
        
        # Add routine details
        for routine in summary['routines']:
            context += f"### {routine['name']} (`{routine['id']}`)\n"
            context += f"- **Category**: {routine['category']}\n"
            context += f"- **Duration**: ~{routine['duration_minutes']} minutes\n"
            context += f"- **Difficulty**: {routine['difficulty']}\n"
            context += f"- **Tags**: {', '.join(routine['tags'])}\n"
            context += f"- **Description**: {routine['description']}\n"
            context += f"- **Steps**: {routine['step_count']} total ({routine['executable_steps']} automated, {routine['manual_steps']} manual)\n"
            
            if routine['has_documentation']:
                context += f"- **Documentation**: Available with detailed instructions\n"
            
            context += "\n"
        
        context += """
## Routine Capabilities

I can help you with routines in the following ways:

1. **Discovery**: Search and filter routines by category, tags, or keywords
2. **Information**: Provide detailed information about any routine including steps and documentation
3. **Execution**: Execute automated portions of routines through the orchestration system
4. **Guidance**: Provide step-by-step guidance for manual routine components
5. **Customization**: Help adapt routines to your specific needs and constraints

To interact with routines, I can use commands like:
- List routines: `registry.list_routines(category="daily", tags=["wellness"])`
- Get details: `registry.get_routine("morning_routine")`
- Execute: `registry.execute_routine("morning_routine")`
- Get documentation: `registry.get_routine_documentation("morning_routine")`

## Integration with Zoros System

Routines are integrated with:
- **Turn Registry**: For automated step execution
- **Fiber System**: For tracking and journaling
- **Language Service**: For AI-assisted components
- **CLI Tools**: For command-line routine management
"""
        
        return context

    def search_routines_for_agent(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Search routines with agent-optimized response format.
        
        Args:
            query: Search query from agent
            context: Optional context about agent's current task/goal
            
        Returns:
            Structured response with routine matches and suggestions
        """
        matches = self.registry.search_routines(query)
        
        response = {
            "query": query,
            "match_count": len(matches),
            "matches": [],
            "suggestions": []
        }
        
        for routine in matches:
            routine_info = {
                "id": routine.routine_id,
                "name": routine.name,
                "category": routine.category,
                "description": routine.description,
                "duration_minutes": routine.estimated_duration_minutes,
                "tags": routine.tags,
                "difficulty": routine.difficulty
            }
            response["matches"].append(routine_info)
        
        # Add contextual suggestions
        if context:
            response["suggestions"] = self._generate_contextual_suggestions(query, context, matches)
        
        return response

    def get_routine_execution_plan(self, routine_id: str) -> Dict[str, Any]:
        """Get detailed execution plan for a routine.
        
        Args:
            routine_id: ID of the routine to plan
            
        Returns:
            Detailed execution plan with timing, dependencies, and instructions
        """
        routine = self.registry.get_routine(routine_id)
        if not routine:
            return {"error": f"Routine not found: {routine_id}"}
        
        plan = {
            "routine_id": routine_id,
            "name": routine.metadata.name,
            "total_duration_minutes": routine.metadata.estimated_duration_minutes,
            "difficulty": routine.metadata.difficulty,
            "prerequisites": routine.metadata.prerequisites,
            "execution_phases": []
        }
        
        current_time = 0
        for i, step in enumerate(routine.steps):
            phase = {
                "step_number": i + 1,
                "step_id": step.step_id,
                "name": step.description,
                "type": step.type,
                "start_time_minutes": current_time,
                "duration_minutes": step.estimated_duration_minutes or 5,
                "end_time_minutes": current_time + (step.estimated_duration_minutes or 5)
            }
            
            if step.type == "manual":
                phase["instructions"] = step.manual_instructions
                phase["execution_method"] = "user_guided"
            elif step.turn_id:
                phase["turn_id"] = step.turn_id
                phase["execution_method"] = "automated"
            elif step.code_path:
                phase["code_path"] = step.code_path
                phase["execution_method"] = "scripted"
            
            plan["execution_phases"].append(phase)
            current_time = phase["end_time_minutes"]
        
        return plan

    def get_routine_documentation_summary(self, routine_id: str) -> Dict[str, Any]:
        """Get documentation summary optimized for agent consumption.
        
        Args:
            routine_id: ID of the routine
            
        Returns:
            Structured documentation summary
        """
        routine = self.registry.get_routine(routine_id)
        docs = self.registry.get_routine_documentation(routine_id)
        
        if not routine:
            return {"error": f"Routine not found: {routine_id}"}
        
        summary = {
            "routine_id": routine_id,
            "name": routine.metadata.name,
            "overview": routine.metadata.description,
            "category": routine.metadata.category,
            "tags": routine.metadata.tags,
            "has_full_documentation": docs is not None,
            "step_summaries": []
        }
        
        for step in routine.steps:
            step_summary = {
                "step_id": step.step_id,
                "description": step.description,
                "type": step.type,
                "duration_minutes": step.estimated_duration_minutes
            }
            
            if step.manual_instructions:
                step_summary["guidance"] = step.manual_instructions
            
            summary["step_summaries"].append(step_summary)
        
        if docs:
            # Extract key sections from documentation
            summary["documentation_available"] = True
            summary["key_sections"] = self._extract_doc_sections(docs)
        
        return summary

    def _generate_contextual_suggestions(self, query: str, context: Dict[str, Any], 
                                       matches: List[RoutineMetadata]) -> List[str]:
        """Generate contextual suggestions based on query and context."""
        suggestions = []
        
        # Time-based suggestions
        if "time" in context:
            current_hour = context.get("time", {}).get("hour", 12)
            if 5 <= current_hour <= 10:
                suggestions.append("Consider morning routines for optimal day start")
            elif 18 <= current_hour <= 23:
                suggestions.append("Evening routines can help with wind-down and recovery")
        
        # Goal-based suggestions
        if "goal" in context:
            goal = context["goal"].lower()
            if "energy" in goal or "focus" in goal:
                suggestions.append("Morning routines often include energy-boosting elements")
            elif "sleep" in goal or "relax" in goal:
                suggestions.append("Evening routines focus on relaxation and sleep preparation")
            elif "health" in goal or "wellness" in goal:
                suggestions.append("Daily wellness routines provide comprehensive health support")
        
        # Match-based suggestions
        if not matches:
            suggestions.append("Try broader search terms or explore by category")
            suggestions.append("Use 'daily', 'wellness', or 'maintenance' as starting points")
        elif len(matches) > 5:
            suggestions.append("Consider filtering by tags or category to narrow results")
        
        return suggestions

    def _extract_doc_sections(self, docs: str) -> List[str]:
        """Extract key sections from documentation for agent summary."""
        sections = []
        
        # Simple extraction of markdown headers
        lines = docs.split('\n')
        for line in lines:
            if line.startswith('## ') or line.startswith('### '):
                section = line.lstrip('#').strip()
                if section not in sections:
                    sections.append(section)
        
        return sections[:10]  # Limit to first 10 sections

    def execute_routine_with_agent_feedback(self, routine_id: str, 
                                          context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute routine with detailed feedback for agent monitoring.
        
        Args:
            routine_id: ID of routine to execute
            context: Optional execution context
            
        Returns:
            Detailed execution results with status, timing, and feedback
        """
        execution_result = {
            "routine_id": routine_id,
            "status": "started",
            "start_time": None,
            "end_time": None,
            "steps_completed": 0,
            "steps_total": 0,
            "messages": [],
            "results": {}
        }
        
        try:
            routine = self.registry.get_routine(routine_id)
            if not routine:
                execution_result["status"] = "error"
                execution_result["messages"].append(f"Routine not found: {routine_id}")
                return execution_result
            
            execution_result["steps_total"] = len(routine.steps)
            execution_result["messages"].append(f"Starting execution of {routine.metadata.name}")
            
            # Execute through registry
            results = self.registry.execute_routine(routine_id, context)
            
            execution_result["status"] = "completed"
            execution_result["steps_completed"] = execution_result["steps_total"]
            execution_result["results"] = results
            execution_result["messages"].append("Routine completed successfully")
            
        except Exception as e:
            execution_result["status"] = "failed"
            execution_result["messages"].append(f"Execution failed: {str(e)}")
            logger.error(f"Agent routine execution failed: {e}")
        
        return execution_result


def get_agent_routine_context() -> str:
    """Convenience function to get routine awareness context for agents."""
    interface = AgentRoutineInterface()
    return interface.get_routine_awareness_context()