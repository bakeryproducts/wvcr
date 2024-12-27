# WVCR - Voice Recording & Transcription Tool

A simple command-line tool for voice recording and transcription using OpenAI's Whisper API.

## Features

- One-click voice recording
- Automatic transcription using OpenAI's Whisper
- Automatic clipboard copy of transcription
- GPT-4 powered QA mode
- Smart grammar correction mode
- Text-to-Speech voiceover mode
- Desktop notifications
- Configurable recording settings

## Installation

1. Clone the repository:
```bash
git clone https://github.com/bakeryproducts/wvcr.git
cd wvcr
pip install .
```

2. Set up your OpenAI API key:
```bash
export OPENAI_API_KEY='your-api-key-here'
```

3. Install system dependencies:
```bash
# Ubuntu/Debian
sudo apt-get install python3-pyaudio
```