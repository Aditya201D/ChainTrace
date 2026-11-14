"""Read-only endpoints supporting the ChainTrace dashboard."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.artifact import ArtifactRecord
from app.schemas.artifact import ArtifactType

router = APIRouter(prefix="/api/v1/ui", tags=["UI Discovery"])


def present(record: ArtifactRecord) -> dict:
    return {
        "artifact_id": record.artifact_id,
        "artifact_id_bytes32": record.artifact_id_bytes32,
        "artifact_type": record.artifact_type,
        "original_filename": record.original_filename,
        "content_hash_bytes32": record.content_hash_bytes32,
        "sha256_hex": record.sha256_hex,
        "file_size_bytes": record.file_size_bytes,
        "mime_type": record.mime_type,
        "uploaded_at": record.uploaded_at,
        "chain_registered": record.chain_registered,
        "chain_tx_hash": record.chain_tx_hash,
    }


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    counts = {artifact_type.value: 0 for artifact_type in ArtifactType}
    for key, count in db.execute(
        select(ArtifactRecord.artifact_type, func.count(ArtifactRecord.id))
        .group_by(ArtifactRecord.artifact_type)
    ).all():
        counts[key] = count

    marked_registered = db.scalar(
        select(func.count(ArtifactRecord.id))
        .where(ArtifactRecord.chain_registered.is_(True))
    ) or 0
    recent = db.scalars(
        select(ArtifactRecord)
        .order_by(ArtifactRecord.uploaded_at.desc(), ArtifactRecord.id.desc())
        .limit(7)
    ).all()
    return {
        "total_artifacts": sum(counts.values()),
        "db_marked_registered": marked_registered,
        "by_type": counts,
        "recent_artifacts": [present(record) for record in recent],
    }


@router.get("/artifacts")
def artifacts(
    artifact_type: ArtifactType | None = None,
    search: str = Query(default="", max_length=150),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    filters = []
    if artifact_type is not None:
        filters.append(ArtifactRecord.artifact_type == artifact_type.value)
    if search.strip():
        term = f"%{search.strip()}%"
        filters.append(or_(
            ArtifactRecord.artifact_id.ilike(term),
            ArtifactRecord.original_filename.ilike(term),
        ))

    stmt = select(ArtifactRecord).where(*filters)
    total = db.scalar(select(func.count(ArtifactRecord.id)).where(*filters)) or 0
    rows = db.scalars(
        stmt.order_by(ArtifactRecord.uploaded_at.desc(), ArtifactRecord.id.desc())
        .offset(offset).limit(limit)
    ).all()
    return {
        "items": [present(record) for record in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
