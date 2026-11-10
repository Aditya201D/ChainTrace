import os
from pathlib import Path

from dotenv import load_dotenv


# Root directory of the ChainTrace repository.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load backend environment variables.
load_dotenv(PROJECT_ROOT / "backend" / ".env")


def resolve_project_path(value: str) -> Path:
    """Resolve a path relative to the project root."""
    path = Path(value).expanduser()

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    return path.resolve()


# Storage configuration.
STORAGE_ROOT = resolve_project_path(
    os.getenv("STORAGE_ROOT", "storage")
)

ARTIFACTS_DIR = STORAGE_ROOT / "artifacts"

# SQLite database.
DATABASE_FILE = STORAGE_ROOT / "chaintrace.db"

DATABASE_URL = f"sqlite:///{DATABASE_FILE.as_posix()}"


# Blockchain configuration.
RPC_URL = os.getenv(
    "RPC_URL",
    "http://127.0.0.1:8545"
)

CONTRACT_ADDRESS = os.getenv(
    "CONTRACT_ADDRESS",
    ""
).strip()

CONTRACT_ARTIFACT_PATH = resolve_project_path(
    os.getenv(
        "CONTRACT_ARTIFACT_PATH",
        "blockchain/artifacts/contracts/"
        "ChainTraceRegistry.sol/ChainTraceRegistry.json"
    )
)

MAX_UPLOAD_SIZE_BYTES = (
    int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))
    * 1024
    * 1024
)


# Create required directories.
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
