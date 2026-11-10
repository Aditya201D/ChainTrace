
from enum import Enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArtifactType(str, Enum):

    DATASET = "Dataset"
    TRAINING_RUN = "TrainingRun"
    MODEL = "Model"
    CONTAINER_IMAGE = "ContainerImage"
    DEPLOYMENT = "Deployment"


# Must match the order of Solidity's ArtifactType enum.
ARTIFACT_TYPE_CODES = {
    ArtifactType.DATASET: 0,
    ArtifactType.TRAINING_RUN: 1,
    ArtifactType.MODEL: 2,
    ArtifactType.CONTAINER_IMAGE: 3,
    ArtifactType.DEPLOYMENT: 4,
}


class ArtifactResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    artifact_id: str
    artifact_id_bytes32: str

    artifact_type: str
    artifact_type_code: int

    original_filename: str

    content_hash_bytes32: str
    sha256_hex: str

    file_size_bytes: int
    mime_type: str | None

    uploaded_at: datetime

    chain_registered: bool
    chain_tx_hash: str | None
