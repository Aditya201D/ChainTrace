from pydantic import BaseModel, Field


class PrepareRegistrationRequest(BaseModel):
    registrar_address: str = Field(
        ...,
        description="Wallet address that will sign the registration."
    )


class ConfirmRegistrationRequest(BaseModel):
    tx_hash: str = Field(
        ...,
        description="Hash of the submitted blockchain transaction."
    )

class PrepareTrainingLinkRequest(BaseModel):
    source_artifact_id: str = Field(...)
    target_artifact_id: str = Field(...)
    registrar_address: str = Field(...)


class ConfirmTrainingLinkRequest(BaseModel):
    source_artifact_id: str = Field(...)
    target_artifact_id: str = Field(...)
    tx_hash: str = Field(...)

class PrepareModelLinkRequest(BaseModel):
    training_run_id: str = Field(...)
    model_artifact_id: str = Field(...)
    registrar_address: str = Field(...)


class ConfirmModelLinkRequest(BaseModel):
    training_run_id: str = Field(...)
    model_artifact_id: str = Field(...)
    tx_hash: str = Field(...)