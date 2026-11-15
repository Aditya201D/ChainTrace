# ChainTrace demonstration guide

## Pre-demo checklist

- Hardhat RPC running on `http://127.0.0.1:8545`; correct contract deployed and configured.
- Roles assigned or `python -m scripts.dev_chain_state restore` completed on the current chain.
- FastAPI running on `http://127.0.0.1:8000`, and `/api/v1/blockchain/status` reports an available contract.
- React/Vite running on `http://127.0.0.1:5173`.
- MetaMask configured for Hardhat Local, chain ID `31337`, with only local test wallets.
- Real ML artifacts and original stored files intact. If demonstrating a deployed chain, select an actual existing deployment ID from the Artifact Registry.

## Suggested demonstration (approx. 5–8 minutes)

### 1. Establish context

Explain that ChainTrace provides tamper-evident, role-authorized **records of model provenance and release approval**. It is not itself a model-quality certification service.

### 2. Show the registry

Open **Overview** and **Artifact Registry**. Point to the five artifact types and explain the difference between off-chain stored files and on-chain hashes. For a known registered artifact, run integrity verification.

### 3. Explain the genuine ML example

Open the real phishing model entry and its provenance graph. Show:

- Registered Dataset: `dataset:2662054ac5c641f6bce991b5100be574`
- Registered TrainingRun: `trainingrun:141e3503286941529357396081f62c22`
- Registered Model: `model:8be33ca166d2474ca1e45e3ff1094414`

Explain that `training_run_manifest.json` includes an MLflow run ID, model/dataset hashes, hyperparameters, evaluation metrics, and confusion matrix. Avoid asserting unreported metric values or an independent safety certification.

### 4. Demonstrate organization roles

Switch MetaMask from Model Developer to Auditor. Show that the on-chain roles update. Open **Transactions** and explain prepare → wallet signature → mined-event confirmation. Use a fresh unregistered test artifact if submitting a new registration, as duplicate registration is not allowed. Avoid revoking an approved model unless you intend to restore the approval before the final screenshot.

### 5. Show independent approval evidence

Open **Auditor Console** for the genuine model. Point out the evidence hash, current approval status, and role-based signing. The available local evidence is a **development-test audit**, not independent certification.

### 6. Verify a deployment

Select a previously recorded Deployment in **Verification Portal**. Inspect `lineage_complete`, `provenance_integrity_verified`, `approval_active_now`, and `trusted_for_current_policy`.

**Do not conflate the genuine phishing-model lineage with a separate metadata-only deployment test:** select the actual deployment's linked model and describe its status accurately.

## Optional negative test: tampering

Only do this if a working backup and restoration procedure are available. Back up the selected stored artifact, append arbitrary bytes to the local copy, and rerun verification. Expect local hash comparison and the overall trust policy to fail; blockchain state remains unchanged. Restore the original bytes and verify the positive result. Do not tamper with the only surviving copy of an artifact.

## Optional negative test: authorization

Try to prepare an Auditor-only approval while using the Model Developer account. The UI should prevent the action; the Solidity contract is the final enforcement mechanism. Contract-level negative tests provide stronger evidence than a disabled UI button alone.

## After the demo

```bash
# From backend/ while Hardhat is still running
python -m scripts.dev_chain_state snapshot
```

Save screenshots of: dashboard, artifact verification, provenance graph, model approval status, MetaMask role detection, and consumer verification outcome. Exclude any private keys, seed phrases, or sensitive `.env` values.

## Common troubleshooting

| Symptom | Likely cause / resolution |
|---|---|
| Backend says artifact registered but on-chain lookup fails | Restarted Hardhat; restore application state and verify the contract address |
| MetaMask transaction nonce too high | Local chain reset while MetaMask retained history; resync/reset local account activity cautiously |
| Transaction dropdown empty | Frontend may request more rows than `/api/v1/ui/artifacts` allows (`limit` max 200) |
| Approval action disabled | Ensure Auditor account active, model eligible, and evidence hash has `0x` + 64 hex digits |
| Approval revoked, deployment fails trust | Expected: current approval is part of the trust policy |
| UI shows `$0.00` | Check token balance on Hardhat Local rather than main-screen USD valuation |
