# ChainTrace API reference (selected endpoints)

Base URL for local backend: `http://127.0.0.1:8000`  
Interactive OpenAPI documentation: `http://127.0.0.1:8000/docs`

All `{id}` placeholders below are *human-readable* IDs such as `model:<uuid>`, unless explicitly named `artifact_id_bytes32`. Percent-encode colons in URLs when needed.

## Artifact storage and integrity

| Method | Path | Role |
|---|---|---|
| POST | `/api/v1/artifacts/upload` | Upload a file as Dataset, TrainingRun, Model, ContainerImage, or Deployment |
| GET | `/api/v1/artifacts/{artifact_id}` | Read locally indexed artifact metadata |
| POST | `/api/v1/artifacts/{artifact_id}/verify-storage` | Verify the stored file's hash against SQLite |
| GET | `/api/v1/artifacts/{artifact_id}/verify` | Unified local/on-chain artifact integrity checks |
| GET | `/api/v1/artifacts/{model_id}/provenance` | Model lineage and integrity report |

Uploads are multipart form-data, with `file` and `artifact_type` fields. Uploading does not register the artifact on-chain.

## Registry discovery / status

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/ui/overview` | Counts and recent artifacts |
| GET | `/api/v1/ui/artifacts` | Artifact list with optional `artifact_type`, `search`, `limit`, `offset` |
| GET | `/api/v1/blockchain/status` | Chain connectivity, block height, contract status |
| GET | `/api/v1/blockchain/artifacts/{artifact_id_bytes32}` | Read on-chain artifact |
| GET | `/api/v1/blockchain/artifacts/{artifact_id_bytes32}/verify?content_hash=0x...` | Verify supplied content hash |

`/api/v1/ui/artifacts` allows `limit` up to 200 per request. SQLite's `chain_registered` is a cached flag; it is not proof of current blockchain registration after a node reset.

## Contract writes: prepare → sign → confirm

| Operation | Prepare endpoint | Confirm endpoint |
|---|---|---|
| Artifact registration | `POST /api/v1/blockchain/artifacts/{id}/prepare-registration` | `POST /api/v1/blockchain/artifacts/{id}/confirm-registration` |
| Dataset → TrainingRun | `POST /api/v1/blockchain/provenance/prepare-training-link` | `POST /api/v1/blockchain/provenance/confirm-training-link` |
| TrainingRun → Model | `POST /api/v1/blockchain/provenance/prepare-model-link` | `POST /api/v1/blockchain/provenance/confirm-model-link` |
| Model → ContainerImage | `POST /api/v1/blockchain/packaging/prepare` | `POST /api/v1/blockchain/packaging/confirm` |
| Model approval | `POST /api/v1/blockchain/audit/models/{id}/prepare-approval` | `POST /api/v1/blockchain/audit/models/{id}/confirm-approval` |
| Approval revocation | `POST /api/v1/blockchain/audit/models/{id}/prepare-revocation` | `POST /api/v1/blockchain/audit/models/{id}/confirm-revocation` |
| ContainerImage → Deployment | `POST /api/v1/blockchain/deployments/prepare` | `POST /api/v1/blockchain/deployments/confirm` |

Typical workflow: call `prepare` with artifact IDs and connected wallet address → sign/send prepared transaction via MetaMask → pass mined `tx_hash` to corresponding `confirm` route. Confirmation validates transaction/event content. **If mined but confirmation fails, retry confirmation only; do not re-send the same contract operation.**

## Audit, provenance, and consumer reads

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/blockchain/provenance/{dataset_id}/{training_run_id}` | Read `UsedForTraining` link |
| GET | `/api/v1/blockchain/provenance/model/{training_run_id}/{model_id}` | Read `Produced` link |
| GET | `/api/v1/blockchain/packaging/{model_id}/{container_id}` | Read `PackagedAs` link |
| GET | `/api/v1/blockchain/deployments/{container_id}/{deployment_id}` | Read deployment link |
| GET | `/api/v1/blockchain/audit/models/{model_id}/status` | Read current model approval |
| GET | `/api/v1/consumer/deployments/{deployment_id}/verify` | Whole deployment trust report |

The deployment verification policy distinguishes existence of the declared chain, integrity of discovered artifacts and links, current approval, and resulting trust. See the Swagger schemas for exact request fields and full response shapes.
