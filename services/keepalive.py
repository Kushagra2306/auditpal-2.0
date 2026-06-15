"""Background session keepalive for NotebookLM.

Google sessions expire on inactivity. A single daemon thread pings
list_notebooks every INTERVAL_HOURS hours so the shared session stays
alive across a multi-user testing window without any manual re-login.
"""

import threading
import time
import logging

INTERVAL_HOURS = 2

_started = False
_lock = threading.Lock()
logger = logging.getLogger(__name__)


def start_keepalive() -> None:
    """Start the keepalive thread exactly once per process."""
    global _started
    with _lock:
        if _started:
            return
        _started = True

    t = threading.Thread(target=_loop, daemon=True, name="notebooklm-keepalive")
    t.start()


def _loop() -> None:
    # Wait one full interval before the first ping so startup isn't slowed.
    time.sleep(INTERVAL_HOURS * 3600)
    while True:
        _ping()
        time.sleep(INTERVAL_HOURS * 3600)


def _ping() -> None:
    try:
        from services.notebook import NotebookService
        NotebookService().list_notebooks()
        logger.info("keepalive: NotebookLM session refreshed")
    except Exception as exc:
        logger.warning("keepalive: ping failed — %s", exc)
