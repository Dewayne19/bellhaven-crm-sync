"""Runtime configuration, read from the environment with sane defaults."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SNAPSHOT_PATH = DATA_DIR / "site_snapshot.json"
DB_PATH = DATA_DIR / "state.sqlite"


def _load_dotenv():
    """Minimal .env support so local runs don't need shell exports."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()

SITE_BASE = os.environ.get(
    "SITE_BASE", "https://analyst-assessment-production.up.railway.app"
)
CRM_BASE = os.environ.get("CRM_BASE", SITE_BASE + "/api/v1")
CRM_TOKEN = os.environ.get("CRM_TOKEN", "")

BELLHAVEN_PARENT_ID = os.environ.get("BELLHAVEN_PARENT_ID", "0015QAPLGS3FVYEEEM")

# Parents whose facilities Bellhaven has taken over (per the operator's About
# page: Harborview in 2025, selected Cedar Trail communities in 2026). Accounts
# still sitting under these are the expected migration candidates.
ACQUIRED_PARENT_IDS = {
    "001FJZYHR7MLFMNPLL": "Harborview Care Group",
    "001FWSQ30SFW6S7604": "Cedar Trail Communities",
}

# Name-similarity thresholds. Above STRONG we trust a name inside a matching
# postcode; between WEAK and STRONG we surface it but never auto-apply.
NAME_STRONG = 0.88
NAME_WEAK = 0.70

DATA_DIR.mkdir(exist_ok=True)
