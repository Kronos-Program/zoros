"""
Intake UI State Manager

This module manages the state of the intake UI, including edit preservation,
navigation between records, and integration with the decoupled dictation service.

Key Features:
- Edit state preservation across navigation
- Record caching and management  
- Dirty state tracking
- Auto-save functionality
- Service integration

Author: ZorOS Claude Code
Date: 2025-07-05
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import logging

# Add project root to path
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from PySide6.QtCore import QObject, Signal, QTimer
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    class Signal:
        def __init__(self, *args): pass
        def emit(self, *args): pass
        def connect(self, func): pass

logger = logging.getLogger(__name__)


@dataclass
class IntakeRecord:
    """Data structure for intake records."""
    id: str
    timestamp: str
    original_content: str
    current_content: str
    correction: Optional[str]
    audio_path: Optional[str]
    fiber_type: str
    submitted: bool
    is_dirty: bool = False
    last_edited: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.current_content != self.original_content:
            self.is_dirty = True


@dataclass
class NavigationState:
    """Navigation state for the intake UI."""
    current_index: int = -1
    total_records: int = 0
    has_previous: bool = False
    has_next: bool = False
    current_record_id: Optional[str] = None


class IntakeStateManager(QObject if QT_AVAILABLE else object):
    """Manages the state of the intake UI with edit preservation."""
    
    # Signals for UI updates
    if QT_AVAILABLE:
        record_loaded = Signal(dict)           # Record data loaded
        navigation_updated = Signal(dict)      # Navigation state changed
        dirty_state_changed = Signal(bool)     # Edit state changed
        auto_save_triggered = Signal(str)      # Auto-save occurred
        records_refreshed = Signal(int)        # Record count updated
    
    def __init__(self, db_path: Path):
        if QT_AVAILABLE:
            super().__init__()
        
        self.db_path = db_path
        
        # State storage
        self.records: List[IntakeRecord] = []
        self.record_cache: Dict[str, IntakeRecord] = {}
        self.current_record: Optional[IntakeRecord] = None
        self.navigation_state = NavigationState()
        
        # Configuration
        self.auto_save_interval = 30  # seconds
        self.max_cache_size = 100
        
        # Auto-save timer
        if QT_AVAILABLE:
            self.auto_save_timer = QTimer()
            self.auto_save_timer.timeout.connect(self._auto_save)
            self.auto_save_timer.setInterval(self.auto_save_interval * 1000)
            self.auto_save_timer.start()
        
        # Dirty tracking
        self.has_unsaved_changes = False
        
        # Initialize
        self.refresh_records()
    
    def refresh_records(self) -> None:
        """Refresh records from database."""
        try:
            self._ensure_db()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT id, timestamp, content, audio_path, correction, fiber_type, submitted
                    FROM intake 
                    ORDER BY timestamp DESC
                """)
                
                records = []
                for row in cursor.fetchall():
                    record = IntakeRecord(
                        id=row[0],
                        timestamp=row[1],
                        original_content=row[2] or "",
                        current_content=row[2] or "",
                        correction=row[4],
                        audio_path=row[3],
                        fiber_type=row[5] or "dictation",
                        submitted=bool(row[6])
                    )
                    records.append(record)
                
                self.records = records
                self._update_navigation_state()
                
                # Update cache for recently accessed records
                for record in records[:self.max_cache_size]:
                    self.record_cache[record.id] = record
                
                if QT_AVAILABLE:
                    self.records_refreshed.emit(len(records))
                
                logger.info(f"Refreshed {len(records)} intake records")
                
        except Exception as e:
            logger.error(f"Error refreshing records: {e}")
    
    def navigate_to_index(self, index: int) -> bool:
        """Navigate to a specific record index."""
        if not self._is_valid_index(index):
            return False
        
        # Save current record if dirty
        if self.current_record and self.current_record.is_dirty:
            self._save_current_record()
        
        # Load new record
        self.navigation_state.current_index = index
        record = self.records[index]
        
        # Get from cache or create
        if record.id in self.record_cache:
            self.current_record = self.record_cache[record.id]
        else:
            self.current_record = record
            self.record_cache[record.id] = record
        
        self._update_navigation_state()
        
        if QT_AVAILABLE:
            self.record_loaded.emit(asdict(self.current_record))
            self.navigation_updated.emit(asdict(self.navigation_state))
        
        logger.info(f"Navigated to record {index}: {record.id}")
        return True
    
    def navigate_previous(self) -> bool:
        """Navigate to previous record."""
        if self.navigation_state.has_previous:
            return self.navigate_to_index(self.navigation_state.current_index - 1)
        return False
    
    def navigate_next(self) -> bool:
        """Navigate to next record."""
        if self.navigation_state.has_next:
            return self.navigate_to_index(self.navigation_state.current_index + 1)
        return False
    
    def navigate_to_record_id(self, record_id: str) -> bool:
        """Navigate to a specific record by ID."""
        for i, record in enumerate(self.records):
            if record.id == record_id:
                return self.navigate_to_index(i)
        return False
    
    def update_current_content(self, content: str) -> None:
        """Update the content of the current record."""
        if not self.current_record:
            return
        
        old_content = self.current_record.current_content
        self.current_record.current_content = content
        self.current_record.last_edited = datetime.now().isoformat()
        
        # Update dirty state
        was_dirty = self.current_record.is_dirty
        self.current_record.is_dirty = (
            content != self.current_record.original_content
        )
        
        # Update global dirty state
        self._update_global_dirty_state()
        
        # Emit signal if dirty state changed
        if QT_AVAILABLE and was_dirty != self.current_record.is_dirty:
            self.dirty_state_changed.emit(self.current_record.is_dirty)
        
        logger.debug(f"Content updated for record {self.current_record.id}")
    
    def save_current_record(self) -> bool:
        """Explicitly save the current record."""
        if not self.current_record:
            return False
        
        return self._save_current_record()
    
    def save_all_dirty_records(self) -> int:
        """Save all dirty records and return count saved."""
        saved_count = 0
        
        for record in self.record_cache.values():
            if record.is_dirty:
                if self._save_record(record):
                    saved_count += 1
        
        self._update_global_dirty_state()
        
        if QT_AVAILABLE:
            self.auto_save_triggered.emit(f"Saved {saved_count} records")
        
        return saved_count
    
    def create_new_record(self, content: str = "", audio_path: str = "") -> str:
        """Create a new intake record."""
        try:
            from uuid import uuid4
            
            record_id = str(uuid4())
            timestamp = datetime.now().isoformat()
            
            # Create new record
            new_record = IntakeRecord(
                id=record_id,
                timestamp=timestamp,
                original_content=content,
                current_content=content,
                correction=None,
                audio_path=audio_path,
                fiber_type="dictation",
                submitted=False,
                is_dirty=bool(content)  # Dirty if has content
            )
            
            # Insert into database
            self._ensure_db()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO intake (id, timestamp, content, audio_path, correction, fiber_type, submitted)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    record_id, timestamp, content, audio_path, None, "dictation", 0
                ))
                conn.commit()
            
            # Add to records and cache
            self.records.insert(0, new_record)
            self.record_cache[record_id] = new_record
            
            # Navigate to new record
            self.navigate_to_index(0)
            
            logger.info(f"Created new record: {record_id}")
            return record_id
            
        except Exception as e:
            logger.error(f"Error creating new record: {e}")
            return ""
    
    def delete_current_record(self) -> bool:
        """Delete the current record."""
        if not self.current_record:
            return False
        
        try:
            record_id = self.current_record.id
            
            # Remove from database
            self._ensure_db()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM intake WHERE id = ?", (record_id,))
                conn.commit()
            
            # Remove from cache and records
            if record_id in self.record_cache:
                del self.record_cache[record_id]
            
            current_index = self.navigation_state.current_index
            if 0 <= current_index < len(self.records):
                del self.records[current_index]
            
            # Navigate to next available record
            if self.records:
                next_index = min(current_index, len(self.records) - 1)
                self.navigate_to_index(next_index)
            else:
                self.current_record = None
                self._update_navigation_state()
            
            logger.info(f"Deleted record: {record_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting record: {e}")
            return False
    
    def get_current_record(self) -> Optional[IntakeRecord]:
        """Get the current record."""
        return self.current_record
    
    def get_navigation_state(self) -> NavigationState:
        """Get the current navigation state."""
        return self.navigation_state
    
    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self.has_unsaved_changes
    
    def get_dirty_record_count(self) -> int:
        """Get count of dirty (unsaved) records."""
        return sum(1 for record in self.record_cache.values() if record.is_dirty)
    
    def _save_current_record(self) -> bool:
        """Save the current record to database."""
        if not self.current_record:
            return False
        
        return self._save_record(self.current_record)
    
    def _save_record(self, record: IntakeRecord) -> bool:
        """Save a specific record to database."""
        try:
            self._ensure_db()
            
            with sqlite3.connect(self.db_path) as conn:
                # Update the content/correction fields
                conn.execute("""
                    UPDATE intake 
                    SET content = ?, correction = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    record.current_content,
                    record.current_content if record.current_content != record.original_content else record.correction,
                    record.id
                ))
                conn.commit()
            
            # Update record state
            record.original_content = record.current_content
            record.is_dirty = False
            
            logger.info(f"Saved record: {record.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving record {record.id}: {e}")
            return False
    
    def _update_navigation_state(self) -> None:
        """Update the navigation state."""
        total = len(self.records)
        current = self.navigation_state.current_index
        
        self.navigation_state.total_records = total
        self.navigation_state.has_previous = current > 0
        self.navigation_state.has_next = current < total - 1
        
        if 0 <= current < total:
            self.navigation_state.current_record_id = self.records[current].id
        else:
            self.navigation_state.current_record_id = None
    
    def _update_global_dirty_state(self) -> None:
        """Update the global dirty state."""
        old_state = self.has_unsaved_changes
        self.has_unsaved_changes = any(
            record.is_dirty for record in self.record_cache.values()
        )
        
        if QT_AVAILABLE and old_state != self.has_unsaved_changes:
            self.dirty_state_changed.emit(self.has_unsaved_changes)
    
    def _is_valid_index(self, index: int) -> bool:
        """Check if an index is valid."""
        return 0 <= index < len(self.records)
    
    def _auto_save(self) -> None:
        """Auto-save dirty records."""
        if self.has_unsaved_changes:
            saved_count = self.save_all_dirty_records()
            logger.info(f"Auto-saved {saved_count} records")
    
    def _ensure_db(self) -> None:
        """Ensure database exists and has required tables."""
        from source.interfaces.intake.main import _ensure_db
        _ensure_db(self.db_path)


# Global state manager instance
_state_manager = None

def get_intake_state_manager(db_path: Path = None) -> IntakeStateManager:
    """Get or create the global intake state manager."""
    global _state_manager
    if _state_manager is None:
        if db_path is None:
            from source.interfaces.intake.main import DB_PATH
            db_path = DB_PATH
        _state_manager = IntakeStateManager(db_path)
    return _state_manager


if __name__ == "__main__":
    # Test the state manager
    from tempfile import NamedTemporaryFile
    
    with NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = Path(f.name)
    
    manager = IntakeStateManager(test_db)
    
    # Create test record
    record_id = manager.create_new_record("Test content")
    print(f"Created record: {record_id}")
    
    # Update content
    manager.update_current_content("Updated content")
    print(f"Dirty state: {manager.has_unsaved_changes()}")
    
    # Save record
    manager.save_current_record()
    print(f"Dirty state after save: {manager.has_unsaved_changes()}")
    
    test_db.unlink()  # Cleanup