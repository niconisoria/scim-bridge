from dataclasses import dataclass
from typing import Awaitable, Callable
from uuid import uuid4

from app.core.logging import get_logger


@dataclass
class Step:
    name: str
    forward: Callable[[], Awaitable[None]]
    rollback: Callable[[], Awaitable[None]] | None = None


class SagaError(Exception):
    def __init__(self, saga_id: str, failed_step: str) -> None:
        self.saga_id = saga_id
        self.failed_step = failed_step
        super().__init__(f"Saga {saga_id} failed at step {failed_step!r}")


async def run_saga(steps: list[Step]) -> None:
    saga_id = str(uuid4())
    log = get_logger().bind(saga_id=saga_id)
    completed: list[Step] = []
    log.info("saga.start", step_count=len(steps))
    for step in steps:
        log.info("step.start", step=step.name)
        try:
            await step.forward()
            completed.append(step)
            log.info("step.done", step=step.name)
        except Exception:
            log.error("step.failed", step=step.name)
            log.info("saga.compensating")
            for s in reversed(completed):
                if s.rollback:
                    try:
                        await s.rollback()
                    except Exception:
                        log.error("rollback.error", step=s.name)
            log.error("saga.failed", failed_step=step.name)
            raise SagaError(saga_id, step.name)
    log.info("saga.completed")
