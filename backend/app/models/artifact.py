
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Integer,
    BigInteger,
    Boolean,
    DateTime
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ArtifactRecord(Base):

    __tablename__ = "artifacts"

    # Internal database ID.
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    # Human-readable artifact identifier.
    artifact_id: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True
    )

    # bytes32 identifier used by Solidity.
    artifact_id_bytes32: Mapped[str] = mapped_column(
        String(66),
        unique=True
    )

    # Dataset, Model, TrainingRun, etc.
    artifact_type: Mapped[str] = mapped_column(
        String(50)
    )

    original_filename: Mapped[str] = mapped_column(
        String(255)
    )

    # Relative path inside our storage directory.
    storage_key: Mapped[str] = mapped_column(
        String(255)
    )

    # SHA-256 hash with 0x prefix.
    content_hash_bytes32: Mapped[str] = mapped_column(
        String(66),
        index=True
    )

    # SHA-256 hex digest without 0x.
    sha256_hex: Mapped[str] = mapped_column(
        String(64)
    )

    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Blockchain registration tracking.
    chain_registered: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    chain_tx_hash: Mapped[str | None] = mapped_column(
        String(66),
        nullable=True
    )
