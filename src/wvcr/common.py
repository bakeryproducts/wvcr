from pynput import keyboard
from loguru import logger
import os
import threading
import time
import select
from abc import ABC, abstractmethod

# Check for optional dependencies
EVDEV_AVAILABLE = False
try:
    import evdev
    from evdev import ecodes, categorize
    EVDEV_AVAILABLE = True
except ImportError:
    logger.debug("evdev package not installed. Install with: pip install evdev")


class KeyboardMonitor(ABC):
    """Abstract base class for keyboard monitoring implementations."""
    
    @abstractmethod
    def start(self):
        """Start monitoring for key presses."""
        pass
    
    @abstractmethod
    def stop(self):
        """Stop monitoring for key presses."""
        pass

class PynputKeyMonitor(KeyboardMonitor):
    """Keyboard monitor implementation using pynput."""
    
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

class EvdevKeyMonitor(KeyboardMonitor):
    """Keyboard monitor implementation using evdev for Wayland compatibility."""
    
    def __init__(self, stop_key, callback):
        self.stop_key = stop_key
        self.callback = callback
        self.running = False
        self.thread = None
        
        if not EVDEV_AVAILABLE:
            logger.warning("evdev package not installed. Install with: pip install evdev")
        
    def _is_real_keyboard(self, device):
        """
        Check if the device is a real keyboard by examining its capabilities.
        A real keyboard should have a substantial number of KEY events.
        """
        try:
            if ecodes.EV_KEY not in device.capabilities():
                return False
            
            # Check if it has a substantial number of key capabilities
            # Real keyboards typically have at least 30+ keys
            key_caps = device.capabilities().get(ecodes.EV_KEY, [])
            if len(key_caps) < 30:
                # logger.debug(f"Ignoring device '{device.name}' with only {len(key_caps)} keys")
                return False
                
            # Check for typical keyboard keys like letters
            required_keys = [ecodes.KEY_A, ecodes.KEY_SPACE, ecodes.KEY_ENTER]
            for key in required_keys:
                if key not in key_caps:
                    # logger.debug(f"Device '{device.name}' missing essential key, likely not a keyboard")
                    return False
                    
            return True
        except Exception as e:
            logger.error(f"Error checking keyboard device: {e}")
            return False
        
    def _monitor_thread(self):
        if not EVDEV_AVAILABLE:
            logger.error("evdev package not installed. Install with: pip install evdev")
            return
            
        try:
            # Find keyboard devices
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
            keyboard_devices = []
            
            for device in devices:
                # logger.debug(f"Device: {device.name}, caps: {device.capabilities()}")
                if self._is_real_keyboard(device):
                    logger.info(f"Found keyboard device: {device.name}")
                    keyboard_devices.append(device)
            
            if not keyboard_devices:
                logger.error("No keyboard devices found")
                return
            
            # Map pynput key to evdev keycode
            key_map = {
                keyboard.Key.esc: ecodes.KEY_ESC,
                # keyboard.Key.space: ecodes.KEY_SPACE,
                # Add more mappings as needed
            }
            
            target_keycode = key_map.get(self.stop_key)
            if target_keycode is None:
                logger.error(f"Unsupported stop key: {self.stop_key}")
                return
                
            self.running = True
            
            # Monitor devices for key events
            devices = {dev.fd: dev for dev in keyboard_devices}
            
            while self.running:
                r, w, x = select.select(devices, [], [], 0.1)
                for fd in r:
                    for event in devices[fd].read():
                        if event.type == ecodes.EV_KEY and event.value == 1:  # Key down
                            if event.code == target_keycode:
                                logger.info(f"Stop key pressed (evdev), stopping")
                                self.running = False
                                self.callback()
                                break
        
        except Exception as e:
            logger.exception(f"Error in evdev monitoring: {e}")
        finally:
            self.running = False
    
    def start(self):
        if not EVDEV_AVAILABLE:
            logger.error("Cannot start evdev monitor: evdev package not installed")
            return
            
        self.thread = threading.Thread(target=self._monitor_thread)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)


def create_key_monitor(stop_key, callback, prefer_evdev=False):
    """
    Factory function to create an appropriate keyboard monitor.
    
    Args:
        stop_key: Key to monitor for stopping
        callback: Function to call when stop key is pressed
        prefer_evdev: If True, tries to use evdev first
        
    Returns:
        A KeyboardMonitor implementation
    """
    # Check environment variable for preference
    env_preference = os.environ.get("WVCR_USE_EVDEV", "").lower()
    if env_preference in ("1", "true", "yes"):
        prefer_evdev = True
        
    if prefer_evdev and EVDEV_AVAILABLE:
        logger.info("Using evdev keyboard monitor")
        return EvdevKeyMonitor(stop_key, callback)
    
    logger.info("Using pynput keyboard monitor")
    return PynputKeyMonitor(stop_key, callback)