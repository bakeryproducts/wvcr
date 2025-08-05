"""Сервис для работы с файлами."""

from pathlib import Path
from datetime import datetime
from wvcr.config import OUTPUT


def create_output_file_path(mode: str, extension: str = "txt") -> Path:
    """Создать путь для выходного файла на основе режима и времени."""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
    output_dir = OUTPUT / mode.lower()
    output_dir.mkdir(exist_ok=True, parents=True)
    return output_dir / f"{timestamp}.{extension}"


def save_text_to_file(text: str, file_path: Path) -> None:
    """Сохранить текст в файл."""
    file_path.parent.mkdir(exist_ok=True, parents=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)


def create_audio_file_path(mode: str, extension: str = "mp3") -> Path:
    """Создать путь для аудио файла."""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
    if mode.lower() == "voiceover":
        output_dir = OUTPUT / "voiceover"
        extension = "wav"
    else:
        output_dir = OUTPUT / "records"
    
    output_dir.mkdir(exist_ok=True, parents=True)
    return output_dir / f"{timestamp}.{extension}"
