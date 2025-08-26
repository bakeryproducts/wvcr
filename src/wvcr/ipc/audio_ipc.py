import os
import time
import socket
import struct
import threading
import queue
import multiprocessing as mp
from collections import deque 

from loguru import logger

from wvcr.services.vad import SileroVAD, NoVad


class UnixAudioInput:
    """
    Simple audio input client reading length-prefixed PCM frames from a Unix domain socket
    and exposing a get(timeout)->bytes API for consumers.
    """

    def __init__(self, socket_path: str = "/tmp/adk_audio.sock", rcvbuf_bytes: int = 4_194_304, max_frames: int = 64):
        self.socket_path = socket_path
        self.rcvbuf_bytes = int(rcvbuf_bytes)
        self.max_frames = int(max_frames)
        self._srv = None
        self._stop = threading.Event()
        self._reader_thread = None
        self._frames: queue.Queue[bytes] = queue.Queue(maxsize=self.max_frames)

    def start(self):
        # Ensure old socket file is gone
        try:
            os.unlink(self.socket_path)
        except FileNotFoundError:
            pass
        except OSError:
            # Might be an active socket; attempt close/unlink later
            pass

        self._srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.rcvbuf_bytes)
        self._srv.bind(self.socket_path)
        self._srv.listen(1)
        logger.info(f"UnixAudioInput listening on {self.socket_path}, SO_RCVBUF={self.rcvbuf_bytes}")

        self._reader_thread = threading.Thread(target=self._accept_and_read, daemon=True)
        self._reader_thread.start()

    def stop(self):
        self._stop.set()
        try:
            if self._srv:
                try:
                    self._srv.close()
                except Exception:
                    pass
        finally:
            self._srv = None
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1)
        try:
            os.unlink(self.socket_path)
        except FileNotFoundError:
            pass
        except Exception:
            pass

    def get(self, timeout: float | None = None) -> bytes:
        """Blocking pop of next audio frame. Raises queue.Empty on timeout for compatibility."""
        return self._frames.get(timeout=timeout)

    # Internal
    def _recv_exact(self, conn: socket.socket, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n and not self._stop.is_set():
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("peer closed")
            buf.extend(chunk)
        return bytes(buf)

    def _accept_and_read(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._srv.accept()
                logger.info("UnixAudioInput client connected")
                with conn:
                    while not self._stop.is_set():
                        header = self._recv_exact(conn, 4)
                        frame_len = struct.unpack("!I", header)[0]
                        if frame_len <= 0 or frame_len > 10_000_000:
                            logger.warning(f"Invalid frame_len={frame_len}, dropping")
                            break
                        data = self._recv_exact(conn, frame_len)
                        try:
                            self._frames.put_nowait(data)
                        except queue.Full:
                            # Drop oldest to keep latency bounded
                            try:
                                _ = self._frames.get_nowait()
                                self._frames.put_nowait(data)
                                logger.debug("UnixAudioInput buffer full, dropped oldest frame")
                            except queue.Empty:
                                pass
            except Exception as e:
                if not self._stop.is_set():
                    logger.debug(f"UnixAudioInput accept/read loop exception: {e}")
                time.sleep(0.1)
        logger.debug("UnixAudioInput reader thread exiting")



def _capture_worker(stop_evt,
                    socket_path: str,
                    rate: int,
                    channels: int,
                    chunk_ms: int,
                    batch_ms: int,
                    sndbuf_bytes: int,
                    warmup_ms: int,
                    enable_vad: bool):
    import pyaudio  # import inside process

    if enable_vad: vad = SileroVAD(window_ms=1000, hangover_ms=1000)
    else: vad = NoVad()


    pa = pyaudio.PyAudio()
    fpb = int(rate * chunk_ms / 1000)
    stream = pa.open(format=pyaudio.paInt16, channels=channels, rate=rate,
                     input=True, frames_per_buffer=fpb)

    # Discard initial samples to avoid device start-up transient
    if warmup_ms and warmup_ms > 0:
        warmup_frames = int(rate * warmup_ms / 1000)
        warmup_iters = max(1, (warmup_frames + fpb - 1) // fpb)
        for _ in range(warmup_iters):
            try:
                _ = stream.read(fpb, exception_on_overflow=False)
            except Exception:
                pass

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, sndbuf_bytes)

    # Retry connect until server is up or stop requested
    while not stop_evt.is_set():
        try:
            s.connect(socket_path)
            break
        except OSError:
            time.sleep(0.1)
    logger.info("Mic capture connected to Unix socket")


    def _send_payload(payload: bytes):
        header = struct.pack("!I", len(payload))
        try:
            s.sendall(header + payload)
            return True
        except (BrokenPipeError, ConnectionError, OSError):
            logger.warning("Mic capture socket send failed; exiting capture loop")
            return False


    bytes_per_sample = pa.get_sample_size(pyaudio.paInt16)  # 2 for Int16
    pre_seconds = 1.0
    prebuf_bytes = int(rate * channels * bytes_per_sample * pre_seconds)
    prebuf = deque(maxlen=prebuf_bytes)

    buf = bytearray()
    last = time.monotonic()
    try:
        while not stop_evt.is_set():
            chunk = stream.read(fpb, exception_on_overflow=False)
            if not vad.is_speech(chunk, rate):
                prebuf.extend(chunk)
                continue
            else:
                prebuf.extend(chunk)
                buf.extend(prebuf)
                prebuf.clear()

            # buf.extend(chunk)

            now = time.monotonic()
            if (now - last) * 1000 >= batch_ms:
                if buf:
                    send_buf = bytes(buf)
                    # if vad.is_speech(chunk, rate):
                    _send_payload(send_buf)
                    buf.clear()
                last = now
    finally:
        if buf:
            send_buf = bytes(buf)
            _send_payload(send_buf)
        try:
            stream.stop_stream(); stream.close()
        finally:
            pa.terminate()
        try:
            s.close()
        except Exception:
            pass
        logger.info("Mic capture process exiting")


def start_mic_capture_process(socket_path: str = "/tmp/adk_audio.sock",
                              rate: int = 16000,
                              channels: int = 1,
                              chunk_ms: int = 20,
                              batch_ms: int = 100,
                              sndbuf_bytes: int = 4_194_304,
                              warmup_ms: int = 50,
                              enable_vad: bool = False,
                              join_timeout: float = 0.3):
    """Start the background mic capture process.

    Added join_timeout + non-blocking stop support so callers can avoid the
    previous hard-coded 2s wait when stopping. The returned handle exposes
    stop(block: bool = True).
    """

    try:
        if mp.get_start_method(allow_none=True) != "spawn":
            mp.set_start_method("spawn", force=True)
    except RuntimeError:
        # Already set in this interpreter; ignore
        pass

    stop_evt = mp.Event()
    proc = mp.Process(
        target=_capture_worker,
        args=(stop_evt, socket_path, rate, channels, chunk_ms, batch_ms, sndbuf_bytes, warmup_ms, enable_vad),
        daemon=True,
    )
    proc.start()

    class _Handle:
        def __init__(self, proc, stop_evt, join_timeout: float):
            self._proc = proc
            self._stop_evt = stop_evt
            self._join_timeout = join_timeout

        def stop(self, block: bool = True):
            """Signal the process to stop.

            If block is False, returns immediately and joins in a background
            thread, avoiding latency in the caller (may sacrifice the last
            partial buffer if the socket is closed early by the caller).
            """
            self._stop_evt.set()
            if block:
                self._join_with_timeout()
            else:
                threading.Thread(target=self._join_with_timeout, daemon=True).start()

        def _join_with_timeout(self):
            if self._proc.is_alive():
                self._proc.join(timeout=self._join_timeout)
                if self._proc.is_alive():
                    logger.warning(
                        f"Mic capture process still alive after {self._join_timeout:.2f}s; continuing asynchronously"
                    )

    return _Handle(proc, stop_evt, join_timeout)
