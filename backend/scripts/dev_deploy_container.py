"""Local-only deployment demonstration; deployment must first be uploaded as artifact type Deployment."""
import argparse
import json
from urllib.parse import quote, urlparse
import requests
from web3 import Web3
from app.config import RPC_URL, CONTRACT_ADDRESS

BASE = "http://127.0.0.1:8000/api/v1/blockchain/deployments"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--container-id", required=True)
    p.add_argument("--deployment-id", required=True)
    a = p.parse_args()
    if urlparse(RPC_URL).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError("Only local Hardhat RPC supported")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected() or w3.eth.chain_id != 31337:
        raise RuntimeError("Expected local Hardhat chain")
    operator = Web3.to_checksum_address(w3.eth.accounts[4])
    response = requests.post(BASE + "/prepare", json={
        "container_artifact_id": a.container_id,
        "deployment_artifact_id": a.deployment_id,
        "operator_address": operator
    }, timeout=20)
    if not response.ok:
        print("Preparation error:", response.text)
    response.raise_for_status()
    prepared = response.json()["transaction"]
    if Web3.to_checksum_address(prepared["from"]) != operator:
        raise RuntimeError("Unexpected sender")
    if Web3.to_checksum_address(prepared["to"]) != Web3.to_checksum_address(CONTRACT_ADDRESS):
        raise RuntimeError("Unexpected contract address")
    if int(prepared["chain_id"]) != 31337:
        raise RuntimeError("Wrong chain")
    tx_hash = w3.eth.send_transaction({
        "from": operator, "to": prepared["to"], "data": prepared["data"],
        "value": int(prepared["value"], 16), "chainId": 31337
    })
    h = Web3.to_hex(tx_hash)
    print("Submitted:", h)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=45)
    if receipt["status"] != 1:
        raise RuntimeError(f"Deployment reverted: {h}")
    response = requests.post(BASE + "/confirm", json={
        "container_artifact_id": a.container_id,
        "deployment_artifact_id": a.deployment_id, "tx_hash": h
    }, timeout=20)
    if not response.ok:
        print("Confirmation error:", response.text)
        print("Do not resubmit. Retry confirmation with tx:", h)
    response.raise_for_status()
    print("Confirmation:", json.dumps(response.json(), indent=2))
    url = BASE + "/" + quote(a.container_id, safe="") + "/" + quote(a.deployment_id, safe="")
    result = requests.get(url, timeout=20)
    result.raise_for_status()
    print("Verification:", json.dumps(result.json(), indent=2))
    if not result.json()["verified"]:
        raise RuntimeError("Deployment verification failed")
    print("SUCCESS: ContainerImage -> Deployment verified")


if __name__ == "__main__":
    main()
