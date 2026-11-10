
from fastapi import APIRouter, HTTPException, Query

from web3.exceptions import ContractLogicError

from app.services.blockchain import blockchain_service


router = APIRouter(
    prefix="/api/v1/blockchain",
    tags=["Blockchain"]
)


@router.get("/status")
def blockchain_status():

    return blockchain_service.get_status()


@router.get("/artifacts/{artifact_id_bytes32}")
def get_on_chain_artifact(artifact_id_bytes32: str):

    try:

        return blockchain_service.get_artifact(
            artifact_id_bytes32
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc)
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


@router.get("/artifacts/{artifact_id_bytes32}/verify")
def verify_on_chain_artifact(
    artifact_id_bytes32: str,
    content_hash: str = Query(...)
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

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc)
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
