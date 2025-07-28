"""Backlog Registry for managing non-immediate items and future work.

This module provides a structured way to organize and track items that are not
being worked on immediately but need to be captured and organized for future
reference and planning.

Architecture: Complements routine registry with backlog management
Tests: tests/test_backlog_registry.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import yaml

from zoros.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BacklogItem:
    """Individual item in the backlog."""
    item_id: str
    title: str
    description: str
    category: str  # 'feature', 'improvement', 'refactor', 'research', 'documentation'
    priority: str  # 'low', 'medium', 'high', 'critical'
    effort_estimate: str  # 'small', 'medium', 'large', 'epic'
    tags: List[str]
    
    # Organizational structure
    project_id: Optional[str] = None
    related_routines: List[str] = None  # Routine IDs this item relates to
    dependencies: List[str] = None  # Other backlog item IDs this depends on
    blocks: List[str] = None  # Other backlog item IDs this blocks
    
    # Status tracking
    status: str = "backlog"  # 'backlog', 'ready', 'in_progress', 'blocked', 'completed', 'archived'
    created_date: str = ""
    last_updated: str = ""
    target_version: Optional[str] = None
    
    # Context and planning
    business_value: Optional[str] = None
    technical_notes: Optional[str] = None
    acceptance_criteria: List[str] = None

    def __post_init__(self):
        if not self.created_date:
            self.created_date = datetime.now().isoformat()
        if not self.last_updated:
            self.last_updated = self.created_date
        if self.related_routines is None:
            self.related_routines = []
        if self.dependencies is None:
            self.dependencies = []
        if self.blocks is None:
            self.blocks = []
        if self.acceptance_criteria is None:
            self.acceptance_criteria = []


@dataclass 
class BacklogEpic:
    """Collection of related backlog items forming a larger initiative."""
    epic_id: str
    title: str
    description: str
    items: List[str]  # BacklogItem IDs
    priority: str
    target_version: Optional[str] = None
    business_objective: Optional[str] = None
    success_metrics: List[str] = None

    def __post_init__(self):
        if self.success_metrics is None:
            self.success_metrics = []


class BacklogRegistry:
    """Registry for managing backlog items and organizing future work."""

    def __init__(self, backlog_dir: Union[str, Path] = "backlog"):
        """Initialize the backlog registry.
        
        Args:
            backlog_dir: Directory containing backlog definitions
        """
        self.backlog_dir = Path(backlog_dir)
        self.items: Dict[str, BacklogItem] = {}
        self.epics: Dict[str, BacklogEpic] = {}
        
        # Ensure directories exist
        self.backlog_dir.mkdir(exist_ok=True)
        (self.backlog_dir / "items").mkdir(exist_ok=True)
        (self.backlog_dir / "epics").mkdir(exist_ok=True)
        
        self._load_backlog()

    def _load_backlog(self) -> None:
        """Load all backlog items and epics from disk."""
        # Load items
        items_dir = self.backlog_dir / "items"
        for item_path in items_dir.glob("*.yml"):
            try:
                with open(item_path, 'r') as f:
                    data = yaml.safe_load(f)
                
                item = BacklogItem(**data)
                self.items[item.item_id] = item
                logger.debug(f"Loaded backlog item: {item.title}")
                
            except Exception as e:
                logger.error(f"Failed to load backlog item from {item_path}: {e}")

        # Load epics
        epics_dir = self.backlog_dir / "epics" 
        for epic_path in epics_dir.glob("*.yml"):
            try:
                with open(epic_path, 'r') as f:
                    data = yaml.safe_load(f)
                
                epic = BacklogEpic(**data)
                self.epics[epic.epic_id] = epic
                logger.debug(f"Loaded backlog epic: {epic.title}")
                
            except Exception as e:
                logger.error(f"Failed to load backlog epic from {epic_path}: {e}")

    def add_item(self, item: BacklogItem) -> None:
        """Add a new item to the backlog."""
        item.last_updated = datetime.now().isoformat()
        self.items[item.item_id] = item
        self._save_item(item)
        logger.info(f"Added backlog item: {item.title}")

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> None:
        """Update an existing backlog item."""
        if item_id not in self.items:
            raise KeyError(f"Backlog item not found: {item_id}")
        
        item = self.items[item_id]
        for key, value in updates.items():
            if hasattr(item, key):
                setattr(item, key, value)
        
        item.last_updated = datetime.now().isoformat()
        self._save_item(item)
        logger.info(f"Updated backlog item: {item.title}")

    def get_items_by_category(self, category: str) -> List[BacklogItem]:
        """Get all items in a specific category."""
        return [item for item in self.items.values() if item.category == category]

    def get_items_by_priority(self, priority: str) -> List[BacklogItem]:
        """Get all items with a specific priority."""
        return [item for item in self.items.values() if item.priority == priority]

    def get_items_by_status(self, status: str) -> List[BacklogItem]:
        """Get all items with a specific status."""
        return [item for item in self.items.values() if item.status == status]

    def get_ready_items(self) -> List[BacklogItem]:
        """Get items that are ready to be worked on (no blocking dependencies)."""
        ready_items = []
        for item in self.items.values():
            if item.status == "ready":
                ready_items.append(item)
            elif item.status == "backlog" and self._are_dependencies_met(item):
                ready_items.append(item)
        
        return sorted(ready_items, key=lambda x: self._priority_score(x.priority), reverse=True)

    def _are_dependencies_met(self, item: BacklogItem) -> bool:
        """Check if all dependencies for an item are completed."""
        for dep_id in item.dependencies:
            if dep_id in self.items:
                dep_item = self.items[dep_id]
                if dep_item.status not in ["completed", "archived"]:
                    return False
        return True

    def _priority_score(self, priority: str) -> int:
        """Convert priority string to numeric score for sorting."""
        scores = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        return scores.get(priority, 0)

    def search_items(self, query: str) -> List[BacklogItem]:
        """Search backlog items by title, description, or tags."""
        query = query.lower()
        matches = []
        
        for item in self.items.values():
            searchable_text = (
                item.title.lower() + " " +
                item.description.lower() + " " +
                " ".join(item.tags).lower()
            )
            
            if query in searchable_text:
                matches.append(item)
        
        return matches

    def get_blocked_items(self) -> List[BacklogItem]:
        """Get items that are blocked by dependencies."""
        blocked = []
        for item in self.items.values():
            if item.status == "blocked" or (item.dependencies and not self._are_dependencies_met(item)):
                blocked.append(item)
        return blocked

    def get_backlog_summary(self) -> Dict[str, Any]:
        """Get summary statistics for the backlog."""
        summary = {
            "total_items": len(self.items),
            "by_status": {},
            "by_priority": {},
            "by_category": {},
            "ready_count": len(self.get_ready_items()),
            "blocked_count": len(self.get_blocked_items())
        }
        
        for item in self.items.values():
            # Count by status
            status = item.status
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            
            # Count by priority
            priority = item.priority
            summary["by_priority"][priority] = summary["by_priority"].get(priority, 0) + 1
            
            # Count by category
            category = item.category
            summary["by_category"][category] = summary["by_category"].get(category, 0) + 1
        
        return summary

    def create_restructuring_plan(self) -> List[BacklogItem]:
        """Get items specifically related to restructuring plan."""
        return [item for item in self.items.values() 
                if "restructuring" in item.tags or item.category == "refactor"]

    def _save_item(self, item: BacklogItem) -> None:
        """Save backlog item to disk."""
        items_dir = self.backlog_dir / "items"
        item_path = items_dir / f"{item.item_id}.yml"
        
        with open(item_path, 'w') as f:
            yaml.dump(asdict(item), f, default_flow_style=False, sort_keys=False)

    def _save_epic(self, epic: BacklogEpic) -> None:
        """Save backlog epic to disk."""
        epics_dir = self.backlog_dir / "epics"
        epic_path = epics_dir / f"{epic.epic_id}.yml"
        
        with open(epic_path, 'w') as f:
            yaml.dump(asdict(epic), f, default_flow_style=False, sort_keys=False)