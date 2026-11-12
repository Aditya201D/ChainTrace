
import argparse
import json
import requests

from urllib.parse import quote
from web3 import Web3

from app.config import RPC_URL


BASE_URL = "http://127.0.0.1:8000"

TRAINING_ID = (
    "trainingrun:cc433ecd87ec4c67be605d7e134ebb83"
)

ACCOUNT_INDEX = 2


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dataset-id",
        required=True,
        help="Human-readable dataset artifact ID"
    )

    args = parser.parse_args()

    dataset_id = args.dataset_id

    # Connect to the local Hardhat blockchain.
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not w3.is_connected():
        raise RuntimeError("Hardhat RPC is unavailable.")

    if w3.eth.chain_id != 31337:
        raise RuntimeError(
            "This development script only supports "
            "the local Hardhat chain (31337)."
        )

    registrar = w3.eth.accounts[ACCOUNT_INDEX]

    print("Dataset:", dataset_id)
    print("TrainingRun:", TRAINING_ID)
    print("Registrar:", registrar)

    # Step 1: Prepare the provenance transaction.
    prepare_response = requests.post(
        f"{BASE_URL}/api/v1/blockchain/provenance/"
        "prepare-training-link",
        json={
            "source_artifact_id": dataset_id,
            "target_artifact_id": TRAINING_ID,
            "registrar_address": registrar
        },
        timeout=15
    )

    prepare_response.raise_for_status()

    prepared = prepare_response.json()["transaction"]

    if Web3.to_checksum_address(prepared["from"]) != registrar:
        raise RuntimeError("Unexpected transaction sender.")

    if int(prepared["chain_id"]) != w3.eth.chain_id:
        raise RuntimeError("Transaction chain ID mismatch.")

    print("\nProvenance transaction prepared.")

    # Step 2: Submit using an unlocked Hardhat account.
    transaction = {
        "from": registrar,
        "to": prepared["to"],
        "data": prepared["data"],
        "value": int(prepared["value"], 16),
        "chainId": w3.eth.chain_id
    }

    tx_hash = w3.eth.send_transaction(transaction)
    tx_hash_hex = Web3.to_hex(tx_hash)

    print("Submitted transaction:", tx_hash_hex)

    # Step 3: Wait for mining.
    receipt = w3.eth.wait_for_transaction_receipt(
        tx_hash,
        timeout=30
    )

    print("Transaction mined in block:", receipt["blockNumber"])

    if receipt["status"] != 1:
        raise RuntimeError(
            f"Provenance transaction reverted: {tx_hash_hex}"
        )

    # Step 4: Confirm through FastAPI.
    confirm_response = requests.post(
        f"{BASE_URL}/api/v1/blockchain/provenance/"
        "confirm-training-link",
        json={
            "source_artifact_id": dataset_id,
            "target_artifact_id": TRAINING_ID,
            "tx_hash": tx_hash_hex
        },
        timeout=15
    )

    if not confirm_response.ok:
        print("Confirmation failed:", confirm_response.text)
        print("Transaction hash for recovery:", tx_hash_hex)
        confirm_response.raise_for_status()

    print("\nConfirmation result:")
    print(json.dumps(confirm_response.json(), indent=2))

    # Step 5: Read the relationship from the blockchain.
    encoded_dataset = quote(dataset_id, safe="")
    encoded_training = quote(TRAINING_ID, safe="")

    link_url = (
        f"{BASE_URL}/api/v1/blockchain/provenance/"
        f"{encoded_dataset}/{encoded_training}"
    )

    link_response = requests.get(link_url, timeout=15)
    link_response.raise_for_status()

    result = link_response.json()

    print("\nOn-chain provenance:")
    print(json.dumps(result, indent=2))

    if not (
        result["exists"]
        and result["relationship_type"] == 0
        and result["linked_by"].lower() == registrar.lower()
    ):
        raise RuntimeError("Provenance verification failed.")

    print("\nSUCCESS: Dataset -> TrainingRun link verified.")


if __name__ == "__main__":
    main()
