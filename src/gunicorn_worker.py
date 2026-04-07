"""Custom Gunicorn worker with explicit proxy trust settings."""

import os

from uvicorn.workers import UvicornWorker


class ProxyAwareUvicornWorker(UvicornWorker):
    """Run Uvicorn under Gunicorn while honoring trusted proxy headers."""

    CONFIG_KWARGS = {
        "proxy_headers": True,
        "forwarded_allow_ips": os.getenv("FORWARDED_ALLOW_IPS", "*"),
    }
