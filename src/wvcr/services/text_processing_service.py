import re
from pathlib import Path
from PIL import Image
from io import BytesIO
import base64

from loguru import logger

from wvcr.config import OUTPUT
from wvcr.config import OAIConfig, GeminiConfig
from wvcr.messages import Messages, get_prev_files, load_previous_responses


def answer_question(transcript: str, config: OAIConfig) -> str:
    logger.info(f"Answering question: {transcript}")

    messages = Messages()
    try:
        messages.clear_history()
        messages.add_message(
            "system", 
            "You are a helpful assistant. Please answer to the following question. "
            "Be concise and informative. Do not use full sentences. "
            "Your answer should start with most relevant information. Add more IF NECESSARY after."
        )

        # Загружаем историю
        answer_dir = OUTPUT / "answer"
        transcribe_dir = OUTPUT / "transcribe"
        
        prev_answers_files = get_prev_files(answer_dir)
        prev_answers = load_previous_responses(prev_answers_files, limit=5)
        
        prev_transcripts_files = get_prev_files(transcribe_dir, prev_answers_files)
        prev_transcripts = load_previous_responses(prev_transcripts_files, limit=5)

        if len(prev_answers) != len(prev_transcripts):
            logger.warning("Previous answers and transcripts do not match")
        else:
            for answer, transcript in zip(prev_answers, prev_transcripts):
                messages.add_message("user", transcript)
                messages.add_message("assistant", answer)
                
        messages.add_message("user", transcript)
        messages._print()
        
        response = config.client.chat.completions.create(
            model=config.GPT_MODEL,
            temperature=config.temperature,
            messages=messages.get_messages()
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.exception(f"Could not process question: {str(e)}")
        return transcript


def explain(transcript: str, config: OAIConfig | GeminiConfig, thing) -> str:
    logger.info(f"Explaining with context: {transcript}")
    messages = Messages()
    messages.clear_history()

    messages.add_message(
        "system",
        "You are a assistant. Please use the following context and proceed to user's question. "
        "Be concise and brief."
    )
    if transcript:
        messages.add_message("user", transcript)

    if thing and isinstance(thing, str):
        # Only treat as file path if it's reasonably short and doesn't contain newlines
        # (actual file paths won't have newlines or be extremely long)
        if len(thing) < 4096 and '\n' not in thing:
            p = Path(thing)
            try:
                if p.exists() and p.is_file():
                    suffix = p.suffix.lower()
                    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                        data = p.read_bytes()
                        messages.add_image(data)
                    else:
                        text = p.read_text(encoding="utf-8", errors="ignore")
                        if text.strip():
                            messages.add_message("user", text.strip())
                else:
                    # Path string but file doesn't exist - use as literal text
                    messages.add_message("user", thing)
            except Exception as e:
                # Path check failed or file read failed - use as literal text
                logger.debug(f"Thing not a valid file path: {e}; using as literal string")
                messages.add_message("user", thing)
        else:
            # Too long or contains newlines - treat as literal text content
            messages.add_message("user", thing)
    elif isinstance(thing, Image.Image):
        messages.add_image(thing)


    messages._print()

    if isinstance(config, OAIConfig):
        return explain_oai(messages, config)
    elif isinstance(config, GeminiConfig):
        return explain_gemini(messages, config)
    return ""


def explain_oai(messages, config: OAIConfig) -> str:
    client = config.get_client()

    try:
        response = client.chat.completions.create(
            model=config.EXPLAIN_MODEL,
            # temperature=config.temperature,
            reasoning_effort='minimal',
            messages=messages.to_oai()  # changed: include image parts in proper format
        )
        logger.debug(f"Response usage: {response.usage}")
        return response.choices[0].message.content
    except Exception as e:
        logger.exception(f"Could not process explanation: {str(e)}")
        return ""


def explain_gemini(messages, config: GeminiConfig) -> str:
    from google.genai import types

    client = config.get_client()

    try:
        # Convert messages to Gemini format
        parts = []
        
        for msg in messages.history:
            if "content" in msg:
                # Add text content with role prefix for context
                role = msg["role"]
                content = msg["content"]
                if role == "system":
                    parts.append(f"Instructions: {content}")
                elif role == "user":
                    parts.append(f"User: {content}")
                elif role == "assistant":
                    parts.append(f"Assistant: {content}")
            elif "image" in msg:
                # Convert PIL Image to bytes
                img: Image.Image = msg["image"]
                buf = BytesIO()
                img.save(buf, format="PNG")
                img_bytes = buf.getvalue()
                parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
        
        logger.debug(f"Sending {len(parts)} parts to Gemini for explanation")
        
        response = client.models.generate_content(
            model=config.EXPLAIN_MODEL,
            config=types.GenerateContentConfig(
                temperature=config.temperature,
                thinking_config=types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel.LOW,
                )
            ),
            contents=parts,
        )
        
        logger.debug(f"Gemini explanation response: {response}")
        text = getattr(response, "text", None)
        if text:
            logger.debug(f"Gemini explanation received {len(text)} chars")
            return text.strip()
        return ""
    except Exception as e:
        logger.exception(f"Could not process explanation with Gemini: {str(e)}")
        return ""


def detect_mode_from_text(transcript: str) -> str:
    lower_transcript = transcript.lower()
    lower_transcript = re.sub(r'[^\w\s]', '', lower_transcript)
    
    answer_keywords = ["режим вопрос"]
    explain_keywords = ["режим объяснение"]
    
    if any(keyword in lower_transcript for keyword in answer_keywords):
        return "answer"
    elif any(keyword in lower_transcript for keyword in explain_keywords):
        return "explain"

    return "transcribe"