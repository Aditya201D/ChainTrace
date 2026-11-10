
import hashlib
import uuid

from pathlib import Path
from fastapi import UploadFile

from app.config import (
    ARTIFACTS_DIR,
    STORAGE_ROOT,
    MAX_UPLOAD_SIZE_BYTES
)


class UploadTooLargeError(Exception):
    pass


class EmptyUploadError(Exception):
    pass


def save_uploaded_file(
    upload: UploadFile
) -> tuple[str, str, int]:

    # Generate a random storage filename.
    stored_filename = f"{uuid.uuid4().hex}.bin"

    destination = ARTIFACTS_DIR / stored_filename

    hasher = hashlib.sha256()
    file_size = 0

    try:

        with destination.open("xb") as output:

            while True:

                chunk = upload.file.read(1024 * 1024)

                if not chunk:
                    break

                file_size += len(chunk)

                if file_size > MAX_UPLOAD_SIZE_BYTES:
                    raise UploadTooLargeError(
                        "Maximum upload size exceeded."
                    )

                hasher.update(chunk)
                output.write(chunk)

        if file_size == 0:
            raise EmptyUploadError(
                "Uploaded file is empty."
            )

    except Exception:

        destination.unlink(missing_ok=True)
        raise

    storage_key = f"artifacts/{stored_filename}"

    sha256_hex = hasher.hexdigest()

    return storage_key, sha256_hex, file_size


def calculate_file_hash(file_path: Path) -> str:

    hasher = hashlib.sha256()

    with file_path.open("rb") as file:

        while chunk := file.read(1024 * 1024):
            hasher.update(chunk)

    return hasher.hexdigest()


def verify_stored_file(
    storage_key: str,
    expected_hash: str
) -> dict:

    # Resolve the path and prevent path traversal.
    file_path = (STORAGE_ROOT / storage_key).resolve()

    if not file_path.is_relative_to(ARTIFACTS_DIR.resolve()):
        raise ValueError("Invalid storage path.")

    if not file_path.is_file():

        return {
            "file_exists": False,
            "matches": False,
            "actual_hash": None
        }

    actual_hash = calculate_file_hash(file_path)

    return {
        "file_exists": True,
        "matches": actual_hash == expected_hash,
        "actual_hash": actual_hash
    }
