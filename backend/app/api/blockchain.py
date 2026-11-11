
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from web3 import Web3
from web3.exceptions import TransactionNotFound
from web3.exceptions import ContractLogicError

from app.core.database import get_db
from app.models.artifact import ArtifactRecord

from app.schemas.artifact import (
    ArtifactType,
    ARTIFACT_TYPE_CODES
)

from app.schemas.blockchain import (
    PrepareRegistrationRequest,
    ConfirmRegistrationRequest
)

from app.services.blockchain import blockchain_service


router = APIRouter(
    prefix="/api/v1/blockchain",
    tags=["Blockchain"]
)


# ================================================
# 1. BLOCKCHAIN STATUS
# ================================================

@router.get("/status")
def blockchain_status():

    try:
        return blockchain_service.get_status()

    except (ConnectionError, RuntimeError, FileNotFoundError) as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )


# ================================================
# 2. GET ON-CHAIN ARTIFACT
# ================================================

@router.get("/artifacts/{artifact_id_bytes32}")
def get_on_chain_artifact(artifact_id_bytes32: str):

    try:

        return blockchain_service.get_artifact(
            artifact_id_bytes32
        )

    except ContractLogicError:

        raise HTTPException(
            status_code=404,
            detail="Artifact does not exist on the blockchain."
        )

    except (ConnectionError, RuntimeError, FileNotFoundError) as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )


# ================================================
# 3. PREPARE ARTIFACT REGISTRATION
# ================================================

@router.post("/artifacts/{artifact_id}/prepare-registration")
def prepare_artifact_registration(
    artifact_id: str,
    request: PrepareRegistrationRequest,
    db: Session = Depends(get_db)
):

    # Retrieve the artifact from our database.
    record = db.scalar(
        select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == artifact_id
        )
    )

    if record is None:

        raise HTTPException(
            status_code=404,
            detail="Artifact not found in database."
        )

    if record.chain_registered:

        raise HTTPException(
            status_code=409,
            detail="Artifact is already registered on blockchain."
        )

    # Deployment artifacts must use the dedicated
    # recordDeployment contract operation.
    if record.artifact_type == ArtifactType.DEPLOYMENT.value:

        raise HTTPException(
            status_code=422,
            detail="Deployment artifacts require the deployment workflow."
        )

    try:

        artifact_type = ArtifactType(record.artifact_type)

        artifact_type_code = ARTIFACT_TYPE_CODES[artifact_type]

        transaction = (
            blockchain_service.prepare_artifact_registration(
                artifact_id_bytes32=record.artifact_id_bytes32,
                artifact_type_code=artifact_type_code,
                content_hash_bytes32=record.content_hash_bytes32,
                registrar_address=request.registrar_address
            )
        )

        return {
            "artifact_id": record.artifact_id,
            "artifact_type": record.artifact_type,
            "content_hash": record.content_hash_bytes32,
            "transaction": transaction,
            "message": "Transaction prepared. Awaiting wallet signature."
        }

    except PermissionError as exc:

        raise HTTPException(
            status_code=403,
            detail=str(exc)
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc)
        )

    except (ConnectionError, RuntimeError, FileNotFoundError) as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )


# ================================================
# 4. CONFIRM ARTIFACT REGISTRATION
# ================================================

@router.post("/artifacts/{artifact_id}/confirm-registration")
def confirm_artifact_registration(
    artifact_id: str,
    request: ConfirmRegistrationRequest,
    db: Session = Depends(get_db)
):

    # Validate transaction hash format.
    if (
        not request.tx_hash.startswith("0x")
        or len(request.tx_hash) != 66
    ):

        raise HTTPException(
            status_code=422,
            detail="Invalid transaction hash."
        )

    try:
        bytes.fromhex(request.tx_hash[2:])
    except ValueError:

        raise HTTPException(
            status_code=422,
            detail="Invalid hexadecimal transaction hash."
        )

    record = db.scalar(
        select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == artifact_id
        )
    )

    if record is None:

        raise HTTPException(
            status_code=404,
            detail="Artifact not found in database."
        )

    tx_hash = Web3.to_hex(
        Web3.to_bytes(hexstr=request.tx_hash)
    )

    # Make confirmation idempotent.
    if record.chain_registered:

        if record.chain_tx_hash == tx_hash:

            return {
                "artifact_id": artifact_id,
                "chain_registered": True,
                "chain_tx_hash": tx_hash,
                "message": "Registration was already confirmed."
            }

        raise HTTPException(
            status_code=409,
            detail="Artifact has already been registered."
        )

    try:

        artifact_type = ArtifactType(record.artifact_type)

        verification = (
            blockchain_service.confirm_artifact_registration(
                tx_hash=tx_hash,
                expected_artifact_id=record.artifact_id_bytes32,
                expected_artifact_type=ARTIFACT_TYPE_CODES[artifact_type],
                expected_content_hash=record.content_hash_bytes32
            )
        )

    except TransactionNotFound:

        raise HTTPException(
            status_code=409,
            detail="Transaction has not been mined yet. Retry later."
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc)
        )

    except (ConnectionError, RuntimeError, FileNotFoundError) as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )

    # Only update the database after verifying
    # the actual blockchain transaction and event.
    try:

        record.chain_registered = True
        record.chain_tx_hash = tx_hash

        db.commit()
        db.refresh(record)

    except SQLAlchemyError:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Blockchain registration succeeded, "
                "but database confirmation failed. "
                "Retry the confirmation request."
            )
        )

    return {
        "artifact_id": artifact_id,
        "chain_registered": True,
        "chain_tx_hash": tx_hash,
        "verification": verification,
        "message": "Artifact successfully registered on blockchain."
    }


# ================================================
# 5. VERIFY ON-CHAIN ARTIFACT HASH
# ================================================

@router.get("/artifacts/{artifact_id_bytes32}/verify")
def verify_on_chain_artifact(
    artifact_id_bytes32: str,
    content_hash: str
):

    try:

        result = blockchain_service.verify_artifact(
            artifact_id_bytes32,
            content_hash
        )

        return {
            "artifact_id": artifact_id_bytes32,
            "supplied_hash": content_hash,
            "verified": result
        }

    except ContractLogicError:

        raise HTTPException(
            status_code=404,
            detail="Artifact does not exist on the blockchain."
        )

    except (ConnectionError, RuntimeError, FileNotFoundError) as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )
