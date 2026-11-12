
import hashlib
import json
from pathlib import Path
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
        raise RuntimeError("Expected local Hardhat network.")

    auditor = w3.eth.accounts[3]

    # Create reproducible test evidence, not a genuine audit.
    evidence = {
        "model_id": MODEL_ID,
        "audit_type": "integration_test",
        "decision": "approve",
        "scope": "blockchain approval workflow only",
        "limitations": (
            "No independent evaluation of model quality, "
            "safety, fairness, or training execution."
        )
    }

    evidence_path = Path("test_audit_evidence.json")
    evidence_path.write_text(
        json.dumps(evidence, indent=2) + "\n",
        encoding="utf-8"
    )

    evidence_hash = "0x" + hashlib.sha256(
        evidence_path.read_bytes()
    ).hexdigest()

    print("Model:", MODEL_ID)
    print("Auditor:", auditor)
    print("Evidence:", evidence_path)
    print("Evidence SHA-256:", evidence_hash)

    # Prepare the approval.
    model_path = quote(MODEL_ID, safe="")
    endpoint = (
        f"{BASE_URL}/api/v1/blockchain/audit/models/"
        f"{model_path}"
    )

    response = requests.post(
        endpoint + "/prepare-approval",
        json={
            "auditor_address": auditor,
            "evidence_hash": evidence_hash
        },
        timeout=15
    )

    if not response.ok:
        print("Preparation failed:", response.text)
    response.raise_for_status()

    prepared = response.json()["transaction"]

    if Web3.to_checksum_address(prepared["from"]) != auditor:
        raise RuntimeError("Unexpected sender.")

    if int(prepared["chain_id"]) != w3.eth.chain_id:
        raise RuntimeError("Chain ID mismatch.")

    if (
        Web3.to_checksum_address(prepared["to"])
        != Web3.to_checksum_address(CONTRACT_ADDRESS)
    ):
        raise RuntimeError("Unexpected contract destination.")

    print("\nApproval transaction prepared.")

    # Submit from unlocked local Auditor account.
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
        tx_hash, timeout=30
    )

    print("Mined in block:", receipt["blockNumber"])

    if receipt["status"] != 1:
        raise RuntimeError(
            f"Approval transaction reverted: {tx_hash_hex}"
        )

    # Confirm the event and transaction.
    response = requests.post(
        endpoint + "/confirm-approval",
        json={"tx_hash": tx_hash_hex},
        timeout=15
    )

    if not response.ok:
        print("Confirmation failed:", response.text)
        print("Recovery transaction:", tx_hash_hex)
        response.raise_for_status()

    print("\nConfirmation:")
    print(json.dumps(response.json(), indent=2))

    # Read current on-chain approval status.
    response = requests.get(
        endpoint + "/status", timeout=15
    )
    response.raise_for_status()

    status = response.json()["approval"]

    print("\nCurrent approval:")
    print(json.dumps(status, indent=2))

    if not (
        status["approved"]
        and status["evidence_hash"].lower()
        == evidence_hash.lower()
        and status["approved_by"].lower() == auditor.lower()
    ):
        raise RuntimeError("Audit approval verification failed.")

    print("\nSUCCESS: Model audit approval verified.")


if __name__ == "__main__":
    main()
