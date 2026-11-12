
import argparse
import json
import requests

from urllib.parse import quote
from urllib.parse import urlparse
from web3 import Web3

from app.config import RPC_URL


BASE_URL = "http://127.0.0.1:8000"

TRAINING_RUN_ID = (
    "trainingrun:cc433ecd87ec4c67be605d7e134ebb83"
)

MODEL_ID = (
    "model:b752d2cb4ba34d518bd078f7d9165612"
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-index", type=int, default=2)
    args = parser.parse_args()

    parsed = urlparse(RPC_URL)

    if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError("This script requires a local RPC endpoint.")

    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not w3.is_connected() or w3.eth.chain_id != 31337:
        raise RuntimeError("Expected local Hardhat blockchain.")

    registrar = w3.eth.accounts[args.account_index]

    print("TrainingRun:", TRAINING_RUN_ID)
    print("Model:", MODEL_ID)
    print("Registrar:", registrar)

    # Prepare transaction.
    response = requests.post(
        f"{BASE_URL}/api/v1/blockchain/provenance/"
        "prepare-model-link",
        json={
            "training_run_id": TRAINING_RUN_ID,
            "model_artifact_id": MODEL_ID,
            "registrar_address": registrar
        },
        timeout=15
    )

    if not response.ok:
        print("Preparation failed:", response.text)
    response.raise_for_status()

    prepared = response.json()["transaction"]

    if Web3.to_checksum_address(prepared["from"]) != registrar:
        raise RuntimeError("Unexpected transaction sender.")

    if int(prepared["chain_id"]) != w3.eth.chain_id:
        raise RuntimeError("Transaction chain ID mismatch.")

    # Check the destination is the configured contract.
    from app.config import CONTRACT_ADDRESS

    if Web3.to_checksum_address(prepared["to"]) != Web3.to_checksum_address(
        CONTRACT_ADDRESS
    ):
        raise RuntimeError("Unexpected contract destination.")

    print("\nTransaction prepared.")

    # Submit with unlocked Hardhat account.
    tx_hash = w3.eth.send_transaction({
        "from": registrar,
        "to": prepared["to"],
        "data": prepared["data"],
        "value": int(prepared["value"], 16),
        "chainId": w3.eth.chain_id
    })

    tx_hash_hex = Web3.to_hex(tx_hash)

    print("Submitted transaction:", tx_hash_hex)

    receipt = w3.eth.wait_for_transaction_receipt(
        tx_hash,
        timeout=30
    )

    print("Mined in block:", receipt["blockNumber"])

    if receipt["status"] != 1:
        raise RuntimeError(
            f"Transaction reverted: {tx_hash_hex}"
        )

    # Confirm through backend.
    response = requests.post(
        f"{BASE_URL}/api/v1/blockchain/provenance/"
        "confirm-model-link",
        json={
            "training_run_id": TRAINING_RUN_ID,
            "model_artifact_id": MODEL_ID,
            "tx_hash": tx_hash_hex
        },
        timeout=15
    )

    if not response.ok:
        print("Confirmation failed:", response.text)
        print("Recovery transaction:", tx_hash_hex)
    response.raise_for_status()

    print("\nConfirmation:")
    print(json.dumps(response.json(), indent=2))

    # Retrieve actual on-chain relationship.
    source = quote(TRAINING_RUN_ID, safe="")
    target = quote(MODEL_ID, safe="")

    response = requests.get(
        f"{BASE_URL}/api/v1/blockchain/provenance/"
        f"model/{source}/{target}",
        timeout=15
    )

    response.raise_for_status()
    result = response.json()

    print("\nOn-chain relationship:")
    print(json.dumps(result, indent=2))

    if not (
        result["exists"]
        and result["relationship_type"] == 1
        and result["linked_by"].lower() == registrar.lower()
    ):
        raise RuntimeError("Model provenance verification failed.")

    print("\nSUCCESS: TrainingRun -> Model provenance verified.")


if __name__ == "__main__":
    main()
