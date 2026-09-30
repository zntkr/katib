import logging

from core.log import DashboardLogHandler


def on_log_entry(callback) -> DashboardLogHandler:
    """Calls callback(level_tag, component, message) for every Katib log entry, exactly as
    the dashboard receives it. conftest.py detaches the handler after each test."""
    handler = DashboardLogHandler()
    handler.bridge.entry.connect(callback)
    logging.getLogger("Katib").addHandler(handler)
    return handler
