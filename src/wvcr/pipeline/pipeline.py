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
                if not e.recoverable:
                    break
            except Exception as e:
                state.errors.append(f"{step.name}: {e}")
                logger.exception(f"[pipeline] {step.name} unexpected error")
                break
            finally:
                duration = time.monotonic() - start
                state.timeline.append((step.name, duration))
                logger.debug(f"[pipeline] End {step.name} ({duration:.2f}s)")
        return state
