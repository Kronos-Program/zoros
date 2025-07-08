# Environment Setup

This repository provides scripts to bootstrap both the Python Codex
backend and the React frontend.

## Prerequisites

- Python 3.11
- Node.js 16 or newer
- System packages: `portaudio19-dev`, `libasound2-dev`, `libegl1`, `libgl1-mesa-dev`

## Steps

1. Clone the repository.
2. Install the backend and frontend environments separately:

   ```bash
   chmod +x scripts/setup_backend_env.sh
   chmod +x scripts/setup_frontend_env.sh
   # Install system libs required by audio and Qt components
   sudo apt-get update -y
   sudo apt-get install -y portaudio19-dev libasound2-dev libegl1 libgl1-mesa-dev
   scripts/setup_backend_env.sh
   scripts/setup_frontend_env.sh
   ```

   The `scripts/bootstrap_all.sh` helper simply runs these two scripts in
   sequence if you prefer a one-line setup.

3. Launch the backend:

   ```bash
   source coder-env/bin/activate
   uvicorn backend.app:app --reload
   ```

4. Launch the frontend:

   ```bash
   cd zoros-frontend
   npm run start
   ```

Navigate to `http://localhost:8000/status` for backend health
and `http://localhost:3000/` for the React UI.

## Troubleshooting

If the setup script fails with an error similar to:

```
ModuleNotFoundError: No module named 'pydantic.fields'
```

check that no local files shadow the real **pydantic** package.
Older revisions included a `pydantic.py` stub which must be removed
or renamed before running `scripts/setup_coder_env.sh`.

## WhisperCPP Setup

To use the offline transcription backend, build `whisper.cpp` and install the
Python wrapper. See [docs/whispercpp_setup.md](docs/whispercpp_setup.md) for
full details. A helper script is provided:

```bash
chmod +x scripts/setup_whispercpp.sh
scripts/setup_whispercpp.sh
```

If you have an existing `whisper.cpp` build, set the `WHISPER_CPP_DIR` environment variable to skip cloning and building:

```bash
export WHISPER_CPP_DIR=/path/to/whisper.cpp
scripts/setup_whispercpp.sh
```

Verify the installation:

```bash
python scripts/test_whispercpp.py
```

The test prints `WhisperCPP OK` when the module loads successfully.
