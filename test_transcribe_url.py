"""
Test script to verify transcribe_url mode implementation.
Run this after installing dependencies with: pip install -e .
"""

import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from wvcr.modes import ProcessingMode, ModeFactory
from wvcr.config import OAIConfig
from wvcr.notification_manager import NotificationManager


def test_transcribe_url_mode():
    """Test that transcribe_url mode can be created successfully."""
    try:
        config = OAIConfig()
        notifier = NotificationManager()
        
        # Test that the mode can be created
        mode_handler = ModeFactory.create_mode(
            ProcessingMode.TRANSCRIBE_URL, 
            config, 
            notifier
        )
        
        print("✅ TranscribeUrlMode created successfully")
        print(f"Mode type: {type(mode_handler).__name__}")
        
        # Test available modes
        available_modes = ModeFactory.get_available_modes()
        print(f"Available modes: {[mode.value for mode in available_modes]}")
        
        if ProcessingMode.TRANSCRIBE_URL in available_modes:
            print("✅ TRANSCRIBE_URL mode is available")
        else:
            print("❌ TRANSCRIBE_URL mode is NOT available")
            
    except Exception as e:
        print(f"❌ Error creating TranscribeUrlMode: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("Testing transcribe_url mode implementation...")
    success = test_transcribe_url_mode()
    
    if success:
        print("\n🎉 All tests passed! You can now install dependencies and use the new mode.")
        print("\nTo install dependencies:")
        print("pip install -e .")
        print("\nTo use the new mode:")
        print("python -m wvcr transcribe_url")
        print("python -m wvcr transcribe_url --audio-processing")
    else:
        print("\n❌ Tests failed. Please check the implementation.")
