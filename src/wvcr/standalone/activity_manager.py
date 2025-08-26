import threading
from typing import Optional
from loguru import logger

from config import StreamingMode, StreamingConfig


class ActivityManager:
    """Manages activity signals for different streaming modes."""
    
    def __init__(self, streaming_config: StreamingConfig):
        self.config = streaming_config
        self._chunk_count = 0
        self._lock = threading.Lock()
        # Track current activity state to avoid duplicate start/end signals
        self._is_active = False

    def _start(self, live_request_queue) -> None:
        logger.debug("Sending initial activity start")
        live_request_queue.send_activity_start()

    def _end(self, live_request_queue) -> None:
        logger.debug("Sending initial activity end")
        live_request_queue.send_activity_end()

    def maybe_send_activity_start(self, live_request_queue) -> bool:
        if self.config.mode != StreamingMode.SIMULTANEOUS:
            return False
        with self._lock:
            if self._is_active:
                return False
            self._start(live_request_queue)
            self._is_active = True
            return True

    def maybe_send_activity_end(self, live_request_queue) -> bool:
        if self.config.mode != StreamingMode.SIMULTANEOUS:
            return False
        with self._lock:
            if not self._is_active:
                return False
            self._end(live_request_queue)
            self._is_active = False
            return True

    def on_first_audio(self, live_request_queue) -> None:
        self.maybe_send_activity_start(live_request_queue)

    def on_silence_timeout(self, live_request_queue) -> None:
        ended = self.maybe_send_activity_end(live_request_queue)
        if ended:
            self.reset()
        
    def should_manage_activity_restart(self) -> bool:
        return self.config.mode == StreamingMode.SIMULTANEOUS
        
    def on_chunk_processed(self, live_request_queue) -> None:
        if not self.should_manage_activity_restart():
            return
            
        with self._lock:
            self._chunk_count += 1
            if self._chunk_count >= self.config.simultaneous_config.activity_restart_interval:
                logger.debug(f"Restarting activity after {self._chunk_count} chunks")
                # if self._is_active:
                #     self._end(live_request_queue)
                #     self._start(live_request_queue)
                self._chunk_count = 0
                
    def reset(self):
        """Reset the chunk counter."""
        with self._lock:
            self._chunk_count = 0
