import time
from typing import List
from loguru import logger
from .step import Step, StepError
from .state import WorkingState

class Pipeline:
    def __init__(self, steps: List[Step]):
        self.steps = steps

    def validate(self):
        provided = set()
        for step in self.steps:
            missing = step.requires - provided
            if missing:
                raise ValueError(f"Step '{step.name}' missing prerequisites: {missing}")
            provided |= step.provides

    def run(self, state: WorkingState, ctx):
        self.validate()
        for step in self.steps:
            if not step.enabled(ctx, state):
                logger.debug(f"[pipeline] Skip step {step.name}")
                continue
            start = time.monotonic()
            logger.debug(f"[pipeline] Begin {step.name}")
            try:
                step.execute(state, ctx)
            except StepError as e:
                state.errors.append(f"{step.name}: {e}")
                logger.error(f"[pipeline] {step.name} error: {e}")
                # Send notification about the error
                self._notify_error(ctx, step.name, str(e))
                if not e.recoverable:
                    break
            except Exception as e:
                state.errors.append(f"{step.name}: {e}")
                logger.exception(f"[pipeline] {step.name} unexpected error")
                # Send notification about the unexpected error
                self._notify_error(ctx, step.name, str(e))
                break
            finally:
                duration = time.monotonic() - start
                state.timeline.append((step.name, duration))
                logger.debug(f"[pipeline] End {step.name} ({duration:.2f}s)")
        return state

    def _notify_error(self, ctx, step_name: str, error_message: str):
        """Send a notification about a pipeline error."""
        try:
            # Truncate long error messages
            max_length = 200
            if len(error_message) > max_length:
                error_message = error_message[:max_length] + "..."
            
            title = f"WVCR Error: {step_name}"
            ctx.notifier.send_notification(title, error_message, timeout=15)
        except Exception as notify_err:
            # Don't let notification errors crash the pipeline
            logger.warning(f"Failed to send error notification: {notify_err}")
