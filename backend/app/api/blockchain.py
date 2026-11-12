
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from web3 import Web3
from web3.exceptions import TransactionNotFound
from web3.exceptions import ContractLogicError
from web3.logs import DISCARD

from app.core.database import get_db
from app.models.artifact import ArtifactRecord

from app.schemas.artifact import (
    ArtifactType,
    ARTIFACT_TYPE_CODES
)

from app.schemas.blockchain import (
    PrepareRegistrationRequest,
    ConfirmRegistrationRequest,
    PrepareTrainingLinkRequest,
    ConfirmTrainingLinkRequest,
    PrepareModelLinkRequest,
    ConfirmModelLinkRequest,
    PrepareModelApprovalRequest,
    ConfirmModelApprovalRequest,
    PrepareModelRevocationRequest,
    ConfirmModelRevocationRequest
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

# ================================================
# 6. TRAINING PROVENANCE — HELPER
# ================================================

def get_training_pair(
    db: Session,
    source_artifact_id: str,
    target_artifact_id: str
):

    source = db.scalar(
        select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == source_artifact_id
        )
    )

    target = db.scalar(
        select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == target_artifact_id
        )
    )

    if source is None or target is None:
        raise HTTPException(
            status_code=404,
            detail="Source or target artifact not found."
        )

    if source.artifact_type != ArtifactType.DATASET.value:
        raise HTTPException(
            status_code=422,
            detail="Source artifact must be a Dataset."
        )

    if target.artifact_type != ArtifactType.TRAINING_RUN.value:
        raise HTTPException(
            status_code=422,
            detail="Target artifact must be a TrainingRun."
        )

    if not source.chain_registered or not target.chain_registered:
        raise HTTPException(
            status_code=409,
            detail="Both artifacts must be registered on blockchain."
        )

    return source, target


# ================================================
# 7. PREPARE DATASET → TRAINING RUN LINK
# ================================================

@router.post("/provenance/prepare-training-link")
def prepare_training_link(
    request: PrepareTrainingLinkRequest,
    db: Session = Depends(get_db)
):

    source, target = get_training_pair(
        db,
        request.source_artifact_id,
        request.target_artifact_id
    )

    try:

        # Verify that the on-chain records match the database.
        for record, expected_type in [
            (source, ARTIFACT_TYPE_CODES[ArtifactType.DATASET]),
            (target, ARTIFACT_TYPE_CODES[ArtifactType.TRAINING_RUN])
        ]:

            chain_record = blockchain_service.get_artifact(
                record.artifact_id_bytes32
            )

            if (
                not chain_record["exists"]
                or chain_record["artifact_type"] != expected_type
                or chain_record["content_hash"].lower()
                != record.content_hash_bytes32.lower()
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "On-chain artifact metadata does not "
                        "match the database."
                    )
                )

        transaction = blockchain_service.prepare_training_link(
            source_artifact_id=source.artifact_id_bytes32,
            target_artifact_id=target.artifact_id_bytes32,
            registrar_address=request.registrar_address
        )

        return {
            "source_artifact_id": source.artifact_id,
            "target_artifact_id": target.artifact_id,
            "relationship": "UsedForTraining",
            "transaction": transaction,
            "message": "Provenance transaction prepared."
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc)
        )

    except (
        ConnectionError,
        RuntimeError,
        FileNotFoundError
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )


# ================================================
# 8. CONFIRM DATASET → TRAINING RUN LINK
# ================================================

@router.post("/provenance/confirm-training-link")
def confirm_training_link(
    request: ConfirmTrainingLinkRequest,
    db: Session = Depends(get_db)
):

    # Validate transaction hash.
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

    source, target = get_training_pair(
        db,
        request.source_artifact_id,
        request.target_artifact_id
    )

    tx_hash = Web3.to_hex(
        Web3.to_bytes(hexstr=request.tx_hash)
    )

    try:

        verification = blockchain_service.confirm_training_link(
            tx_hash=tx_hash,
            expected_source_id=source.artifact_id_bytes32,
            expected_target_id=target.artifact_id_bytes32
        )

        return {
            "source_artifact_id": source.artifact_id,
            "target_artifact_id": target.artifact_id,
            "relationship": "UsedForTraining",
            "verification": verification,
            "message": "Provenance relationship successfully recorded."
        }

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

    except (
        ConnectionError,
        RuntimeError,
        FileNotFoundError
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )


