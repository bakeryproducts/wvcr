import time
import queue
import threading

import pyaudio
from loguru import logger


class AudioPlayer:
    def __init__(self, rate=24000, channels=1, frames_per_buffer=1024, debug=False, name="AudioPlayer", buffer_seconds: float = 300.0):
        self.rate = rate
        self.channels = channels
        self.frames_per_buffer = frames_per_buffer
        self.debug = debug
        self._name = name
        # Time-based capacity (in sample frames). Default ~5 minutes at given rate.
        self._max_frames = int(self.rate * buffer_seconds)
        # Tracks total queued frames awaiting playback.
        self._queued_frames = 0
        self._cv = threading.Condition()  # guards _queued_frames and coordinates backpressure

        # Debug state
        self._enq_seq = 0
        self._deq_seq = 0
        self._silence_writes = 0
        self._dropped_writes = 0
        self._last_play_ts = None
        self._last_log_ts = 0.0

        # Configure loguru logger level based on debug flag
        if not self.debug:
            logger.disable(__name__)

        # Unbounded queue; we enforce capacity via time-based backpressure
        self._q = queue.Queue(maxsize=0)
        self._stop = threading.Event()
        self._clear = threading.Event()
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.rate,
            output=True,
            frames_per_buffer=self.frames_per_buffer,
        )
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        if self.debug:
            logger.info(
                "Starting stream",
                name=self._name,
                rate=self.rate,
                channels=self.channels,
                frames_per_buffer=self.frames_per_buffer,
                buffer_seconds=self._max_frames / max(1, self.rate)
            )
        self._thread.start()

    def stop(self):
        if self.debug:
            logger.info("Stopping stream (signaling thread)", name=self._name)
        # Unblock any writers waiting on capacity and the player thread waiting on queue
        with self._cv:
            self._stop.set()
            self._cv.notify_all()
        self._q.put(b"")  # unblock get
        self._thread.join(timeout=2)
        try:
            self._stream.stop_stream()
            self._stream.close()
        finally:
            self._pa.terminate()
        if self.debug:
            logger.info(
                "Stopped",
                name=self._name,
                enq=self._enq_seq,
                deq=self._deq_seq,
                dropped=self._dropped_writes,
                silence_writes=self._silence_writes,
                q_remaining=self._q.qsize(),
                queued_frames=self._queued_frames
            )

    def write(self, data: bytes):

        frame_width = self.channels * 2  # int16 per channel
        if self.debug and (len(data) % frame_width) != 0:
            logger.warning("Unaligned chunk size", name=self._name, bytes=len(data), frame_width=frame_width)

        frames = len(data) // frame_width
        # Block when the buffered duration exceeds the configured capacity.
        with self._cv:
            while not self._stop.is_set() and (self._queued_frames + frames) > self._max_frames:
                self._cv.wait(timeout=0.1)
            if self._stop.is_set():
                return
            self._queued_frames += frames

        # Enqueue the data (no drop)
        try:
            self._q.put(bytes(data))
            self._enq_seq += 1
            if self.debug:
                backlog_ms = (self._queued_frames / max(1, self.rate)) * 1000.0
                logger.debug(
                    "Enqueued data",
                    name=self._name,
                    seq=self._enq_seq,
                    bytes=len(data),
                    samples=frames,
                    qsize=self._q.qsize(),
                    backlog_ms=backlog_ms
                )
        except Exception as e:
            # Should not happen with unbounded queue; keep for safety
            self._dropped_writes += 1
            if self.debug:
                logger.warning(
                    "Enqueue failed: dropping chunk",
                    name=self._name,
                    bytes=len(data),
                    dropped_total=self._dropped_writes,
                    error=str(e)
                )

    def clear(self):
        if self.debug:
            logger.info("Clearing playback queue", name=self._name)
        # Only drain queued chunks. We do not set a flag to drop the next dequeued chunk,
        # so the first chunk of a new response will not be lost.
        frame_width = self.channels * 2
        drained = 0
        drained_frames = 0
        while not self._q.empty():
            try:
                chunk = self._q.get_nowait()
                drained += 1
                drained_frames += (len(chunk) // frame_width)
            except queue.Empty:
                break
        # Adjust buffered frame counter and wake any waiting producers
        with self._cv:
            self._queued_frames = max(0, self._queued_frames - drained_frames)
            self._cv.notify_all()
        if self.debug:
            logger.info("Cleared queue", name=self._name, items=drained, drained_frames=drained_frames)

    def _run(self):
        frame_width = self.channels * 2
        silence = b"\x00\x00" * self.frames_per_buffer
        while not self._stop.is_set():
            try:
                chunk = self._q.get(timeout=0.05)
            except queue.Empty:
                # periodic summary while idle
                self._silence_writes += 1
                if self.debug:
                    now = time.time()
                    if now - self._last_log_ts >= 1.0:
                        self._last_log_ts = now
                        logger.debug(
                            "Idle: writing silence",
                            name=self._name,
                            qsize=self._q.qsize(),
                            silence_writes=self._silence_writes
                        )
                self._stream.write(silence)
                continue

            if self._clear.is_set():
                # Drop this dequeued chunk (turn boundary or barge-in) and fix counters
                frames = len(chunk) // frame_width
                with self._cv:
                    self._queued_frames = max(0, self._queued_frames - frames)
                    self._cv.notify_all()
                self._clear.clear()
                if self.debug:
                    logger.debug("Clear flag set: dropped one dequeued chunk", name=self._name)
                continue

            if chunk:
                t0 = time.time()
                self._stream.write(chunk)
                t1 = time.time()
                self._deq_seq += 1
                # Decrement buffered frames and wake any waiting producers
                frames = len(chunk) // frame_width
                with self._cv:
                    self._queued_frames = max(0, self._queued_frames - frames)
                    self._cv.notify_all()

                if self.debug:
                    samples = frames
                    gap = None if self._last_play_ts is None else max(0.0, t0 - self._last_play_ts)
                    logger.debug(
                        "Playing audio",
                        name=self._name,
                        seq=self._deq_seq,
                        bytes=len(chunk),
                        samples=samples,
                        write_ms=(t1 - t0) * 1000,
                        gap_ms=(gap or 0.0) * 1000,
                        qsize=self._q.qsize()
                    )
                self._last_play_ts = t1
            else:
                # Empty chunk used to unblock on stop; write one silence buffer
                self._silence_writes += 1
                if self.debug:
                    logger.debug("Received empty chunk: writing one silence buffer", name=self._name)
                self._stream.write(silence)