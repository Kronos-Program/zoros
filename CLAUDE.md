# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Application Overview

**Zoros** (Zero-Obstruction Routine Orchestration System) is a dictation and transcription platform built around processing content through **Fibers** (atomic units) and **Threads** (sequences), with an integrated **LanguageService** for content processing.

## Core Architecture

### Weaving Metaphor Foundation
- **Fibers**: Atomic content units (text, audio, tasks, external events)
- **Threads**: Ordered sequences of Fibers forming coherent topics (the "warp")
- **Routines**: Multi-stage workflows that "weft" new Fibers into Threads via Turns
- **Fiberizers**: Content processors that operate at multiple "fold levels" (Ultra → Gist → Source → Expanded)

### Key System Components

**Language Processing Hub**: `LanguageService` (`source/language_service.py`) routes all LLM operations through LMOS Router with configurable backends (OpenAI, local models).

**Dictation Pipeline**: Multiple Whisper backends optimized for Apple Silicon M1/M2:
- `MLXWhisperBackend` - Metal-accelerated for M1/M2 Macs
- `QueueBasedStreamingBackend` - Production-ready streaming (fastest)
- `FasterWhisperBackend` - MPS acceleration
- `WhisperCPPBackend` - Offline processing
- `OpenAIAPIBackend` - Cloud processing

**Fiberization Framework**: Hierarchical content processing at multiple abstraction levels with configurable prompts and metadata tracking.

## Directory Structure

```
source/
├── core/models/          # Domain models (Fiber, Thread, FibrizerOptions)
├── orchestration/        # Workflow orchestration (RoutineRunner, TurnRegistry, Fiberizers)
├── interfaces/          # UI components (React, PySide6, Streamlit)
├── dictation_backends/  # Audio transcription services
└── services/           # External integrations

backend/                # FastAPI REST service
zoros-frontend/         # React TypeScript application
scripts/               # Development and automation tools
tests/                # Comprehensive test suite (83+ passing tests)
```

## Development Commands

### Environment Setup
```bash
# Complete bootstrap
./scripts/environment/bootstrap_all.sh

# Individual environments
./scripts/environment/setup_backend_env.sh    # Python/FastAPI
./scripts/environment/setup_frontend_env.sh   # Node.js/React
```

### CLI Entry Points (via `zoros` command)
```bash
zoros intake          # PySide6 intake UI with real-time audio
zoros unified         # PySide6 with embedded React
zoros streamlit       # Streamlit fiber processing tools
zoros fiberize-pdf    # Convert PDF to structured DocFibers
zoros lint-fiber      # Validate/fix fiber markdown
zoros diagnose        # System health check
zoros menu           # Interactive command selection
```

### Development Servers
```bash
# Backend (FastAPI on port 8000)
source coder-env/bin/activate
uvicorn backend.app:app --reload

# Frontend (React/Vite on port 3000)
cd zoros-frontend
npm run dev

# Alternative interfaces
python -m source.interfaces.intake.main  # Native PySide6 intake
streamlit run source/interfaces/streamlit/fiberizer_review.py
```

### Testing
```bash
# Full test suite
pytest

# Frontend tests
npm run test:ui

# Specific categories
pytest tests/core/          # Core models
pytest tests/orchestration/ # Fiberizers and workflows
pytest tests/test_intake.py # Intake pipeline
```

## Key Technical Details

### Dictation Performance Optimization
The system is optimized for **3-5 second stop-to-text latency**:
- **QueueBasedStreamingMLXWhisper** is the fastest production backend (~2s for 5s audio)
- **Streaming Architecture** processes chunks in real-time for immediate feedback
- **Model Caching** eliminates reload overhead for subsequent transcriptions
- **M1/M2 Optimization** leverages Metal acceleration and Neural Engine

### Configuration Management
- **Language Service**: `source/config/language_service.yml`
- **Whisper Settings**: `~/.zoros/intake_settings.json`
- **Theme System**: `assets/theme_tokens.json` for unified dark mode
- **Plugin Manifests**: Extensible plugin architecture

### Data Flow
```
Audio/Text Input → Whisper Transcription → Fiber Creation → 
Fiberization (Multi-level) → Thread Assignment → Database Storage
```

### API Integration
- **REST API**: 40+ endpoints in `backend/app.py`
- **Database**: SQLite for MVP, with PostgreSQL planned
- **File Storage**: Audio files in `audio/intake/`, configurations in `~/.zoros/`

## Development Best Practices

### Code Organization
- **Domain-Driven Design**: Core models separate from infrastructure
- **Layered Architecture**: Interface → Orchestration → Core → Persistence
- **Type Safety**: Comprehensive TypeScript/Python typing with Pydantic models

### Testing Strategy
- **Unit Tests**: Core business logic and models
- **Integration Tests**: API endpoints and complete workflows
- **UI Tests**: Playwright for React components
- **Performance Tests**: Transcription benchmarks and pipeline timing

### Environment Dependencies
- **Python 3.11+** with ML/AI stack (torch, transformers, mlx-whisper)
- **Node.js 16+** for React frontend
- **System Libraries**: Audio processing (portaudio), Qt WebEngine for unified UI
- **Optional**: WhisperCPP for offline transcription

## Common Tasks

### Adding New Fiberizers
1. Extend `BaseFiberizer` in `source/orchestration/fibrizers/`
2. Implement `fiberize_content()` method with appropriate prompts
3. Register in `TurnRegistry` for workflow integration
4. Add tests in `tests/orchestration/`

### Extending Dictation Backends
1. Implement backend interface in `source/dictation_backends/`
2. Add backend detection to `utils.py`
3. Update settings UI in `source/interfaces/intake/`
4. Add performance benchmarks

### Frontend Component Development
1. Components in `zoros-frontend/src/components/`
2. Use theme tokens from `assets/theme_tokens.json`
3. TypeScript interfaces for API communication
4. Responsive design with CSS modules

### API Endpoint Development
1. Add routes to `backend/app.py`
2. Use Pydantic models for request/response validation
3. Implement proper error handling with global handler
4. Add integration tests in `tests/`

## Packaging & Deployment

### Executable Building
```bash
python scripts/build_executable.py
```
Creates standalone executable with embedded dependencies and plugin system.

### Plugin Development
Plugin structure:
```
plugin_name/
├── plugin_manifest.yaml  # Plugin metadata and dependencies
├── plugin_name/         # Python package
└── pyproject.toml       # Build configuration
```

This architecture supports both development flexibility and production deployment with comprehensive tooling for all aspects of the personal productivity platform.

## Agent Documentation

For detailed agent interaction logs, solutions, and development history, see [AGENTS.md](AGENTS.md). When completing significant tasks or troubleshooting issues, document the process in `.agents/log/` using the format `chat-{number}-{brief-description}.md`.

### Task Documentation Guidelines

- **Document all significant tasks**: Environment fixes, feature implementations, bug resolutions, etc.
- **Use descriptive filenames**: `chat-{number}-{brief-description}.md`
- **Include**: Problem description, root cause analysis, solution implementation, files modified, verification steps
- **Reference in AGENTS.md**: Add entries to the appropriate sections for discoverability
- **Task File Generation**: Task files, located in `docs/tasks`, should be generated with the user's initial prompting verbatim, and then any interpolations and extrapolations that the agent sees fit.