# ================================================
# 9. GET PROVENANCE LINK
# ================================================

@router.get(
    "/provenance/{source_artifact_id}/{target_artifact_id}"
)
def get_training_provenance(
    source_artifact_id: str,
    target_artifact_id: str,
    db: Session = Depends(get_db)
):

    source, target = get_training_pair(
        db,
        source_artifact_id,
        target_artifact_id
    )

    try:

        return blockchain_service.get_provenance_link(
            source.artifact_id_bytes32,
            target.artifact_id_bytes32
        )

    except ContractLogicError:

        raise HTTPException(
            status_code=404,
            detail="Provenance relationship does not exist."
        )

    except (
        ConnectionError,
        RuntimeError,
        FileNotFoundError
    ) as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )


# ================================================
# 10. MODEL PROVENANCE — HELPER
# ================================================

def get_model_pair(
    db: Session,
    training_run_id: str,
    model_artifact_id: str
):
    training_run = db.scalar(
        select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == training_run_id
        )
    )

    model = db.scalar(
        select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == model_artifact_id
        )
    )

    if training_run is None or model is None:
        raise HTTPException(
            status_code=404,
            detail="TrainingRun or Model artifact not found."
        )

    if training_run.artifact_type != ArtifactType.TRAINING_RUN.value:
        raise HTTPException(
            status_code=422,
            detail="Source artifact must be a TrainingRun."
        )

    if model.artifact_type != ArtifactType.MODEL.value:
        raise HTTPException(
            status_code=422,
            detail="Target artifact must be a Model."
        )

    if not training_run.chain_registered or not model.chain_registered:
        raise HTTPException(
            status_code=409,
            detail="Both artifacts must be registered on blockchain."
        )

    return training_run, model


# ================================================
# 11. PREPARE TRAINING RUN -> MODEL LINK
# ================================================

@router.post("/provenance/prepare-model-link")
def prepare_model_link(
    request: PrepareModelLinkRequest,
    db: Session = Depends(get_db)
):
    training_run, model = get_model_pair(
        db,
        request.training_run_id,
        request.model_artifact_id
    )

    try:
        # Verify registered artifacts against blockchain.
        for record, expected_type in [
            (
                training_run,
                ARTIFACT_TYPE_CODES[ArtifactType.TRAINING_RUN]
            ),
            (
                model,
                ARTIFACT_TYPE_CODES[ArtifactType.MODEL]
            )
        ]:
            chain_record = blockchain_service.get_artifact(
                record.artifact_id_bytes32
            )

            if (
                not chain_record["exists"]
                or chain_record["artifact_type"] != expected_type
                or chain_record["content_hash"].lower()
                != record.content_hash_bytes32.lower()
            ):
                raise HTTPException(
                    status_code=409,
                    detail="On-chain artifact metadata mismatch."
                )

        transaction = blockchain_service.prepare_training_link(
            source_artifact_id=training_run.artifact_id_bytes32,
            target_artifact_id=model.artifact_id_bytes32,
            registrar_address=request.registrar_address,
            relationship_type=1
        )

        return {
            "training_run_id": training_run.artifact_id,
            "model_artifact_id": model.artifact_id,
            "relationship": "Produced",
            "transaction": transaction,
            "message": "Model provenance transaction prepared."
        }

    except HTTPException:
        raise

    except ContractLogicError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Smart contract rejected the link: {exc}"
        )

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    except (
        ConnectionError,
        RuntimeError,
        FileNotFoundError
    ) as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# ================================================
# 12. CONFIRM TRAINING RUN -> MODEL LINK
# ================================================

