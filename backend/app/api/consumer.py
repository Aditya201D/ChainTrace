"""Consumer-facing verification of an existing ChainTrace deployment.

The endpoint verifies recorded integrity and current auditor approval; it does
not establish that model training or actual service deployment occurred.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from web3.exceptions import ContractLogicError

from app.core.database import get_db
from app.models.artifact import ArtifactRecord
from app.schemas.artifact import ArtifactType, ARTIFACT_TYPE_CODES
from app.services.blockchain import blockchain_service
from app.services.hashing import verify_stored_file

router = APIRouter(prefix="/api/v1/consumer", tags=["Consumer Verification"])


def _artifact_report(record: ArtifactRecord) -> dict:
    """Compare a known local record and file with the current chain."""
    stored = verify_stored_file(record.storage_key, record.sha256_hex)
    actual_hash = stored.get("actual_hash")
    file_ok = bool(
        stored.get("file_exists")
        and actual_hash is not None
        and actual_hash.lower().removeprefix("0x") == record.sha256_hex.lower()
    )
    try:
        chain = blockchain_service.get_artifact(record.artifact_id_bytes32)
    except ContractLogicError:
        chain = None

    chain_ok = bool(
        chain is not None
        and chain["exists"]
        and chain["artifact_type"] == ARTIFACT_TYPE_CODES[ArtifactType(record.artifact_type)]
        and chain["content_hash"].lower() == record.content_hash_bytes32.lower()
    )
    return {
        "artifact_id": record.artifact_id,
        "artifact_type": record.artifact_type,
        "file_exists": bool(stored.get("file_exists")),
        "file_hash_matches": file_ok,
        "blockchain_record_matches": chain_ok,
        "sqlite_chain_registered": bool(record.chain_registered),
        "verified": bool(file_ok and chain_ok),
    }


def _find_parent(
    db: Session,
    child: ArtifactRecord,
    parent_type: ArtifactType,
    relationship_code: int,
):
    """Discover parent from locally indexed artifacts, then validate on-chain."""
    candidates = db.scalars(
        select(ArtifactRecord).where(ArtifactRecord.artifact_type == parent_type.value)
    ).all()
    matches = []
    for candidate in candidates:
        try:
            # Avoid treating arbitrary stale SQLite rows as valid lineage.
            outgoing = blockchain_service.get_outgoing_links(candidate.artifact_id_bytes32)
        except ContractLogicError:
            continue
        if child.artifact_id_bytes32.lower() not in {x.lower() for x in outgoing}:
            continue
        try:
            link = blockchain_service.get_provenance_link(
                candidate.artifact_id_bytes32, child.artifact_id_bytes32
            )
        except ContractLogicError:
            continue
        if link["exists"] and link["relationship_type"] == relationship_code:
            matches.append((candidate, link))
    return matches


def _relationship(parent, child, link, name):
    return {
        "source": parent.artifact_id,
        "target": child.artifact_id,
        "relationship": name,
        "linked_by": link["linked_by"],
        "linked_at": link["linked_at"],
        "verified": bool(link["exists"]),
    }


@router.get("/deployments/{deployment_id}/verify")
def verify_deployment(deployment_id: str, db: Session = Depends(get_db)):
    deployment = db.scalar(
        select(ArtifactRecord).where(ArtifactRecord.artifact_id == deployment_id)
    )
    if deployment is None:
        raise HTTPException(404, "Deployment artifact not found")
    if deployment.artifact_type != ArtifactType.DEPLOYMENT.value:
        raise HTTPException(422, "Artifact must be a Deployment")

    try:
        # Trace backward. A parent link must exist on-chain and match its type.
        stages = [
            (ArtifactType.CONTAINER_IMAGE, 3, "DeployedAs"),
            (ArtifactType.MODEL, 2, "PackagedAs"),
            (ArtifactType.TRAINING_RUN, 1, "Produced"),
        ]
        records = {"deployment": deployment}
        relationships = []
        current = deployment
        errors = []

        for artifact_type, code, name in stages:
            parents = _find_parent(db, current, artifact_type, code)
            if len(parents) != 1:
                errors.append(
                    f"Expected one {name} predecessor for {current.artifact_id}; "
                    f"found {len(parents)} among locally indexed artifacts"
                )
                break
            parent, link = parents[0]
            records[artifact_type.value.lower()] = parent
            relationships.append(_relationship(parent, current, link, name))
            current = parent

        # A TrainingRun can legitimately consume multiple datasets.
        datasets = []
        if "trainingrun" in records:
            parents = _find_parent(
                db, records["trainingrun"], ArtifactType.DATASET, 0
            )
            if not parents:
                errors.append("No on-chain UsedForTraining datasets were found")
            for dataset, link in parents:
                datasets.append(dataset)
                relationships.append(
                    _relationship(dataset, records["trainingrun"], link, "UsedForTraining")
                )

        artifact_reports = {
            name: _artifact_report(record) for name, record in records.items()
        }
        dataset_reports = [_artifact_report(item) for item in datasets]

        approval = None
        approval_active = False
        if "model" in records:
            try:
                approval = blockchain_service.get_model_approval(
                    records["model"].artifact_id_bytes32
                )
                approval_active = bool(approval["approved"])
            except ContractLogicError:
                errors.append("Model approval could not be read from chain")

        complete = bool(
            not errors
            and all(key in records for key in (
                "deployment", "containerimage", "model", "trainingrun"
            ))
            and len(datasets) > 0
        )
        integrity_verified = bool(
            complete
            and all(x["verified"] for x in artifact_reports.values())
            and all(x["verified"] for x in dataset_reports)
            and all(x["verified"] for x in relationships)
        )
        return {
            "deployment_id": deployment_id,
            "lineage_complete": complete,
            "artifacts": artifact_reports,
            "datasets": dataset_reports,
            "relationships": relationships,
            "model_approval": approval,
            "approval_active_now": approval_active,
            "provenance_integrity_verified": integrity_verified,
            "trusted_for_current_policy": bool(integrity_verified and approval_active),
            "notes": [
                "Approval reflects current chain state, not approval at deployment time.",
                "This verifies recorded integrity and declared lineage, not actual training or live serving.",
                "Reverse lookup is limited to artifacts indexed in local SQLite.",
            ],
            "errors": errors,
        }
    except (ConnectionError, RuntimeError, FileNotFoundError, OSError) as exc:
        raise HTTPException(503, f"Verification infrastructure unavailable: {exc}") from exc
