"""Let browser cleanup finish after Ctrl+C instead of interrupting it again."""

import signal
import threading
from contextlib import contextmanager


@contextmanager
def defer_ctrl_c():
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)


@contextmanager
def finish_browser_call():
    """Wait for a synchronous Playwright call to settle before raising Ctrl+C.

    Raising inside Playwright's greenlet switch abandons its pending asyncio
    task. Calls have a timeout; interruption happens immediately after they finish.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    interrupted = False

    def request_stop(signum, frame):
        nonlocal interrupted
        interrupted = True

    previous = signal.signal(signal.SIGINT, request_stop)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)
        if interrupted:
            raise KeyboardInterrupt
