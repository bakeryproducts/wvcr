from pynput import keyboard
from loguru import logger

class KeyMonitor:
    def __init__(self, stop_key, callback):
        self.stop_key = stop_key
        self.callback = callback
        self.listener = None

    def _on_key_press(self, key):
        if key == self.stop_key:
            logger.info(f"Key {self.stop_key} pressed, stopping")
            self.callback()
            self.listener.stop()

    def start(self):
        self.listener = keyboard.Listener(on_press=self._on_key_press)
        self.listener.start()

    def stop(self):
        if self.listener:
            self.listener.stop()