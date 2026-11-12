
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
from web3.exceptions import ContractLogicError

from app.services.blockchain import blockchain_service

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


# ================================================
# 4. UNIFIED ARTIFACT VERIFICATION
# ================================================

@router.get("/{artifact_id}/verify")
def verify_artifact(
    artifact_id: str,
    db: Session = Depends(get_db)
):

    # Step 1: Retrieve artifact metadata.
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

    # Step 2: Verify the actual stored file.
    try:

        local_result = verify_stored_file(
            record.storage_key,
            record.sha256_hex
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    # Step 3: Check the blockchain record.
    try:

        chain_result = blockchain_service.get_artifact(
            record.artifact_id_bytes32
        )

    except ContractLogicError:

        chain_result = None

    except (ConnectionError, RuntimeError, FileNotFoundError) as exc:

        raise HTTPException(
            status_code=503,
            detail=f"Blockchain unavailable: {exc}"
        )

    # Step 4: Compare hashes.
    database_hash = record.sha256_hex.lower()

    actual_hash = (
        local_result["actual_hash"].lower()
        if local_result["actual_hash"]
        else None
    )

    local_matches = (
        actual_hash == database_hash
        if actual_hash is not None
        else False
    )

    blockchain_exists = (
        chain_result is not None
        and chain_result["exists"]
    )

    blockchain_hash = (
        chain_result["content_hash"].lower()
        if blockchain_exists
        else None
    )

    blockchain_matches = (
        blockchain_hash == record.content_hash_bytes32.lower()
        if blockchain_hash is not None
        else False
    )

    # Step 5: Determine overall verification status.
    verified = all([
        local_result["file_exists"],
        local_matches,
        blockchain_exists,
        blockchain_matches
    ])

    return {
        "artifact_id": record.artifact_id,

        "verification": {
            "file_exists": local_result["file_exists"],
            "local_hash_matches_database": local_matches,
            "blockchain_record_exists": blockchain_exists,
            "blockchain_hash_matches_database": blockchain_matches,
            "overall_verified": verified
        },

        "hashes": {
            "database_hash": database_hash,
            "local_file_hash": actual_hash,
            "blockchain_hash": blockchain_hash
        },

        "message": (
            "Artifact integrity verified successfully."
            if verified
            else "Artifact integrity verification failed."
        )
    }


# ================================================
# 5. UNIFIED MODEL PROVENANCE VERIFICATION
# ================================================

@router.get("/{model_id}/provenance")
def verify_model_provenance(
    model_id: str,
    db: Session = Depends(get_db)
):
    model = db.scalar(
        select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == model_id
        )
    )

    if model is None:
        raise HTTPException(
            status_code=404,
            detail="Model artifact not found."
        )

    if model.artifact_type != ArtifactType.MODEL.value:
        raise HTTPException(
            status_code=422,
            detail="Artifact must be a Model."
        )

    # Verify a single artifact against its stored file,
    # database metadata, and on-chain registration.
    def check_artifact(record):
        local = verify_stored_file(
            record.storage_key,
            record.sha256_hex
        )

        actual_hash = local.get("actual_hash")
        local_matches = (
            actual_hash is not None
            and actual_hash.lower() == record.sha256_hex.lower()
        )

        chain_record = None

        try:
            chain_record = blockchain_service.get_artifact(
                record.artifact_id_bytes32
            )
        except ContractLogicError:
            pass

        artifact_type = ArtifactType(record.artifact_type)
        expected_type = ARTIFACT_TYPE_CODES[artifact_type]

        chain_matches = (
            chain_record is not None
            and chain_record["exists"]
            and chain_record["artifact_type"] == expected_type
            and chain_record["content_hash"].lower()
                == record.content_hash_bytes32.lower()
        )

        return {
            "artifact_id": record.artifact_id,
            "artifact_type": record.artifact_type,
            "file_exists": local["file_exists"],
            "local_hash_matches": local_matches,
            "blockchain_record_matches": chain_matches,
            "verified": bool(
                local["file_exists"]
                and local_matches
                and chain_matches
            )
        }

    # Use the contract as the authority for relationships.
    # SQLite supplies the known human-readable artifact IDs.
    def linked_targets(source_record):
        try:
            return {
                item.lower()
                for item in blockchain_service.get_outgoing_links(
                    source_record.artifact_id_bytes32
                )
            }
        except ContractLogicError:
            return set()

    try:
        model_result = check_artifact(model)

        # Discover registered TrainingRuns that point to this Model.
        training_runs = db.scalars(
            select(ArtifactRecord).where(
                ArtifactRecord.artifact_type
                == ArtifactType.TRAINING_RUN.value,
                ArtifactRecord.chain_registered.is_(True)
            )
        ).all()

        matching_runs = []

        for run in training_runs:
            outgoing = linked_targets(run)

            if model.artifact_id_bytes32.lower() in outgoing:
                matching_runs.append(run)

        # The contract permits only one producing TrainingRun.
        if len(matching_runs) != 1:
            return {
                "model_id": model.artifact_id,
                "model": model_result,
                "training_run": None,
                "datasets": [],
                "relationships": [],
                "overall_verified": False,
                "message": (
                    "Expected exactly one producing TrainingRun; "
                    f"found {len(matching_runs)}."
                )
            }

        training_run = matching_runs[0]

        training_result = check_artifact(training_run)

        produced_link = blockchain_service.get_provenance_link(
            training_run.artifact_id_bytes32,
            model.artifact_id_bytes32
        )

        produced_verified = (
            produced_link["exists"]
            and produced_link["relationship_type"] == 1
        )

        relationships = [{
            "source": training_run.artifact_id,
            "target": model.artifact_id,
            "relationship": "Produced",
            "verified": produced_verified
        }]

        # Find all registered datasets linked to the TrainingRun.
        datasets = db.scalars(
            select(ArtifactRecord).where(
                ArtifactRecord.artifact_type
                == ArtifactType.DATASET.value,
                ArtifactRecord.chain_registered.is_(True)
            )
        ).all()

        dataset_results = []

        for dataset in datasets:
            outgoing = linked_targets(dataset)

            if (
                training_run.artifact_id_bytes32.lower()
                not in outgoing
            ):
                continue

            dataset_result = check_artifact(dataset)
            dataset_results.append(dataset_result)

            dataset_link = blockchain_service.get_provenance_link(
                dataset.artifact_id_bytes32,
                training_run.artifact_id_bytes32
            )

            link_verified = (
                dataset_link["exists"]
                and dataset_link["relationship_type"] == 0
            )

            relationships.append({
                "source": dataset.artifact_id,
                "target": training_run.artifact_id,
                "relationship": "UsedForTraining",
                "verified": link_verified
            })

        # All discovered artifacts and relationships
        # must pass verification, and at least one
        # dataset must be linked to the TrainingRun.
        artifacts_verified = all([
            model_result["verified"],
            training_result["verified"],
            len(dataset_results) > 0,
            all(item["verified"] for item in dataset_results)
        ])

        relationships_verified = all(
            item["verified"] for item in relationships
        )

        overall_verified = (
            artifacts_verified and relationships_verified
        )

        return {
            "model_id": model.artifact_id,
            "model": model_result,
            "training_run": training_result,
            "datasets": dataset_results,
            "relationships": relationships,
            "overall_verified": overall_verified,
            "message": (
                "Model provenance verified successfully."
                if overall_verified
                else "Model provenance verification failed."
            )
        }

    except ContractLogicError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"On-chain provenance lookup failed: {exc}"
        )

    except (ConnectionError, RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Blockchain unavailable: {exc}"
        )
