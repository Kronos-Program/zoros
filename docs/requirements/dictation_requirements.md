# ZorOS Dictation Needs, Requirements, and Specifications

**Implementation:** [source/interfaces/intake/main.py](source/interfaces/intake/main.py)  
**Library:** [source/interfaces/intake/dictation_library.py](source/interfaces/intake/dictation_library.py)  
**Backends:** [source/dictation_backends/](source/dictation_backends/)  
**Tests:** [tests/test_intake_pipeline.py](tests/test_intake_pipeline.py), [tests/test_dictation_library.py](tests/test_dictation_library.py)  
**Documentation:** [docs/dictation_library.md](docs/dictation_library.md), [docs/dictation.md](docs/dictation.md)  
**Architecture:** [docs/zoros_architecture.md](docs/zoros_architecture.md#ui-blueprint)

## 1. Needs

1. **Instant Capture**: Hotkey-triggered start/stop within 1 s latency.  
2. **High-Fidelity Audio**: Save raw audio (16 kHz mono WAV) for reprocessing.  
3. **Fast Feedback**: Provide a quick transcript within 5× real-time.  
4. **Deep Accuracy**: Secondary transcription pass with higher quality.  
5. **Custom Vocabulary**: Inject lexicon terms to boost recognition of user-specific words.  
6. **User Correction**: Inline editing of transcripts with diff highlighting.  
7. **Clipboard Integration**: Copy transcript segments or summary automatically.  
8. **Storage & Traceability**: Persist audio, transcripts (fast, full, corrected), and accuracy metrics.  
9. **Modular Processing**: Hand off transcripts to downstream modules (chunking, threading).  
10. **Error Detection**: Compute WER and flag low-confidence dictations.

---

## 2. Requirements

### Functional Requirements {#functional-requirements}

| ID | Feature | Description |
|---|---|---|
| F1 | Hotkey Control | Globally capture hotkey to start/stop recording |
| F2 | Audio Recording | Record 16 kHz mono WAV until stop signal |
| F3 | Fast Transcription | Local model (Whisper-turbo) fast pass |
| F4 | Deep Transcription | Local/remote high-quality pass |
| F5 | Lexicon Injection | Pre‑load custom word list into transcription pipeline |
| F6 | Correction UI | Show original vs. editable transcript with diff highlighting |
| F7 | Clipboard Export | Copy selected transcript to clipboard |
| F8 | Data Persistence | Save audio + transcripts + metadata in storage layer |
| F9 | Accuracy Metrics | Compute & display WER quick→full & full→corrected |
| F10 | Export for Processing | Provide transcript to next module via API or file |

### Non-Functional Requirements {#non-functional-requirements}

| ID | Requirement | Target |
|---|---|---|
| N1 | Latency | Start recording <1 s after hotkey |
| N2 | Throughput | Fast transcript ≤5× real-time |
| N3 | Scalability | Support 1000+ dictations stored locally |
| N4 | Extensibility | Pluggable UI & back-end adapters |
| N5 | Reliability | 99% success rate without lost audio |
| N6 | Usability | Keyboard-driven workflow; minimal clicks |
| N7 | Privacy | All processing local-first; optional API fallback |
| N8 | Testability | Core logic unit-testable via adapter mocks |

---

## 3. Specifications

### 3.1 Data Model {#data-model}

```json
Dictation {
  id: UUID,
  timestamp: ISO8601,
  audio_path: String,
  quick_transcript: String,
  full_transcript: String,
  corrected_transcript: String,
  lexicon_terms: [String],
  wer_qf: Float,
  wer_fc: Float,
  status: Enum(Draft, Processed, Linked),
  metadata: JSON
}
```

### 3.2 Transcription Pipeline {#transcription-pipeline}

1. **record_audio(filepath, stop_event)**  
2. **transcribe(audio, fast=True)** → quick_transcript  
3. **transcribe(audio, fast=False)** → full_transcript  
4. **apply_lexicon_boost(text, lexicon_terms)**  
5. **user_edit(text)** → corrected_transcript  
6. **score_accuracy(base, reference)** → WER metrics  
7. **persist(Dictation)**

### 3.3 UI Workflow {#ui-workflow}

- **Hotkey** → start recording  
- **Hotkey** → stop recording → auto-launch CorrectionPage  
- **CorrectionPage**: play audio, edit transcript, view WER  
- **Approve & Next** → save & load next  
- **Dashboard**: show aggregated accuracy charts

### 3.4 Lexicon Preparation {#lexicon-preparation}

- **collect_texts(folders, formats)** → raw corpus  
- **compute_user_freq(corpus)**  
- **compute_standard_freq(words)**  
- **identify_special_terms(ratio,min_freq)** → lexicon_terms  
- **export CSV** for review

### 3.5 Configuration {#configuration}

The dictation system supports configurable settings for:
- Audio device selection and recording parameters
- Whisper backend selection and model configuration
- User interface preferences and workflow options
- Data persistence and export settings

### 3.6 Backend Requirements {#backend-requirements}

The transcription system supports multiple backend implementations:
- **StandardOpenAIWhisper**: CPU-based transcription using upstream whisper
- **FasterWhisper**: GPU-accelerated transcription with MPS support
- **WhisperCPP**: Native C++ implementation for performance
- **MLXWhisper**: Apple Silicon optimization
- **OpenAIAPI**: Cloud-based transcription service
- **Mock**: Testing and development backend

All backends must implement a consistent interface for:
- Audio file transcription
- Error handling and recovery
- Performance metrics and logging
- Model loading and caching

### 3.7 Audio Recording {#audio-recording}

The system provides real-time audio recording capabilities:
- **Sample Rate**: 16 kHz mono WAV format
- **Device Selection**: Configurable audio input device
- **Level Monitoring**: Real-time audio level visualization
- **Stream Management**: Persistent or per-session audio streams
- **Error Handling**: Graceful fallback for device failures

### 3.8 Backend Interface {#backend-interface}

All transcription backends must implement the following interface:
```python
class WhisperBackend:
    def __init__(self, model_name: str):
        """Initialize backend with specified model."""
        
    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file and return text."""
        
    @classmethod
    def is_available(cls) -> bool:
        """Check if backend is available on current system."""
```

---

**This document unifies the end-to-end dictation module** — from user needs through detailed specs — ensuring the MVP meets performance, accuracy, and extensibility goals for ZorOS.
