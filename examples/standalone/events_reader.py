import asyncio
import threading
import queue
import time
import wave
from loguru import logger

from config import AppConfig, StreamingMode
from activity_manager import ActivityManager
from ipc.audio_ipc import UnixAudioInput

class EventsReader:
    def __init__(self, audio_input: UnixAudioInput,
                  audio_player,
                  app_config: AppConfig,
                  app_name="ADK Streaming example"):
        self.audio_input = audio_input
        self.audio_player = audio_player
        self.app_name = app_name
        self.app_config = app_config
        self.activity_manager = ActivityManager(app_config.streaming)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._forwarder_thread = None
        self._live_request_queue = None
        self._runner = None
        self._debug_wav_file = None

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        # Stop forwarder first
        if self._forwarder_thread and self._forwarder_thread.is_alive():
            self._forwarder_thread.join(timeout=2)
        # Close debug WAV file if open
        if self._debug_wav_file:
            try:
                self._debug_wav_file.close()
            except Exception:
                pass
        # Close live request queue if created
        if self._live_request_queue:
            try:
                self._live_request_queue.close()
            except Exception:
                pass
        # Join main events thread
        self._thread.join(timeout=2)

    def _run(self):
        asyncio.run(self._consume())

    async def _consume(self):
        # Lazy imports to avoid startup delay in main thread
        from google.adk.runners import InMemoryRunner
        from google.adk.agents import LiveRequestQueue
        from google.adk.sessions import Session
        from google_search_agent.agent import create_agent

        agent = create_agent(self.app_config.agent)
        self._runner = InMemoryRunner(app_name=self.app_name, agent=agent)
        self._live_request_queue = LiveRequestQueue()

        session: Session = await self._runner.session_service.create_session(app_name=self.app_name, user_id="standalone")

        if self.app_config.streaming.mode == StreamingMode.SIMULTANEOUS:
            await self._consume_simultaneous(session)
        else:
            await self._consume_turn_based(session)

    async def _consume_simultaneous(self, session):
        from google.adk.agents.run_config import RunConfig
        from google.genai import types
        from google.genai.types import Blob

        # Forwarder: lazily start/end activity based on input activity with a short inactivity timeout
        def _forwarder():
            input_active = False

            while not self._stop.is_set():
                try:
                    chunk = self.audio_input.get(timeout=0.5)
                    logger.debug(f"Got audio chunk of size {len(chunk)}")
                except queue.Empty:
                    if input_active:
                        # silence window passed: end activity once
                        self.activity_manager.on_silence_timeout(self._live_request_queue)
                        input_active = False
                    continue

                try:
                    if not input_active:
                        self.activity_manager.on_first_audio(self._live_request_queue)
                        input_active = True

                    # DEBUG: dump to wav file with proper headers
                    if not self._debug_wav_file:
                        self._debug_wav_file = wave.open("audio_dump.wav", "wb")
                        self._debug_wav_file.setnchannels(1)  # mono
                        self._debug_wav_file.setsampwidth(2)  # 16-bit
                        self._debug_wav_file.setframerate(16000)  # 16kHz sample rate
                    
                    self._debug_wav_file.writeframes(chunk)

                    blob = Blob(data=chunk, mime_type="audio/pcm")
                    self._live_request_queue.send_realtime(blob)
                    self.activity_manager.on_chunk_processed(self._live_request_queue)
                except Exception:
                    logger.exception("Failed to send audio blob")

        self._forwarder_thread = threading.Thread(target=_forwarder, daemon=True)
        self._forwarder_thread.start()
        # return

        run_config = RunConfig(
            response_modalities=["AUDIO"],
            session_resumption=types.SessionResumptionConfig(),
            realtime_input_config=types.RealtimeInputConfig(
                activity_handling=types.ActivityHandling.NO_INTERRUPTION,
                automatic_activity_detection=types.AutomaticActivityDetection(disabled=True),
            ),
        )

        live_events = self._runner.run_live(session=session, live_request_queue=self._live_request_queue, run_config=run_config)
        await self._handle_live_events(live_events)

    async def _consume_turn_based(self, session):
        from google.adk.agents.run_config import RunConfig
        from google.genai import types
        from google.genai.types import Blob

        def _forwarder():
            while not self._stop.is_set():
                try:
                    chunk = self.audio_input.get(timeout=0.5)
                    logger.debug(f"Got audio chunk of size {len(chunk)}")
                except queue.Empty:
                    continue

                try:
                    blob = Blob(data=chunk, mime_type="audio/pcm")
                    self._live_request_queue.send_realtime(blob)
                except Exception:
                    logger.exception("Failed to send audio blob")

        self._forwarder_thread = threading.Thread(target=_forwarder, daemon=True)
        self._forwarder_thread.start()

        run_config = RunConfig(
            response_modalities=["AUDIO"],
            session_resumption=types.SessionResumptionConfig(),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(disabled=False),
            ),
        )

        live_events = self._runner.run_live(session=session, live_request_queue=self._live_request_queue, run_config=run_config)
        await self._handle_live_events(live_events)

    async def _handle_live_events(self, live_events):
        awaiting_first_audio_chunk = True
        async for event in live_events:
            if self._stop.is_set():
                break
            # Turn boundaries & barge-in handling
            if event.turn_complete or event.interrupted:
                awaiting_first_audio_chunk = True
                if event.interrupted:
                    self.audio_player.clear()
                continue
            part = event.content and event.content.parts and event.content.parts[0]
            if not part:
                continue
            # On start of a new audio response, clear any leftover buffered audio
            if awaiting_first_audio_chunk and getattr(part, "inline_data", None) and part.inline_data.mime_type and part.inline_data.mime_type.startswith("audio/pcm"):
                self.audio_player.clear()
                awaiting_first_audio_chunk = False
            if getattr(part, "inline_data", None) and part.inline_data.mime_type and part.inline_data.mime_type.startswith("audio/pcm"):
                data = part.inline_data.data
                if data:

                    # if not self._debug_wav_file:
                    #     self._debug_wav_file = wave.open("audio_dump.wav", "wb")
                    #     self._debug_wav_file.setnchannels(1)  # mono
                    #     self._debug_wav_file.setsampwidth(2)  # 16-bit
                    #     self._debug_wav_file.setframerate(24000)  # 16kHz sample rate
                    
                    # self._debug_wav_file.writeframes(data)

                    self.audio_player.write(data)
            elif getattr(part, "text", None) and event.partial:
                print(part.text, end="", flush=True)
