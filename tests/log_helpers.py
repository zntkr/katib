import logging

from core.log import LogViewHandler


def on_log_entry(callback) -> LogViewHandler:
    """Calls callback(level_tag, component, message) for every Katib log entry, exactly as
    the log tab receives it. conftest.py detaches the handler after each test."""
    handler = LogViewHandler()
    handler.bridge.entry.connect(callback)
    logging.getLogger("Katib").addHandler(handler)
    return handler
