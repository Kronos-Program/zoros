# See architecture: docs/zoros_architecture.md#component-overview
import io
import os
import numpy as np
import soundfile as sf
import whisper
from openai import OpenAI
import tempfile
import subprocess

from utils import ConfigManager

def create_local_model():
    """
    Create a local model using the OpenAI Whisper library.
    """
    ConfigManager.console_print('Creating local model...')
    local_model_options = ConfigManager.get_config_section('model_options')['local']
    model_path = local_model_options.get('model_path')
    device = local_model_options['device']

    # Auto-select device if requested or validate requested device
    try:
        import torch
        if device == 'auto':
            if torch.backends.mps.is_available():
                device = 'mps'
            elif torch.cuda.is_available():
                device = 'cuda'
            else:
                device = 'cpu'
        elif device == 'mps' and not torch.backends.mps.is_available():
            ConfigManager.console_print('MPS requested but not available. Falling back to CPU.')
            device = 'cpu'
        elif device == 'cuda' and not torch.cuda.is_available():
            ConfigManager.console_print('CUDA requested but not available. Falling back to CPU.')
            device = 'cpu'
    except Exception:
        if device == 'auto':
            device = 'cpu'

    try:
        if model_path:
            ConfigManager.console_print(f'Loading model from: {model_path}')
            model = whisper.load_model(model_path, device=device)
        else:
            model = whisper.load_model(local_model_options['model'], device=device)
    except Exception as e:
        ConfigManager.console_print(f'Error initializing Whisper model: {e}')
        ConfigManager.console_print('Falling back to CPU.')
        model = whisper.load_model(model_path or local_model_options['model'], device='cpu')

    ConfigManager.console_print('Local model created.')
    return model

def transcribe_local(audio_data, local_model=None):
    """
    Transcribe an audio file using a local model.
    """
    if not local_model:
        local_model = create_local_model()
    model_options = ConfigManager.get_config_section('model_options')

    # Convert int16 to float32
    audio_data_float = audio_data.astype(np.float32) / 32768.0

    result = local_model.transcribe(audio_data_float,
                                    language=model_options['common']['language'],
                                    initial_prompt=model_options['common']['initial_prompt'],
                                    condition_on_previous_text=model_options['local']['condition_on_previous_text'],
                                    temperature=model_options['common']['temperature'])
    return result.get('text', '')

def transcribe_api(audio_data):
    """
    Transcribe an audio file using the OpenAI API.
    """
    model_options = ConfigManager.get_config_section('model_options')
    client = OpenAI(
        api_key=os.getenv('OPENAI_API_KEY') or None,
        base_url=model_options['api']['base_url'] or 'https://api.openai.com/v1'
    )

    # Convert numpy array to WAV file
    byte_io = io.BytesIO()
    sample_rate = ConfigManager.get_config_section('recording_options').get('sample_rate') or 16000
    sf.write(byte_io, audio_data, sample_rate, format='wav')
    byte_io.seek(0)

    response = client.audio.transcriptions.create(
        model=model_options['api']['model'],
        file=('audio.wav', byte_io, 'audio/wav'),
        language=model_options['common']['language'],
        prompt=model_options['common']['initial_prompt'],
        temperature=model_options['common']['temperature'],
    )
    return response.text

def transcribe_whisper_cpp(audio_data):
    """Transcribe audio using the whisper.cpp command-line tool."""
    ConfigManager.console_print('Using whisper.cpp backend...')
    sample_rate = ConfigManager.get_config_section('recording_options').get('sample_rate') or 16000
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        sf.write(tmp.name, audio_data, sample_rate, format='wav')
    model_name = ConfigManager.get_config_section('model_options')['local']['model']
    model_path = os.path.expanduser(f"~/.local/share/whisper-cpp/{model_name}.bin")
    binary = os.environ.get('WHISPER_CPP_BINARY', 'whisper-cli')
    cmd = [binary, tmp.name, '--model', model_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        transcription = result.stdout.strip().splitlines()[-1]
    except Exception as e:
        ConfigManager.console_print(f'Error running whisper.cpp: {e}')
        transcription = ''
    finally:
        os.remove(tmp.name)
    return transcription

def transcribe_easy_whisper_ui(audio_data):
    """Placeholder for EasyWhisperUI backend."""
    ConfigManager.console_print('EasyWhisperUI backend not implemented yet.')
    return ''

def post_process_transcription(transcription):
    """
    Apply post-processing to the transcription.
    """
    transcription = transcription.strip()
    post_processing = ConfigManager.get_config_section('post_processing')
    if post_processing['remove_trailing_period'] and transcription.endswith('.'):
        transcription = transcription[:-1]
    if post_processing['add_trailing_space']:
        transcription += ' '
    if post_processing['remove_capitalization']:
        transcription = transcription.lower()

    return transcription

def transcribe(audio_data, local_model=None):
    """
    Transcribe audio date using the OpenAI API or a local model, depending on config.
    """
    if audio_data is None:
        return ''

    backend = ConfigManager.get_config_value('model_options', 'backend')
    if backend == 'openai_api' or ConfigManager.get_config_value('model_options', 'use_api'):
        transcription = transcribe_api(audio_data)
    elif backend == 'whisper_cpp':
        transcription = transcribe_whisper_cpp(audio_data)
    elif backend == 'easy_whisper_ui':
        transcription = transcribe_easy_whisper_ui(audio_data)
    else:
        transcription = transcribe_local(audio_data, local_model)

    return post_process_transcription(transcription)

