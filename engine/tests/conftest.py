import os
import tempfile

# Isolate every test run in its own data directory before any app module is imported.
os.environ.setdefault("ULASAPP_DATA_DIR", tempfile.mkdtemp(prefix="ulasapp-test-"))

from app.core.db import init_db  # noqa: E402

init_db()