@router.post("/provenance/confirm-model-link")
def confirm_model_link(
    request: ConfirmModelLinkRequest,
    db: Session = Depends(get_db)
):
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

    training_run, model = get_model_pair(
        db,
        request.training_run_id,
        request.model_artifact_id
    )

    tx_hash = Web3.to_hex(
        Web3.to_bytes(hexstr=request.tx_hash)
    )

    try:
        verification = blockchain_service.confirm_training_link(
            tx_hash=tx_hash,
            expected_source_id=training_run.artifact_id_bytes32,
            expected_target_id=model.artifact_id_bytes32,
            relationship_type=1
        )

        return {
            "training_run_id": training_run.artifact_id,
            "model_artifact_id": model.artifact_id,
            "relationship": "Produced",
            "verification": verification,
            "message": "Model provenance successfully recorded."
        }

    except TransactionNotFound:
        raise HTTPException(
            status_code=409,
            detail="Transaction not mined yet. Retry confirmation."
        )

    except ContractLogicError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc)
        )

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    except (
        ConnectionError,
        RuntimeError,
        FileNotFoundError
    ) as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# ================================================
# 13. GET TRAINING RUN -> MODEL PROVENANCE
# ================================================

@router.get(
    "/provenance/model/{training_run_id}/{model_artifact_id}"
)
def get_model_provenance(
    training_run_id: str,
    model_artifact_id: str,
    db: Session = Depends(get_db)
):
    training_run, model = get_model_pair(
        db,
        training_run_id,
        model_artifact_id
    )

    try:
        result = blockchain_service.get_provenance_link(
            training_run.artifact_id_bytes32,
            model.artifact_id_bytes32
        )

        if (
            not result["exists"]
            or result["relationship_type"] != 1
        ):
            raise HTTPException(
                status_code=404,
                detail="Produced relationship does not exist."
            )

        return result

    except HTTPException:
        raise

    except ContractLogicError:
        raise HTTPException(
            status_code=404,
            detail="Produced relationship does not exist."
        )

    except (
        ConnectionError,
        RuntimeError,
        FileNotFoundError
    ) as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# ================================================
# 14. AUDITOR APPROVAL
# ================================================

def get_approval_model(db: Session, model_id: str):
    record = db.scalar(
        select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == model_id
        )
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Model artifact not found."
        )

    if record.artifact_type != ArtifactType.MODEL.value:
        raise HTTPException(
            status_code=422,
            detail="Artifact must be a Model."
        )

    if not record.chain_registered:
        raise HTTPException(
            status_code=409,
            detail="Model is not registered on-chain."
        )

    return record


@router.post("/audit/models/{model_id}/prepare-approval")
def prepare_model_approval(
    model_id: str,
    request: PrepareModelApprovalRequest,
    db: Session = Depends(get_db)
):
    record = get_approval_model(db, model_id)

    try:
        chain_record = blockchain_service.get_artifact(
            record.artifact_id_bytes32
        )

        if (
            not chain_record["exists"]
            or chain_record["artifact_type"] != 2
            or chain_record["content_hash"].lower()
            != record.content_hash_bytes32.lower()
        ):
            raise HTTPException(
                status_code=409,
                detail="On-chain model metadata mismatch."
            )

        transaction = blockchain_service.prepare_model_approval(
            model_id=record.artifact_id_bytes32,
            evidence_hash=request.evidence_hash,
            auditor_address=request.auditor_address
        )

        return {
            "model_id": record.artifact_id,
            "evidence_hash": request.evidence_hash,
            "transaction": transaction,
            "message": "Approval transaction prepared."
        }

    except HTTPException:
        raise

    except ContractLogicError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    except (
        ConnectionError, RuntimeError, FileNotFoundError
    ) as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/audit/models/{model_id}/confirm-approval")
