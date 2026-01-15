from __future__ import annotations

"""Minimal IPC mic handler extracted from IPCVoiceRecorder.

Responsible only for:
 - starting the UnixAudioInput server
 - spawning the mic capture process
 - exposing get_frame(timeout)
 - stopping both (idempotent)

No additional behaviour or streaming logic here; recorder still buffers
frames in memory and writes them on stop.
"""

from loguru import logger

from wvcr.ipc.audio_ipc import UnixAudioInput, start_mic_capture_process


class IPCMicHandler:
    def __init__(self,
                 rate: int = 16000,
                 channels: int = 1,
                 socket_path: str = "/tmp/adk_audio.sock",
                 rcvbuf_bytes: int = 4_194_304,
                 max_frames: int = 256,
                 enable_vad: bool = False,
                 join_timeout: float = 0.2):
        self.rate = rate
        self.channels = channels
        self.socket_path = socket_path
        self._rcvbuf_bytes = rcvbuf_bytes
        self._max_frames = max_frames
        self._enable_vad = enable_vad
        self._join_timeout = join_timeout
        self._socket_client: UnixAudioInput | None = None
        self._capture_handle = None
        self._started = False

    def start(self):
        if self._started:
            return
        self._socket_client = UnixAudioInput(
            socket_path=self.socket_path,
            rcvbuf_bytes=self._rcvbuf_bytes,
            max_frames=self._max_frames,
        )
        self._socket_client.start()
        self._capture_handle = start_mic_capture_process(
            socket_path=self.socket_path,
            rate=self.rate,
            channels=self.channels,
            chunk_ms=20,
            batch_ms=140,
            enable_vad=self._enable_vad,
            join_timeout=self._join_timeout,
        )
        self._started = True
        logger.debug("IPCMicHandler started")

    def get_frame(self, timeout: float | None = None) -> bytes:
        if not self._socket_client:
            raise RuntimeError("IPCMicHandler not started")
        return self._socket_client.get(timeout=timeout)

    def stop(self):
        if not self._started:
            return
        # Stop capture process first so it stops sending
        try:
            if self._capture_handle:
                try:
                    self._capture_handle.stop(block=False)
                except TypeError:
                    # In case legacy handle signature differs
                    self._capture_handle.stop()
        except Exception:
            logger.exception("Error stopping capture process")
        # Then stop socket listener
        try:
            if self._socket_client:
                self._socket_client.stop()
        except Exception:
            logger.exception("Error stopping UnixAudioInput")
        self._started = False
        logger.debug("IPCMicHandler stopped")
