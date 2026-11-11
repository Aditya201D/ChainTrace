
import argparse

import requests
from urllib.parse import quote, urlparse

from web3 import Web3

from app.config import RPC_URL
from app.services.blockchain import blockchain_service


API_BASE = "http://127.0.0.1:8000"


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--artifact-id",
        required=True
    )

    parser.add_argument(
        "--account-index",
        type=int,
        default=1
    )

    args = parser.parse_args()

    # This helper must never be used with a remote chain.
    hostname = urlparse(RPC_URL).hostname

    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Local Hardhat RPC required.")

    w3 = blockchain_service.w3

    if not w3.is_connected():
        raise ConnectionError("Hardhat node is unavailable.")

    accounts = w3.eth.accounts

    if args.account_index < 0 or args.account_index >= len(accounts):
        raise ValueError("Invalid local account index.")

    registrar = Web3.to_checksum_address(
        accounts[args.account_index]
    )

    encoded_id = quote(args.artifact_id, safe="")

    prepare_url = (
        f"{API_BASE}/api/v1/blockchain/artifacts/"
        f"{encoded_id}/prepare-registration"
    )

    print(f"Preparing registration for: {args.artifact_id}")
    print(f"Registrar: {registrar}")

    # Ask FastAPI to prepare and validate the transaction.
    response = requests.post(
        prepare_url,
        json={"registrar_address": registrar},
        timeout=15
    )

    response.raise_for_status()

    prepared = response.json()

    transaction = prepared["transaction"]

    # Use the locally unlocked Hardhat account to submit
    # the transaction. No private key is stored in Python.
    tx_hash = w3.eth.send_transaction({
        "from": registrar,
        "to": transaction["to"],
        "data": transaction["data"],
        "value": 0
    })

    tx_hash_hex = Web3.to_hex(tx_hash)
    print(f"Submitted transaction: {tx_hash_hex}")

    receipt = w3.eth.wait_for_transaction_receipt(
        tx_hash,
        timeout=60
    )

    if receipt["status"] != 1:
        raise RuntimeError("Blockchain transaction failed.")

    print(f"Transaction mined in block: {receipt['blockNumber']}")

    confirm_url = (
        f"{API_BASE}/api/v1/blockchain/artifacts/"
        f"{encoded_id}/confirm-registration"
    )

    # Ask FastAPI to verify the actual transaction event
    # and update the database.
    confirmation = requests.post(
        confirm_url,
        json={"tx_hash": tx_hash_hex},
        timeout=15
    )

    if not confirmation.ok:
        print("Confirmation failed!")
        print("Status:", confirmation.status_code)
        print("Response:", confirmation.text)
        confirmation.raise_for_status()

    print("\nRegistration confirmed:")
    print(confirmation.json())


if __name__ == "__main__":
    main()
