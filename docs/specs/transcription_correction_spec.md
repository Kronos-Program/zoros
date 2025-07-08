# ZorOS Transcription Correction UI Specification (PyQt Edition)

## Objective

Design a PyQt-based desktop UI to review, correct, and assess dictation transcripts for ZorOS. The UI will allow users to:

* Filter and navigate uncorrected dictations
* Playback audio recordings
* Display original and editable transcripts side by side
* Highlight text differences (additions, deletions, modifications)
* Approve corrections and advance through dictations
* View transcript-level and aggregate accuracy metrics

## Technology Stack

* **Framework**: PyQt6
* **Audio**: PyQt6 Multimedia (QMediaPlayer)
* **Diffing**: `difflib` or external library (e.g., `python-Levenshtein`)
* **Data Storage**: Abstracted Storage Layer (initially JSON/SQLite, later PostgreSQL)

## UI Components & Layout

### MainWindow (QMainWindow)

* **Menu Bar**: File, View, Help
* **Sidebar (QDockWidget)**:

  * Filters: Status (Draft, Processed, Linked), Date Range (QDateEdit), Tags
  * Button: Refresh List
* **Central Widget**: QStackedWidget with two pages:

  1. **DictationListPage**
  2. **CorrectionPage**

### DictationListPage (QWidget)

* **QTableView**: List of dictations (columns: ID, Date, Status, WER Quick→Full, WER Full→Corrected)
* **Buttons**: Open (load selected), Dashboard

### CorrectionPage (QWidget)

* **Audio Player Panel** (top)

  * QMediaPlayer controls: Play, Pause, Seek slider, Timestamp display
* **Transcript Panels** (middle, horizontal split)

  * Left: Original transcript (QTextEdit, read-only)
  * Right: Editable transcript (QTextEdit)
  * Diff Highlighting: use QTextCharFormat to color changes
* **Correction Controls** (bottom)

  * Labels: Current WER metrics
  * Buttons: Save Correction (updates corrected\_transcript), Approve & Next (marks status, loads next)

### DashboardPage (QWidget)

* **Charts**: QChartView (Qt Charts) showing average WER per model
* **Table**: QTableView of dictation metrics and statuses

## Data Interfaces

* **StorageLayer** class with methods:

  * `list_dictations(filter_criteria) -> List[Dictation]`
  * `load_dictation(dictation_id) -> Dictation`
  * `save_correction(dictation_id, corrected_text, wer_metrics)`
  * `get_accuracy_metrics() -> DataFrame` or list for dashboard

* **DictationProcessor** integration:

  * Provides audio file path and transcript texts
  * Computes WER via utility function on save

## Diff Implementation

* Use Python's `difflib.SequenceMatcher` to compute difference ops
* Map ops to text ranges in editable pane and apply formats:

  * Insertions: green background
  * Deletions: red strikethrough in original pane
  * Substitutions: yellow background

## Keyboard Shortcuts

* Next dictation: Ctrl+Right
* Previous dictation: Ctrl+Left
* Save: Ctrl+S
* Approve & Next: Ctrl+Enter

## UX Considerations

* Immediate visual feedback on changes
* Confirmation dialog on unsaved edits when navigating away
* Responsive resizing of panels

## Next Steps

1. Scaffold PyQt6 project structure (`ui/`, `core/`, `storage/`, `processors/`).
2. Build MainWindow with sidebar and stacked widget.
3. Implement DictationListPage with model/view.
4. Develop CorrectionPage, integrate QMediaPlayer.
5. Add diff highlighting logic and save workflow.
6. Create DashboardPage for metrics.
7. Wire up StorageLayer to JSON/SQLite.
8. Iterate on styling and UX polish.
