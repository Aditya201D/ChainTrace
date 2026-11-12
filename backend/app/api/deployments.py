"""ChainTrace 4.2B: atomic deployment registration and verification."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from web3 import Web3
from web3.exceptions import ContractLogicError, TransactionNotFound
from web3.logs import DISCARD

from app.core.database import get_db
from app.models.artifact import ArtifactRecord
from app.schemas.artifact import ArtifactType
from app.services.blockchain import blockchain_service
from app.services.hashing import verify_stored_file

router = APIRouter(prefix="/api/v1/blockchain/deployments", tags=["Deployments"])

class PrepareDeployment(BaseModel):
    container_artifact_id: str
    deployment_artifact_id: str
    operator_address: str

class ConfirmDeployment(BaseModel):
    container_artifact_id: str
    deployment_artifact_id: str
    tx_hash: str


def _pair(db, container_id, deployment_id):
    c = db.scalar(select(ArtifactRecord).where(ArtifactRecord.artifact_id == container_id))
    d = db.scalar(select(ArtifactRecord).where(ArtifactRecord.artifact_id == deployment_id))
    if c is None or d is None:
        raise HTTPException(404, "ContainerImage or Deployment artifact not found")
    if c.artifact_type != ArtifactType.CONTAINER_IMAGE.value or d.artifact_type != ArtifactType.DEPLOYMENT.value:
        raise HTTPException(422, "Expected ContainerImage source and Deployment target")
    return c, d


def _b32(value):
    return blockchain_service._decode_bytes32(value, "artifact identifier/hash")


def _chain_container(c):
    chain = blockchain_service.get_artifact(c.artifact_id_bytes32)
    if (not chain["exists"] or chain["artifact_type"] != 3 or
            chain["content_hash"].lower() != c.content_hash_bytes32.lower()):
        raise HTTPException(409, "Container metadata does not match blockchain")


def _local_integrity(record):
    actual = verify_stored_file(record.storage_key, record.sha256_hex)
    if not actual["file_exists"] or not actual["matches"]:
        raise HTTPException(409, f"Local file integrity failed: {record.artifact_id}")


@router.post("/prepare")
def prepare(request: PrepareDeployment, db: Session = Depends(get_db)):
    c, d = _pair(db, request.container_artifact_id, request.deployment_artifact_id)
    if not c.chain_registered:
        raise HTTPException(409, "Container is not registered")
    if d.chain_registered:
        raise HTTPException(409, "Deployment is already marked registered")
    if not Web3.is_address(request.operator_address):
        raise HTTPException(422, "Invalid operator wallet address")
    try:
        _local_integrity(c)
        _local_integrity(d)
        _chain_container(c)
        op = Web3.to_checksum_address(request.operator_address)
        contract = blockchain_service.get_contract()
        f = contract.functions.recordDeployment(
            _b32(c.artifact_id_bytes32), _b32(d.artifact_id_bytes32),
            _b32(d.content_hash_bytes32)
        )
        f.call({"from": op})
        tx = f.build_transaction({"from": op, "chainId": blockchain_service.w3.eth.chain_id, "value": 0})
        return {"container_id": c.artifact_id, "deployment_id": d.artifact_id,
                "transaction": {"from": op, "to": contract.address, "data": tx["data"],
                                "value": "0x0", "chain_id": blockchain_service.w3.eth.chain_id}}
    except HTTPException:
        raise
    except (ContractLogicError, ValueError) as exc:
        raise HTTPException(422, str(exc))
    except (ConnectionError, RuntimeError, FileNotFoundError, OSError) as exc:
        raise HTTPException(503, str(exc))


@router.post("/confirm")
def confirm(request: ConfirmDeployment, db: Session = Depends(get_db)):
    c, d = _pair(db, request.container_artifact_id, request.deployment_artifact_id)
    try:
        h = request.tx_hash
        if not h.startswith("0x") or len(h) != 66:
            raise ValueError("Invalid transaction hash")
        bytes.fromhex(h[2:])
        w3 = blockchain_service.w3
        contract = blockchain_service.get_contract()
        tx = w3.eth.get_transaction(h)
        receipt = w3.eth.get_transaction_receipt(h)
        if receipt["status"] != 1 or tx["to"] is None or Web3.to_checksum_address(tx["to"]) != Web3.to_checksum_address(contract.address):
            raise ValueError("Unsuccessful transaction or wrong destination")
        reg = contract.events.ArtifactRegistered().process_receipt(receipt, errors=DISCARD)
        links = contract.events.ArtifactLinked().process_receipt(receipt, errors=DISCARD)
        expected_id = _b32(d.artifact_id_bytes32)
        expected_hash = _b32(d.content_hash_bytes32)
        container_id = _b32(c.artifact_id_bytes32)
        sender = Web3.to_checksum_address(tx["from"])
        valid_regs = [e for e in reg if bytes(e["args"]["artifactId"]) == expected_id
                      and int(e["args"]["artifactType"]) == 4
                      and bytes(e["args"]["contentHash"]) == expected_hash
                      and Web3.to_checksum_address(e["args"]["registeredBy"]) == sender]
        valid_links = [e for e in links if bytes(e["args"]["sourceArtifactId"]) == container_id
                       and bytes(e["args"]["targetArtifactId"]) == expected_id
                       and int(e["args"]["relationshipType"]) == 3
                       and Web3.to_checksum_address(e["args"]["linkedBy"]) == sender]
        if len(valid_regs) != 1 or len(valid_links) != 1:
            raise ValueError("Expected matching ArtifactRegistered and ArtifactLinked events")
        actual_artifact = blockchain_service.get_artifact(d.artifact_id_bytes32)
        actual_link = blockchain_service.get_provenance_link(c.artifact_id_bytes32, d.artifact_id_bytes32)
        if (not actual_artifact["exists"] or actual_artifact["artifact_type"] != 4 or
                actual_artifact["content_hash"].lower() != d.content_hash_bytes32.lower() or
                not actual_link["exists"] or actual_link["relationship_type"] != 3):
            raise ValueError("Current deployment state does not match transaction")
        canonical = Web3.to_hex(receipt["transactionHash"])
        if d.chain_registered and d.chain_tx_hash and d.chain_tx_hash.lower() != canonical.lower():
            raise HTTPException(409, "Deployment already confirmed using another transaction")
        d.chain_registered = True
        d.chain_tx_hash = canonical
        db.commit()
        return {"deployment_id": d.artifact_id, "container_id": c.artifact_id,
                "chain_registered": True, "chain_tx_hash": canonical,
                "block_number": int(receipt["blockNumber"]), "relationship": "DeployedAs",
                "verified": True}
    except HTTPException:
        raise
    except TransactionNotFound:
        raise HTTPException(409, "Transaction not mined or no longer on this chain")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(500, "Blockchain succeeded but SQLite update failed; retry confirmation")
    except (ValueError, ContractLogicError) as exc:
        raise HTTPException(422, str(exc))
    except (ConnectionError, RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(503, str(exc))


@router.get("/{container_id}/{deployment_id}")
def read(container_id: str, deployment_id: str, db: Session = Depends(get_db)):
    c, d = _pair(db, container_id, deployment_id)
    try:
        artifact = blockchain_service.get_artifact(d.artifact_id_bytes32)
        link = blockchain_service.get_provenance_link(c.artifact_id_bytes32, d.artifact_id_bytes32)
        valid = (artifact["exists"] and artifact["artifact_type"] == 4 and
                 artifact["content_hash"].lower() == d.content_hash_bytes32.lower() and
                 link["exists"] and link["relationship_type"] == 3)
        return {"deployment_id": d.artifact_id, "container_id": c.artifact_id,
                "deployment": artifact, "relationship": link, "verified": bool(valid)}
    except ContractLogicError:
        raise HTTPException(404, "Deployment registration or relationship not found")
