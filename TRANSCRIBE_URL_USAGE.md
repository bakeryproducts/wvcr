# Usage Examples for transcribe_url Mode

## Prerequisites

1. Install ffmpeg on your system:
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg
   
   # macOS
   brew install ffmpeg
   
   # Windows
   # Download from https://ffmpeg.org/download.html
   ```

2. Install Python dependencies:
   ```bash
   pip install -e .
   ```

## Usage

### Basic Usage

1. Copy a URL to your clipboard (YouTube video, direct audio/video file)
2. Run the command:
   ```bash
   python -m wvcr transcribe_url
   ```

### With Audio Processing

For better transcription quality, you can enable audio processing (normalization and noise reduction):
```bash
python -m wvcr transcribe_url --audio-processing
```

## Supported URL Types

### YouTube Videos
- https://www.youtube.com/watch?v=VIDEO_ID
- https://youtu.be/VIDEO_ID
- https://www.youtube.com/embed/VIDEO_ID
- https://www.youtube.com/shorts/VIDEO_ID

### Direct File URLs
- https://example.com/audio.mp3
- https://example.com/video.mp4
- https://example.com/audio.wav
- https://example.com/video.mkv

## Workflow

1. **URL Detection**: Reads URL from clipboard
2. **Download**: Downloads audio/video file using yt-dlp or direct download
3. **Audio Extraction**: Extracts audio track from video files using ffmpeg
4. **Audio Processing** (optional): Applies noise reduction and normalization
5. **Transcription**: Uses OpenAI's Whisper API for transcription
6. **Output**: Saves transcription to file and copies to clipboard
7. **Cleanup**: Removes temporary files

## Output

- Transcription is saved to `output/transcribe/YYYY-MM-DD_HH:MM:SS.txt`
- Transcription is copied to clipboard
- Desktop notification shows preview of transcription

## Error Handling

The mode handles various error scenarios:
- Invalid URLs
- Download failures
- Unsupported formats
- Network issues
- ffmpeg processing errors

## Examples

### Transcribe a YouTube tutorial:
1. Copy: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
2. Run: `python -m wvcr transcribe_url`

### Transcribe a podcast episode:
1. Copy: `https://example.com/podcast-episode.mp3`
2. Run: `python -m wvcr transcribe_url --audio-processing`

### Transcribe a video lecture:
1. Copy: `https://example.com/lecture.mp4`
2. Run: `python -m wvcr transcribe_url`
