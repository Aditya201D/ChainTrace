
import argparse
import json
from urllib.parse import quote, urlparse

import requests
from web3 import Web3

from app.config import RPC_URL, CONTRACT_ADDRESS


BASE_URL = "http://127.0.0.1:8000"
MODEL_ID = "model:b752d2cb4ba34d518bd078f7d9165612"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--container-id", required=True)
    args = parser.parse_args()

    container_id = args.container_id

    if urlparse(RPC_URL).hostname not in (
        "localhost", "127.0.0.1", "::1"
    ):
        raise RuntimeError("Only local Hardhat RPC is supported.")

    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not w3.is_connected() or w3.eth.chain_id != 31337:
        raise RuntimeError("Expected local Hardhat blockchain.")

    operator = Web3.to_checksum_address(w3.eth.accounts[4])

    print("Model:", MODEL_ID)
    print("Container:", container_id)
    print("Operator:", operator)

    endpoint = f"{BASE_URL}/api/v1/blockchain/packaging"

    # Prepare packaging.
    response = requests.post(
        endpoint + "/prepare",
        json={
            "model_artifact_id": MODEL_ID,
            "container_artifact_id": container_id,
            "operator_address": operator
        },
        timeout=15
    )

    if not response.ok:
        print("Preparation failed:", response.text)

    response.raise_for_status()
    prepared = response.json()["transaction"]

    if (
        Web3.to_checksum_address(prepared["from"])
        != operator
    ):
        raise RuntimeError("Unexpected transaction sender.")

    if int(prepared["chain_id"]) != w3.eth.chain_id:
        raise RuntimeError("Chain ID mismatch.")

    if (
        Web3.to_checksum_address(prepared["to"])
        != Web3.to_checksum_address(CONTRACT_ADDRESS)
    ):
        raise RuntimeError("Unexpected contract destination.")

    print("\nPackaging transaction prepared.")

    # Submit transaction.
    tx_hash = w3.eth.send_transaction({
        "from": operator,
        "to": prepared["to"],
        "data": prepared["data"],
        "value": int(prepared["value"], 16),
        "chainId": w3.eth.chain_id
    })

    tx_hash_hex = Web3.to_hex(tx_hash)

    print("Submitted transaction:", tx_hash_hex)

    receipt = w3.eth.wait_for_transaction_receipt(
        tx_hash, timeout=30
    )

    print("Mined in block:", receipt["blockNumber"])

    if receipt["status"] != 1:
        raise RuntimeError(
            f"Packaging transaction reverted: {tx_hash_hex}"
        )

    # Confirm the ArtifactLinked event.
    response = requests.post(
        endpoint + "/confirm",
        json={
            "model_artifact_id": MODEL_ID,
            "container_artifact_id": container_id,
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

    # Read relationship from blockchain.
    model_path = quote(MODEL_ID, safe="")
    container_path = quote(container_id, safe="")

    response = requests.get(
        f"{endpoint}/{model_path}/{container_path}",
        timeout=15
    )

    response.raise_for_status()
    result = response.json()

    print("\nOn-chain packaging relationship:")
    print(json.dumps(result, indent=2))

    if not (
        result["exists"]
        and result["relationship_type"] == 2
        and result["linked_by"].lower() == operator.lower()
    ):
        raise RuntimeError(
            "Packaging provenance verification failed."
        )

    print("\nSUCCESS: Model -> ContainerImage link verified.")


if __name__ == "__main__":
    main()
