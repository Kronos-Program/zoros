# Zoros - Personal LLM Operating System

> **⚠️ Alpha Release**: This is an early, experimental iteration of a larger vision. The **dictation system** is stable and production-ready, but other components are under active development.

## The Vision

Why do I have so many apps? Why does nothing work when the internet goes down? How can I find the right tool for the job or the right file?

Zoros is my attempt to scratch that itch — a personal operating system built around Large Language Models that aims to unify the scattered landscape of productivity tools into a coherent, AI-native environment.

### The Problem

- **App Fragmentation**: Dozens of single-purpose apps that don't talk to each other
- **Internet Dependency**: Most tools become useless offline
- **Context Switching**: Constant mental overhead jumping between interfaces
- **Tool Discovery**: Never finding the right tool when you need it
- **Data Silos**: Information trapped in incompatible formats across platforms

### The Solution

Zoros envisions a unified interface where:

- **Voice is the primary input** - natural dictation and conversation
- **AI orchestrates everything** - intelligent routing and tool selection  
- **Offline-first design** - core functionality works without internet
- **Everything is searchable** - unified interface to all your tools and data
- **Extensible by design** - easy to add new capabilities and integrations

## Current State: Dictation Core

**What's Stable Now**: The dictation and transcription system is production-ready and serves as the foundation for everything else.

Inspired by [WhisperWriter](https://github.com/savbell/whisper-writer), but architected as part of a larger system, the current release provides:

### 🎤 High-Performance Dictation

- **Real-time Transcription**: 3-5 second stop-to-text latency
- **Multiple Whisper Backends**: MLX, FasterWhisper, WhisperCPP, OpenAI API
- **Apple Silicon Optimized**: Metal acceleration for M1/M2 Macs
- **Streaming Processing**: Text appears as you speak
- **Audio Recovery**: Never lose a recording, always retranscribeable

### 🔧 Production Features

- **Cross-Platform UI**: Native PySide6 and React interfaces
- **Robust Audio Pipeline**: Automatic device detection and configuration
- **Crash Recovery**: Auto-save drafts and persistent audio storage
- **Performance Monitoring**: Built-in benchmarking and diagnostics
- **Extensible Architecture**: Plugin system ready for future components

## Quick Start

### Installation

```bash
git clone https://github.com/your-org/zoros.git
cd zoros
./scripts/environment/bootstrap_all.sh
source coder-env/bin/activate
```

### Basic Usage

```bash
# Launch dictation interface
zoros intake

# Run system diagnostics  
zoros diagnose

# See all commands
zoros --help
```

### Dictation Workflow

1. **Start Recording**: Click Record in the intake interface
2. **Speak Naturally**: Visual feedback shows audio capture
3. **Real-time Text**: Transcription appears as you speak
4. **Edit & Save**: Refine text and save to dictation library
5. **Never Lose Content**: Audio preserved for retranscription

## Architecture

Zoros is built around a "digital loom" metaphor:

- **Fibers**: Atomic content units (text, audio, external events)
- **Threads**: Ordered sequences forming coherent topics
- **LanguageService**: Central AI processing hub with configurable backends
- **Intake System**: Primary input pipeline for voice and text

## Whisper Backend Configuration

### MLX Whisper (Recommended for M1/M2 Macs)

- **Performance**: ~2 seconds for 5-second audio clips
- **Requirements**: Apple Silicon with Metal acceleration
- **Setup**: Automatically detected on compatible systems

### FasterWhisper

- **Best for**: CUDA systems or when MLX unavailable
- **Features**: CPU/GPU processing with MPS support
- **Setup**: `pip install faster-whisper`

### WhisperCPP

- **Best for**: Offline processing and resource-constrained environments
- **Performance**: CPU-optimized C++ implementation  
- **Setup**: `./scripts/environment/setup_whispercpp.sh`

### OpenAI API

- **Best for**: Cloud processing with highest accuracy
- **Setup**: Set `OPENAI_API_KEY` environment variable

## Development

### Backend (Python/FastAPI)

```bash
./scripts/environment/setup_backend_env.sh
source coder-env/bin/activate
uvicorn backend.app:app --reload
```

### Frontend (React/TypeScript)

```bash
./scripts/environment/setup_frontend_env.sh
cd zoros-frontend
npm run dev
```

### Testing

```bash
# Core functionality
pytest

# Audio system
python scripts/test_audio_devices.py

# Performance benchmarks
python scripts/benchmark_streaming_backends.py
```

## Configuration

### Whisper Settings

Configure in `~/.zoros/intake_settings.json`:

```json
{
  "whisper_backend": "MLXWhisperBackend",
  "streaming_enabled": true,
  "auto_save": true,
  "audio_quality": "high"
}
```

### Language Service

Configure in `source/config/language_service.yml`:

```yaml
router_url: "http://localhost:11434"
default_model: "llama3.2:latest"
timeout: 30
```

## Roadmap

### Next Milestones

- **🔍 Universal Search**: Find anything across all connected systems
- **🤖 AI Orchestration**: Intelligent task routing and tool selection
- **🔌 Tool Integration**: Connect existing apps through unified interface
- **📁 Content Management**: Unified file and data organization
- **🌐 Offline Intelligence**: Local LLM integration for internet-independent operation

### Future Vision

- **Natural Language Interface**: Describe what you want, not how to do it
- **Context Awareness**: AI that remembers and connects your work across time
- **Adaptive Workflows**: System learns and optimizes your personal patterns
- **Collaborative Intelligence**: Seamless human-AI collaboration on complex tasks

## System Requirements

### Minimum (Dictation Only)

- Python 3.11+
- 4GB RAM
- Microphone input

### Recommended (Full Vision)

- Apple Silicon M1/M2 Mac (Metal acceleration)
- 16GB+ RAM (for local LLMs)
- High-quality USB microphone
- SSD storage for fast file operations

## Troubleshooting

### Audio Issues

**Not recording?**

- Check microphone permissions in System Preferences
- Test with: `python scripts/test_audio_devices.py`
- Try different backend in settings

**Slow transcription?**

- Use MLX backend on Apple Silicon
- Enable streaming mode
- Check available system memory

### Recovery

**Lost transcription?**

```bash
# Check recent dictations
sqlite3 zoros_intake.db "SELECT id, timestamp, content FROM intake ORDER BY timestamp DESC LIMIT 5;"

# Retranscribe audio
python scripts/retranscribe_audio.py path/to/audio.wav
```

## Contributing

This is a personal research project, but I welcome:

- **Bug reports** for the dictation system
- **Performance optimizations** for transcription backends  
- **Documentation improvements** and usage examples
- **Architecture discussions** for the broader vision

## Philosophy

Zoros represents a different approach to personal computing:

- **AI-Native**: Designed for the LLM era, not retrofitted
- **Privacy-First**: Your data stays on your machine by default
- **Offline-Capable**: Core functionality works without internet
- **Extensible**: Easy to adapt and expand for personal needs
- **Voice-Centric**: Natural language as the primary interface

The goal isn't to replace every app, but to create a unified layer that makes all your tools more discoverable, accessible, and intelligent.

---

**Current Status**: The dictation core is ready for daily use. The broader vision is actively under development.

**Feedback Welcome**: Share your thoughts on the vision or report issues with the dictation system.