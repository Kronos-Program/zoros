# Dictation Library

The Dictation Library provides a comprehensive interface for viewing, editing, and managing all dictation objects stored in the intake database. It shows both submitted and unsubmitted dictations, allows editing of transcriptions, and provides audio playback capabilities.

**Specification:** [docs/requirements/dictation_requirements.md](docs/requirements/dictation_requirements.md#data-model)  
**Architecture:** [docs/zoros_architecture.md](docs/zoros_architecture.md#ui-blueprint)  
**Implementation:** [source/interfaces/intake/dictation_library.py](source/interfaces/intake/dictation_library.py)  
**Tests:** [tests/test_dictation_library.py](tests/test_dictation_library.py)  
**Integration:** [source/interfaces/intake/main.py](source/interfaces/intake/main.py#open_dictation_library)

## Features

### Core Functionality
- **View All Dictations**: Browse all dictation objects in the database
- **Status Tracking**: Distinguish between submitted and draft dictations
- **Content Editing**: Edit transcriptions and corrections
- **Audio Playback**: Play associated audio files
- **Real-time Updates**: Auto-refresh every 5 seconds

### Filtering and Search
- **Status Filter**: Filter by "All", "Draft", or "Submitted" status
- **Type Filter**: Filter by "dictation" or "free_text" type
- **Date Range**: Filter by creation date
- **Content Search**: Search within dictation content
- **Combined Filters**: Apply multiple filters simultaneously

### Management Features
- **Create New Dictations**: Add new empty dictations
- **Edit Content**: Modify transcriptions and corrections
- **Mark as Submitted**: Change draft status to submitted
- **Delete Dictations**: Remove dictations from the database
- **Export Data**: Export filtered dictations to JSON

## Usage

### Opening the Library
1. **From Intake UI**: Click the "Dictation Library" button in the main intake window
2. **Direct Launch**: Run `python -m source.interfaces.intake.dictation_library`

### Interface Layout
- **Left Panel**: Filters and dictation table
- **Right Panel**: Detail view with content editor and metadata
- **Status Bar**: Shows current status and operation results

### Working with Dictations

#### Viewing Dictations
- The table shows: ID, Status, Type, Date, Content Preview, and Audio indicator
- Click on any row to view details in the right panel
- Status colors: Green for submitted, Orange for drafts

#### Editing Content
1. Select a dictation from the table
2. Edit the content in the text area
3. Click "Save Changes" to update the database
4. The table will refresh to show updated content

#### Managing Status
- **Draft Dictations**: Show "Mark as Submitted" button
- **Submitted Dictations**: Show as green in the status column
- **New Transcriptions**: Start as drafts until manually submitted

#### Audio Playback
- Audio files are indicated with 🔊 icon in the table
- Click "Play Audio" in the metadata tab to play associated audio
- Audio files must exist at the stored path to be playable

## Database Schema

The dictation library works with the `intake` table which includes:

```sql
CREATE TABLE intake (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    content TEXT,
    audio_path TEXT,
    correction TEXT,
    fiber_type TEXT,
    submitted INTEGER DEFAULT 1
);
```

### Field Descriptions
- `id`: Unique identifier for the dictation
- `timestamp`: ISO format timestamp of creation
- `content`: Original transcription content
- `audio_path`: Path to associated audio file (optional)
- `correction`: Corrected/edited version of content (optional)
- `fiber_type`: Type of dictation ("dictation" or "free_text")
- `submitted`: Boolean flag (1=submitted, 0=draft)

## Workflow Integration

### Intake UI Integration
- New transcriptions are saved as drafts initially
- Users can edit transcriptions before submitting
- Submit button marks dictations as submitted
- Library button provides quick access to all dictations

### Data Flow
1. **Recording**: Audio is recorded and transcribed
2. **Draft Creation**: Transcription is saved as unsubmitted draft
3. **Editing**: User can edit content in intake UI or library
4. **Submission**: User clicks submit to mark as submitted
5. **Management**: Library provides ongoing access and editing

## Export Functionality

The library can export filtered dictations to JSON format:

```json
[
  {
    "id": "uuid-string",
    "timestamp": "2025-01-01T12:00:00",
    "content": "Original content",
    "correction": "Corrected content",
    "audio_path": "/path/to/audio.wav",
    "fiber_type": "dictation",
    "submitted": true,
    "status": "Submitted"
  }
]
```

## Testing

Run the test suite to verify functionality:

```bash
python -m pytest tests/test_dictation_library.py -v
```

Tests cover:
- DictationItem class functionality
- Database schema compatibility
- Filtering and search functionality
- Window creation and data loading

## Configuration

The library uses the same database as the intake UI (`zoros_intake.db`) and respects the same configuration settings. No additional configuration is required.

## Troubleshooting

### Common Issues
1. **Audio Not Playing**: Check that audio files exist at the stored paths
2. **Database Errors**: Ensure the database has the correct schema with the `submitted` column
3. **UI Not Loading**: Check that PySide6 is properly installed

### Logging
The library logs to `logs/dictation_library.log` for debugging purposes.

## Future Enhancements

Potential improvements:
- Bulk operations (delete multiple, mark multiple as submitted)
- Advanced search with regex support
- Audio waveform visualization
- Integration with external transcription services
- Export to various formats (CSV, XML, etc.)
- Tagging and categorization system 