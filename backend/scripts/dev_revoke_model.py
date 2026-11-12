
import json
from urllib.parse import quote, urlparse

import requests
from web3 import Web3

from app.config import RPC_URL, CONTRACT_ADDRESS


BASE_URL = "http://127.0.0.1:8000"
MODEL_ID = "model:b752d2cb4ba34d518bd078f7d9165612"


def main():
    if urlparse(RPC_URL).hostname not in (
        "localhost", "127.0.0.1", "::1"
    ):
        raise RuntimeError("Only local Hardhat RPC is supported.")

    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not w3.is_connected() or w3.eth.chain_id != 31337:
        raise RuntimeError("Expected local Hardhat blockchain.")

    auditor = Web3.to_checksum_address(w3.eth.accounts[3])
    model_path = quote(MODEL_ID, safe="")

    endpoint = (
        f"{BASE_URL}/api/v1/blockchain/audit/models/"
        f"{model_path}"
    )

    # Check that the model is currently approved.
    response = requests.get(endpoint + "/status", timeout=15)
    response.raise_for_status()

    current_status = response.json()["approval"]

    if not current_status["approved"]:
        raise RuntimeError(
            "Model is not currently approved. "
            "No revocation transaction is needed."
        )

    print("Model:", MODEL_ID)
    print("Auditor:", auditor)
    print("Current approval: Active")

    # Prepare revocation.
    response = requests.post(
        endpoint + "/prepare-revocation",
        json={"auditor_address": auditor},
        timeout=15
    )

    if not response.ok:
        print("Preparation failed:", response.text)

    response.raise_for_status()

    prepared = response.json()["transaction"]

    if Web3.to_checksum_address(prepared["from"]) != auditor:
        raise RuntimeError("Unexpected transaction sender.")

    if int(prepared["chain_id"]) != w3.eth.chain_id:
        raise RuntimeError("Chain ID mismatch.")

    if (
        Web3.to_checksum_address(prepared["to"])
        != Web3.to_checksum_address(CONTRACT_ADDRESS)
    ):
        raise RuntimeError("Incorrect contract destination.")

    print("\nRevocation transaction prepared.")

    # Submit using the unlocked local Auditor account.
    tx_hash = w3.eth.send_transaction({
        "from": auditor,
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
            f"Revocation transaction reverted: {tx_hash_hex}"
        )

    # Confirm transaction and event through FastAPI.
    response = requests.post(
        endpoint + "/confirm-revocation",
        json={"tx_hash": tx_hash_hex},
        timeout=15
    )

    if not response.ok:
        print("Confirmation failed:", response.text)
        print("Recovery transaction:", tx_hash_hex)

    response.raise_for_status()

    print("\nConfirmation:")
    print(json.dumps(response.json(), indent=2))

    # Read current approval state.
    response = requests.get(endpoint + "/status", timeout=15)
    response.raise_for_status()

    status = response.json()["approval"]

    print("\nCurrent approval:")
    print(json.dumps(status, indent=2))

    if not (
        status["approved"] is False
        and status["revoked_by"].lower() == auditor.lower()
        and status["revoked_at"] > 0
    ):
        raise RuntimeError("Revocation verification failed.")

    print("\nSUCCESS: Model approval revoked and verified.")


if __name__ == "__main__":
    main()
