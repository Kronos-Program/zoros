# ZorOS MVP Strategy: Audio Capture and Transcription Accuracy

## Vision

Establish a robust MVP pipeline for dictation capture that:

* Records audio reliably
* Generates an initial fast transcript
* Reprocesses with an enhanced model for deeper transcription
* Supports user correction and feedback
* Scores and tracks transcription accuracy
* Provides a basis for improving future transcription performance

## Core MVP Workflow

### Step 1: Audio Capture

* Capture audio input immediately into a standard, high-quality format (e.g., WAV, 16kHz mono)
* Store raw audio securely with metadata (timestamp, environment tags if available)

### Step 2: Initial (Fast) Transcription

* Transcribe audio using a **local fast model**:

  * Planning to build off of Whisper-Writer
  * Prioritize low latency and reasonable quality
* Save output as `quick_transcript`

### Step 3: Secondary (Deep) Transcription

* Reprocess audio with a **higher quality model**:

  * Example: Whisper large, boosted beam search
  * Allow for punctuation restoration, better sentence boundaries
* Save output as `full_transcript`

### Step 4: User Correction Phase (Optional)

* Allow user to manually review and correct:

  * Misspelled words
  * Missing sections
  * Misinterpretations
* Save final corrected output as `corrected_transcript`

### Step 5: Accuracy Scoring

* Compare:

  * `quick_transcript` vs `full_transcript`
  * `full_transcript` vs `corrected_transcript`
* Metrics:

  * **Word Error Rate (WER)**
  * **Edit Distance** (Levenshtein)
  * **Transcription Confidence** (optional: use LLM to estimate soft error likelihood)
* Store accuracy results alongside the dictation metadata for trend tracking.

## Implementation Notes

* Use lightweight tools for audio handling (pydub, soundfile)
* Use or adapt local models with token alignment metadata to assess confidence per word (optional)
* Set thresholds for acceptable initial quality vs needs secondary processing

## Future Improvement Methods

| Method                        | Purpose                                                                    |
| ----------------------------- | -------------------------------------------------------------------------- |
| Personal Vocabulary Injection | Boost decoding likelihood for known frequent terms                         |
| Environment-Aware Models      | Adjust model settings depending on noise conditions                        |
| Model Ensembles               | Blend outputs from fast and slow models to produce better fast-pass drafts |
| Prompted LLM Review           | Post-process transcripts to improve grammar and clarity automatically      |

## Summary Flow

```
Audio Capture → Fast Transcript → Deep Transcript → Correction → Accuracy Scoring → Improvement Feedback
```

---

**Summary**: This MVP strategy for audio and transcription accuracy gives ZorOS a structured way to measure, improve, and evolve its dictation capabilities, ensuring that spontaneous thought capture is reliable, adaptable, and ever-improving.
