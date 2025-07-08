# ZorOS Specification Document: Dictation

## Concept

In ZorOS, a **Dictation** is a structured capture of freeform input — typically voice, but extensible to text or other media — that is recorded, processed, and optionally threaded into routines or knowledge graphs.

Dictations serve as flexible seeds for:

- Creating new Threads, Fibers, or Knowledge Nodes
- Capturing ephemeral thoughts and turning them into actionable items
- Supporting reflection, journaling, or dynamic workflows

## Purpose

- Capture raw, high-fidelity input from the user
- Store original and processed forms separately
- Allow multiple stages of processing (fast transcription, deep transcription, summarization)
- Link dictations into the graph ecosystem as Threads, Notes, or Actions

## Core Properties

| Property | Type | Description |
|:---|:---|:---|
| `dictation_id` | UUID/String | Unique identifier for the Dictation |
| `created_at` | Timestamp | Capture time of the original input |
| `source_type` | Enum | Voice, Text, Audio File, External Input |
| `raw_capture` | Binary/Path | Reference to original audio or text file |
| `quick_transcript` | String | Fast, initial transcription (lower fidelity) |
| `full_transcript` | String | Higher-quality transcription (after deeper processing) |
| `processed_summary` | String | Summarized version of the dictation (optional) |
| `linked_fibers` | List of Fiber IDs | Fibers or Threads created as a result of this dictation |
| `status` | Enum | Draft, Processed, Linked, Archived |
| `metadata` | Dict | Tags, topic hints, language model parameters used |

## Lifecycle States

| State | Meaning |
|:---|:---|
| **Draft** | Raw capture exists, minimal processing done |
| **Processed** | Full transcription or summarization available |
| **Linked** | Content has been linked to Fibers, Threads, or Knowledge Graph |
| **Archived** | Preserved for long-term storage, no immediate workflow attachment |

## Example Dictation

```json
{
  "dictation_id": "dict-001122",
  "created_at": "2025-04-27T09:45:00Z",
  "source_type": "Voice",
  "raw_capture": "/storage/dictations/001122.wav",
  "quick_transcript": "Need to email John about the report, also schedule dentist appointment",
  "full_transcript": "I need to remember to email John about finalizing the project report today. Also, I should call and schedule a dentist appointment for next week.",
  "processed_summary": "Email John (Project Report), Schedule Dentist Appointment",
  "linked_fibers": ["fiber-345", "fiber-346"],
  "status": "Linked",
  "metadata": {
    "priority": "medium",
    "tags": ["reminders", "health", "work"]
  }
}
```

## Notes

- Multiple passes of transcription may be supported (e.g., "Fast" and "Deep" models)
- Metadata can include user-assigned tags or automatic topic extraction
- Dictations can spawn multiple Fibers depending on content complexity
- Dictations can later be searched, reviewed, or reflected upon

## Future Extensions

- **Voice Metadata**: Speaker ID, sentiment, urgency inference
- **Multi-Language Support**: Language detection and auto-processing
- **Chain of Dictations**: Sequential dictations linked into thought threads
- **LLM Enrichment**: Using language models to propose Fiber creation directly from dictations

---

**Summary**: In ZorOS, **Dictations** are the first breath of new routines and knowledge — captured at the moment of inspiration, nurtured into structure, and woven into the user's orchestration graph.
