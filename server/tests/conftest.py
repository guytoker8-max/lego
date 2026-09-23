"""Test settings, applied before any app module reads the environment."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["BRICKSNAP_DATA"] = tempfile.mkdtemp(prefix="bricksnap-test-")
os.environ["BRICKSNAP_ADMIN_TOKEN"] = "test-admin"
os.environ["BRICKSNAP_SHIP_COUNTRIES"] = "IL"
os.environ["BRICKSNAP_BUILDS_PER_HOUR"] = "100"
os.environ["BRICKSNAP_WEB_DIST"] = os.path.join(os.environ["BRICKSNAP_DATA"], "no-web")
for key in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "ANTHROPIC_API_KEY"):
    os.environ.pop(key, None)
