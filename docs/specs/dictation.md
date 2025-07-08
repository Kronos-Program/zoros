# Dictation & Intake UI Workflow

The Intake UI provides a simple way to capture voice notes and convert them into Fibers.

1. **Record** – Use the Record button or the `Ctrl+Shift+D` hotkey to start/stop capture. While recording, a waveform animates in real time.
2. **Lexicon Corrections** – After a quick pass through Whisper, highlighted tokens can be reverted by clicking.
3. **Submit** – Once satisfied, click Submit. The backend performs a deep transcription and saves a Fiber to the database via `/api/dictate/full`.
4. **Partial** – Stopping a recording sends the audio to `/api/dictate/partial` for a quick draft transcript.
5. **Copy** – Use the Copy button or enable Auto Copy in settings to place the transcript on your clipboard.

## Settings

Open the gear icon to configure audio device, persistent stream, and Whisper backend. Settings are saved to `~/.zoros/intake_settings.json`.

Available backends now include **OpenAIAPI**, **StandardOpenAIWhisper**, **FasterWhisper**, and **WhisperCPP**. Use the **Test** button in the settings dialog to verify that the selected backend initializes correctly.

Both `/api/dictate/partial` and `/api/dictate/full` accept raw WAV data. The full endpoint also returns a `fiber_id` for the created entry.

### Confidence Overlay

Starting with version 1.1 of the Intake UI, a yellow overlay appears on the waveform. Its opacity reflects the transcription confidence returned by Whisper.
