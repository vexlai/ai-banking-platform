import os
import sys
from pathlib import Path

# Force the deterministic path before any test imports `api.main` (which builds the
# engine and reads `.env`). `load_dotenv(override=False)` never overrides an
# already-set variable, so this keeps CI/local suites off the live LLM network path.
os.environ["USE_LLM"] = "false"
os.environ.pop("OPENAI_API_KEY", None)

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
