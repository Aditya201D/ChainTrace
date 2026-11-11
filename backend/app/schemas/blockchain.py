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
