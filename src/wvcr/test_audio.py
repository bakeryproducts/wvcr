import base64
import os
import argparse
import tempfile
from openai import OpenAI
from dotenv import load_dotenv
import requests

# Add pydub for audio conversion
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    print("Warning: pydub not installed. OGG conversion will not work.")
    print("Install with: pip install pydub")
    print("You'll also need ffmpeg installed on your system.")
    PYDUB_AVAILABLE = False

load_dotenv('.env')

client = OpenAI()

def convert_to_wav(audio_path):
    """Convert audio file to WAV format using pydub"""
    if not PYDUB_AVAILABLE:
        print("Error: pydub is required for audio conversion")
        return None
    
    try:
        # Get file extension (without the dot)
        file_ext = os.path.splitext(audio_path)[1][1:].lower()
        
        if file_ext == "wav":
            # No conversion needed
            return audio_path
            
        # Load audio file
        if file_ext == "ogg":
            audio = AudioSegment.from_ogg(audio_path)
        elif file_ext == "mp3":
            audio = AudioSegment.from_mp3(audio_path)
        else:
            audio = AudioSegment.from_file(audio_path, format=file_ext)
        
        # Create temporary WAV file
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        # Export to WAV format
        audio.export(temp_path, format="wav")
        print(f"Converted {file_ext} to WAV: {temp_path}")
        
        return temp_path
    except Exception as e:
        print(f"Error converting audio: {e}")
        return None

def process_audio_file(file_path):
    """Process audio file and return base64 encoded string"""
    try:
        # Convert to WAV if necessary
        wav_path = convert_to_wav(file_path)
        if not wav_path:
            return None
            
        # Read the WAV file
        with open(wav_path, 'rb') as audio_file:
            audio_data = audio_file.read()
            
        # Clean up temporary file if it's different from the original
        if wav_path != file_path:
            try:
                os.unlink(wav_path)
            except:
                pass
                
        return base64.b64encode(audio_data).decode('utf-8')
    except Exception as e:
        print(f"Error processing audio file: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Test OpenAI audio capabilities')
    parser.add_argument('--input-audio', type=str, help='Path to input audio file')
    parser.add_argument('--voice', type=str, default='echo', help='Voice to use (default: echo)')
    args = parser.parse_args()

    messages = [
        {"role": "system", 
         "content": """Этот человек — мужчина средних лет, с глубоким, бархатистым голосом, который звучит уверенно и спокойно. 
Его речь размеренная, он никогда не торопится, тщательно подбирая слова,
словно взвешивает каждое из них. Темп его речи медленный, но не утомительный — он говорит так, что каждое слово звучит значимо,
а паузы между фразами создают ощущение размышления и глубины.
Интонация мягкая, с легким понижением в конце предложений, что придает его словам оттенок завершенности и авторитетности.
Он редко повышает голос, предпочитая сохранять ровный, почти гипнотический тон, который располагает к доверию.
Однако, если он увлечен темой, в его голосе появляются теплые нотки энтузиазма, а интонация становится чуть более оживленной,
но все равно остается сдержанной.
Его манера говорить напоминает человека, который привык быть услышанным,
но не стремится доминировать в разговоре — он скорее ведет собеседника за собой, чем навязывает свою точку зрения"""
}
]
    # messages = []

    audio_user_content = None
    
    # Default prompt content
    user_content = [{ 
        "type": "text", 
        "text": """" Voiceover this line.
я кстати рядом с офисом Reddit оказывается все это время сидел, но он совсем без вывески, скрываются.
только на гугл картах подписано здание
Однажды решил зайти внутрь, но на входе меня встретил охранник с подозрительным взглядом.
Сказал, что без приглашения внутрь не пускают, и я задумался, что же там такого секретного.
"""
    }]
    
    # If input audio is provided, add it to the message
    if args.input_audio:
        audio_path = args.input_audio
        if not os.path.isabs(audio_path) and not os.path.exists(audio_path):
            # Try looking in the output folder if relative path doesn't exist
            potential_path = os.path.join('output', audio_path)
            if os.path.exists(potential_path):
                audio_path = potential_path
        
        if os.path.exists(audio_path):
            print(f"Processing audio file: {audio_path}")
            encoded_audio = process_audio_file(audio_path)
            if encoded_audio:
                # Always use "wav" format for OpenAI API regardless of input format
                audio_user_content = [
                    {
                        "type": "text",
                        "text": "MUST Copy style and accent from this audio! Try to be as close tonality as you can to make a bond with a user"
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": encoded_audio,
                            "format": "wav"  # Always use WAV format for OpenAI API
                        }
                    }
                ]
        else:
            print(f"Audio file not found: {audio_path}")

    messages.append({"role": "user", "content": user_content})
    if audio_user_content:
        messages.append({"role": "user", "content": audio_user_content})
    
    completion = client.chat.completions.create(
        model="gpt-4o-audio-preview",
        modalities=["text", "audio"],
        audio={"voice": args.voice, "format": "wav"},
        messages=messages
    )

    text = completion.choices[0].message.content
    print(text)

    # Save the output audio
    wav_bytes = base64.b64decode(completion.choices[0].message.audio.data)
    os.makedirs("output", exist_ok=True)
    with open("output/text_gpt_audio.wav", "wb") as f:
        f.write(wav_bytes)

if __name__ == "__main__":
    main()