def confirm_model_approval(
    model_id: str,
    request: ConfirmModelApprovalRequest,
    db: Session = Depends(get_db)
):
    record = get_approval_model(db, model_id)

    if not (
        request.tx_hash.startswith("0x")
        and len(request.tx_hash) == 66
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

    try:
        # The event supplies the evidence hash. Retrieve it
        # from the receipt, then validate the complete event.
        contract = blockchain_service.get_contract()
        receipt = blockchain_service.w3.eth.get_transaction_receipt(
            request.tx_hash
        )

        events = contract.events.ModelApproved().process_receipt(
            receipt,
            errors=DISCARD
        )

        matching = [
            event for event in events
            if Web3.to_hex(
                event["args"]["modelArtifactId"]
            ).lower() == record.artifact_id_bytes32.lower()
        ]

        if len(matching) != 1:
            raise HTTPException(
                status_code=422,
                detail="Matching approval event not found."
            )

        evidence_hash = Web3.to_hex(
            matching[0]["args"]["evidenceHash"]
        )

        result = blockchain_service.confirm_model_approval(
            tx_hash=request.tx_hash,
            expected_model_id=record.artifact_id_bytes32,
            expected_model_hash=record.content_hash_bytes32,
            expected_evidence_hash=evidence_hash
        )

        return {
            "model_id": record.artifact_id,
            "verification": result,
            "message": "Approval transaction verified."
        }

    except HTTPException:
        raise

    except TransactionNotFound:
        raise HTTPException(
            status_code=409,
            detail="Transaction not mined yet."
        )

    except (ContractLogicError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    except (
        ConnectionError, RuntimeError, FileNotFoundError
    ) as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/audit/models/{model_id}/status")
def get_model_audit_status(
    model_id: str,
    db: Session = Depends(get_db)
):
    record = get_approval_model(db, model_id)

    try:
        result = blockchain_service.get_model_approval(
            record.artifact_id_bytes32
        )

        return {
            "model_id": record.artifact_id,
            "approval": result
        }

    except ContractLogicError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    except (
        ConnectionError, RuntimeError, FileNotFoundError
    ) as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# ================================================
# 15. AUDITOR APPROVAL REVOCATION
# ================================================

@router.post("/audit/models/{model_id}/prepare-revocation")
def prepare_model_revocation(
    model_id: str,
    request: PrepareModelRevocationRequest,
    db: Session = Depends(get_db)
):
    record = get_approval_model(db, model_id)

    try:
        chain_record = blockchain_service.get_artifact(
            record.artifact_id_bytes32
        )

        if (
            not chain_record["exists"]
            or chain_record["artifact_type"] != 2
            or chain_record["content_hash"].lower()
            != record.content_hash_bytes32.lower()
        ):
            raise HTTPException(
                status_code=409,
                detail="On-chain model metadata mismatch."
            )

        transaction = blockchain_service.prepare_model_revocation(
            model_id=record.artifact_id_bytes32,
            auditor_address=request.auditor_address
        )

        return {
            "model_id": record.artifact_id,
            "transaction": transaction,
            "message": "Revocation transaction prepared."
        }

    except HTTPException:
        raise

    except ContractLogicError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    except (
        ConnectionError, RuntimeError, FileNotFoundError
    ) as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/audit/models/{model_id}/confirm-revocation")
def confirm_model_revocation(
    model_id: str,
    request: ConfirmModelRevocationRequest,
    db: Session = Depends(get_db)
):
    record = get_approval_model(db, model_id)

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

    try:
        result = blockchain_service.confirm_model_revocation(
            tx_hash=request.tx_hash,
            expected_model_id=record.artifact_id_bytes32
        )

        return {
            "model_id": record.artifact_id,
            "verification": result,
            "message": "Revocation transaction verified."
        }

    except TransactionNotFound:
        raise HTTPException(
            status_code=409,
            detail="Transaction not mined yet. Retry confirmation."
        )

    except (ContractLogicError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    except (
        ConnectionError, RuntimeError, FileNotFoundError
    ) as exc:
        raise HTTPException(status_code=503, detail=str(exc))
