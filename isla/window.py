"""Lazy optional GUI launcher. Importing the CLI never imports Qt."""
from __future__ import annotations

import sys
import threading

INSTALL_GUIDANCE = "Control window unavailable. Install: python -m pip install -e '.[gui]' (from the ISLA checkout). Traditional CLI: isla or python -m isla."


def run_window(controller=None):
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("Open window on the main application thread; use isla window from a shell.")
    if controller is not None:
        if getattr(controller, '_window_owner', None) is not None:
            raise RuntimeError("A control window already owns this session.")
        if controller._setup_stage is not None:
            raise RuntimeError("Finish setup audio or type cancel before opening window.")
    try:
        from isla.qt_window import launch
    except (ImportError, OSError) as exc:
        print(f"{INSTALL_GUIDANCE}\nDetails: {exc}", file=sys.stderr)
        return 1
    return launch(controller)
