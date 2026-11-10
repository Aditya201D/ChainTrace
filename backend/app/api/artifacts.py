
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile
)

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from web3 import Web3

from app.config import STORAGE_ROOT
from app.core.database import get_db
from app.models.artifact import ArtifactRecord
from app.schemas.artifact import (
    ArtifactType,
    ArtifactResponse,
    ARTIFACT_TYPE_CODES
)

from app.services.hashing import (
    save_uploaded_file,
    verify_stored_file,
    UploadTooLargeError,
    EmptyUploadError
)


router = APIRouter(
    prefix="/api/v1/artifacts",
    tags=["Artifacts"]
)


def format_artifact(record: ArtifactRecord) -> dict:

    artifact_type = ArtifactType(record.artifact_type)

    return {
        "artifact_id": record.artifact_id,
        "artifact_id_bytes32": record.artifact_id_bytes32,
        "artifact_type": record.artifact_type,
        "artifact_type_code": ARTIFACT_TYPE_CODES[artifact_type],
        "original_filename": record.original_filename,
        "content_hash_bytes32": record.content_hash_bytes32,
        "sha256_hex": record.sha256_hex,
        "file_size_bytes": record.file_size_bytes,
        "mime_type": record.mime_type,
        "uploaded_at": record.uploaded_at,
        "chain_registered": record.chain_registered,
        "chain_tx_hash": record.chain_tx_hash
    }


# ================================================
# 1. UPLOAD AND REGISTER METADATA
# ================================================

@router.post(
    "/upload",
    response_model=ArtifactResponse,
    status_code=201
)
def upload_artifact(
    file: UploadFile = File(...),
    artifact_type: ArtifactType = Form(...),
    db: Session = Depends(get_db)
):

    try:

        storage_key, sha256_hex, file_size = (
            save_uploaded_file(file)
        )

    except UploadTooLargeError as exc:

        raise HTTPException(
            status_code=413,
            detail=str(exc)
        )

    except EmptyUploadError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except OSError:

        raise HTTPException(
            status_code=500,
            detail="Unable to store uploaded file."
        )

    # Generate a readable artifact identifier.
    artifact_id = (
        f"{artifact_type.value.lower()}:{uuid4().hex}"
    )

    # Convert the readable identifier into bytes32.
    artifact_id_bytes32 = Web3.to_hex(
        Web3.keccak(text=artifact_id)
    )

    # Convert SHA-256 into bytes32 hexadecimal format.
    content_hash_bytes32 = "0x" + sha256_hex

    original_filename = Path(
        (file.filename or "upload.bin").replace("\\", "/")
    ).name[:255]

    record = ArtifactRecord(
        artifact_id=artifact_id,
        artifact_id_bytes32=artifact_id_bytes32,
        artifact_type=artifact_type.value,
        original_filename=original_filename,
        storage_key=storage_key,
        content_hash_bytes32=content_hash_bytes32,
        sha256_hex=sha256_hex,
        file_size_bytes=file_size,
        mime_type=file.content_type,
        chain_registered=False
    )

    try:

        db.add(record)
        db.commit()
        db.refresh(record)

    except SQLAlchemyError:

        db.rollback()

        (STORAGE_ROOT / storage_key).unlink(missing_ok=True)

        raise HTTPException(
            status_code=500,
            detail="Unable to save artifact metadata."
        )

    return format_artifact(record)


# ================================================
# 2. GET ARTIFACT METADATA
# ================================================

@router.get(
    "/{artifact_id}",
    response_model=ArtifactResponse
)
def get_artifact(
    artifact_id: str,
    db: Session = Depends(get_db)
):

    record = db.scalar(
        select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == artifact_id
        )
    )

    if record is None:

        raise HTTPException(
            status_code=404,
            detail="Artifact not found."
        )

    return format_artifact(record)


# ================================================
# 3. VERIFY STORED FILE
# ================================================

@router.post("/{artifact_id}/verify-storage")
def verify_artifact_storage(
    artifact_id: str,
    db: Session = Depends(get_db)
):

    record = db.scalar(
        select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == artifact_id
        )
    )

    if record is None:

        raise HTTPException(
            status_code=404,
            detail="Artifact not found."
        )

    result = verify_stored_file(
        record.storage_key,
        record.sha256_hex
    )

    return {
        "artifact_id": artifact_id,
        "original_hash": record.sha256_hex,
        **result
    }
