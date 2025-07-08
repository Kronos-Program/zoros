# See architecture: docs/zoros_architecture.md#component-overview
import os
import sys
import numpy as np
import soundfile as sf
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from transcription import transcribe_api, transcribe_whisper_cpp
from utils import ConfigManager

st.title("Whisper Transcription Demo")

uploaded_file = st.file_uploader("Upload WAV file", type=["wav"])
backend = st.selectbox("Backend", ["openai_api", "whisper_cpp"])

if uploaded_file and st.button("Transcribe"):
    audio_data, sample_rate = sf.read(uploaded_file, dtype="int16")
    ConfigManager.initialize()
    if backend == "openai_api":
        result = transcribe_api(audio_data)
    else:
        result = transcribe_whisper_cpp(audio_data)
    st.write(result)
