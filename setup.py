from setuptools import setup, find_packages

setup(
    name="zoros",
    version="0.1.0",
    packages=find_packages(include=["source", "source.*", "backend", "zoros"]),
    install_requires=[
        "typer>=0.9.0",
        "sounddevice>=0.4.6",
        "soundfile>=0.12.1",
        "PySide6>=6.7.0",
        "streamlit>=1.33.0",
        "fastapi>=0.110.0",
        "uvicorn>=0.29.0",
        "pydantic>=2.6.3",
        "fuzzywuzzy>=0.18.0",
        "python-Levenshtein>=0.23.0",
        "openai-whisper",
        "faster-whisper>=1.0.2",
        "requests>=2.31.0",
        "pytest>=8.3.4",
        "python-dotenv>=1.0.0",
        "numpy>=1.24.3",
        "pynput>=1.7.6",
        "pyperclip>=1.8.2",
        "keyring>=24.3.1",
        "aiohttp>=3.8.4",
        "PyYAML>=6.0.1",
        "tqdm>=4.65.0",
        "colorama>=0.4.6",
        "coloredlogs>=15.0.1"
    ],
    entry_points={
        'console_scripts': [
            'zoros=zoros.cli:run',
        ],
    },
)
