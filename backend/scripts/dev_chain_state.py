"""Snapshot current ChainTrace contract data and replay it after local Hardhat restart.

Use only with a trusted local Hardhat node and unlocked development accounts.
Snapshot captures contract application state, not the actual blocks, timestamps or transaction history.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timezone
from web3 import Web3
from web3.exceptions import ContractLogicError
from sqlalchemy import select

from app.config import RPC_URL
from app.core.database import get_db
from app.models.artifact import ArtifactRecord
from app.services.blockchain import blockchain_service
from app.services.hashing import verify_stored_file

TYPE_CODES = {"Dataset": 0, "TrainingRun": 1, "Model": 2,
              "ContainerImage": 3, "Deployment": 4}
TYPE_ACCOUNTS = {0: 1, 1: 2, 2: 2, 3: 4, 4: 4}
LINK_ACCOUNTS = {0: 2, 1: 2, 2: 4}
ROLE_ACCOUNT = {"DATASET_PROVIDER_ROLE": 1, "MODEL_DEVELOPER_ROLE": 2,
                "AUDITOR_ROLE": 3, "DEPLOYMENT_OPERATOR_ROLE": 4}


def context():
    if urlparse(RPC_URL).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError("Refusing nonlocal blockchain")
    w3 = blockchain_service.w3
    if not w3.is_connected() or w3.eth.chain_id != 31337:
        raise RuntimeError("Requires local Hardhat chain ID 31337")
    contract = blockchain_service.get_contract()
    accounts = w3.eth.accounts
    if len(accounts) < 5:
        raise RuntimeError("At least five unlocked Hardhat accounts required")
    return w3, contract, accounts


def b32(value):
    return blockchain_service._decode_bytes32(value, "bytes32")


def integrity(row):
    check = verify_stored_file(row.storage_key, row.sha256_hex)
    if not check["file_exists"] or not check["matches"]:
        raise RuntimeError(f"File integrity check failed: {row.artifact_id}")


def call_or_missing(fn):
    try:
        return fn()
    except ContractLogicError:
        return None


def registered(row):
    value = call_or_missing(lambda: blockchain_service.get_artifact(row.artifact_id_bytes32))
    if value is None:
        return False
    expected = TYPE_CODES[row.artifact_type]
    if (not value["exists"] or value["artifact_type"] != expected or
            value["content_hash"].lower() != row.content_hash_bytes32.lower()):
        raise RuntimeError(f"Conflicting on-chain artifact: {row.artifact_id}")
    return True


def link_state(src, dst):
    return call_or_missing(lambda: blockchain_service.get_provenance_link(src, dst))


def send(w3, fn, account):
    fn.call({"from": account})
    tx_hash = w3.eth.send_transaction(fn.build_transaction({
        "from": account, "chainId": w3.eth.chain_id, "value": 0
    }))
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=45)
    if receipt["status"] != 1:
        raise RuntimeError(f"Transaction reverted: {Web3.to_hex(tx_hash)}")
    return Web3.to_hex(tx_hash)


def grant_roles(w3, contract, accounts):
    admin_role = contract.functions.DEFAULT_ADMIN_ROLE().call()
    admin = next((a for a in accounts if contract.functions.hasRole(admin_role, a).call()), None)
    if not admin:
        raise RuntimeError("No unlocked admin account")
    for name, idx in ROLE_ACCOUNT.items():
        role = getattr(contract.functions, name)().call()
        target = accounts[idx]
        if not contract.functions.hasRole(role, target).call():
            send(w3, contract.functions.grantRole(role, target), admin)
            print(f"Granted {name} to account {idx}")


def snapshot(path):
    w3, contract, accounts = context()
    gen = get_db()
    db = next(gen)
    try:
        rows = db.scalars(select(ArtifactRecord)).all()
        active = []
        by_hex = {}
        for r in rows:
            if registered(r):
                integrity(r)
                active.append({"id": r.artifact_id, "bytes32": r.artifact_id_bytes32,
                               "type": r.artifact_type, "hash": r.content_hash_bytes32})
                by_hex[r.artifact_id_bytes32.lower()] = r.artifact_id
        links = []
        for item in active:
            for out in blockchain_service.get_outgoing_links(item["bytes32"]):
                source = item["id"]
                dest = by_hex.get(out.lower())
                if dest is None:
                    raise RuntimeError(f"On-chain link target missing from local DB: {out}")
                val = blockchain_service.get_provenance_link(item["bytes32"], out)
                if not val["exists"]:
                    raise RuntimeError("Inconsistent on-chain link index")
                links.append({"source": source, "target": dest,
                              "relationship_type": val["relationship_type"]})
        approvals = []
        for item in active:
            if item["type"] != "Model":
                continue
            a = blockchain_service.get_model_approval(item["bytes32"])
            if a["approved"]:
                approvals.append({"model_id": item["id"], "evidence_hash": a["evidence_hash"]})
        state = {"format_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                 "chain_id": w3.eth.chain_id, "contract_address": contract.address,
                 "artifacts": active, "links": links, "approvals": approvals}
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise RuntimeError(f"Snapshot already exists; choose another filename: {path}")
        path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {len(active)} artifacts, {len(links)} links, {len(approvals)} active approvals to {path}")
        if any(r.artifact_type == "Deployment" and not registered(r) for r in rows):
            print("NOTE: unregistered Deployment rows not included in snapshot")
    finally:
        gen.close()


def restore(path):
    if not path.is_file():
        raise RuntimeError(f"Snapshot file does not exist: {path}")
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("format_version") != 1 or state.get("chain_id") != 31337:
        raise RuntimeError("Unsupported snapshot format/chain")
    w3, contract, accounts = context()
    if Web3.to_checksum_address(state["contract_address"]) != Web3.to_checksum_address(contract.address):
        raise RuntimeError("Snapshot and configured contract address differ; verify deployment first")
    gen = get_db()
    db = next(gen)
    try:
        rows = {r.artifact_id: r for r in db.scalars(select(ArtifactRecord)).all()}
        items = state["artifacts"]
        ids = [i["id"] for i in items]
        if len(set(ids)) != len(ids):
            raise RuntimeError("Duplicate artifact IDs in snapshot")
        for item in items:
            r = rows.get(item["id"])
            if r is None or r.artifact_id_bytes32.lower() != item["bytes32"].lower() or r.artifact_type != item["type"] or r.content_hash_bytes32.lower() != item["hash"].lower():
                raise RuntimeError(f"SQLite/snapshot mismatch: {item['id']}")
            integrity(r)
        grant_roles(w3, contract, accounts)
        # Register non-deployment artifacts; deployment must be atomic.
        for item in sorted(items, key=lambda x: TYPE_CODES[x["type"]]):
            r = rows[item["id"]]
            t = TYPE_CODES[r.artifact_type]
            if t == 4:
                continue
            if not registered(r):
                tx = send(w3, contract.functions.registerArtifact(b32(r.artifact_id_bytes32), t,
                          b32(r.content_hash_bytes32)), accounts[TYPE_ACCOUNTS[t]])
                r.chain_tx_hash = tx
                print(f"Registered {r.artifact_id}")
            r.chain_registered = True
            db.commit()
        links = state["links"]
        # Reconstruct dataset->run and run->model before approval/packaging.
        for kind in (0, 1):
            for edge in [e for e in links if e["relationship_type"] == kind]:
                s, d = rows[edge["source"]], rows[edge["target"]]
                existing = link_state(s.artifact_id_bytes32, d.artifact_id_bytes32)
                if existing is None:
                    send(w3, contract.functions.linkArtifacts(b32(s.artifact_id_bytes32),
                         b32(d.artifact_id_bytes32), kind), accounts[LINK_ACCOUNTS[kind]])
                    print(f"Linked {s.artifact_id} -> {d.artifact_id} ({kind})")
                elif not existing["exists"] or existing["relationship_type"] != kind:
                    raise RuntimeError("Conflicting provenance link")
        # Restore currently active approvals, not historical revoked approvals.
        for item in state["approvals"]:
            r = rows[item["model_id"]]
            current = blockchain_service.get_model_approval(r.artifact_id_bytes32)
            if not current["approved"]:
                send(w3, contract.functions.approveModel(b32(r.artifact_id_bytes32),
                     b32(item["evidence_hash"])), accounts[3])
                print(f"Approved {r.artifact_id}")
            elif current["evidence_hash"].lower() != item["evidence_hash"].lower():
                raise RuntimeError("Conflicting existing approval")
        for edge in [e for e in links if e["relationship_type"] == 2]:
            s, d = rows[edge["source"]], rows[edge["target"]]
            existing = link_state(s.artifact_id_bytes32, d.artifact_id_bytes32)
            if existing is None:
                send(w3, contract.functions.linkArtifacts(b32(s.artifact_id_bytes32),
                     b32(d.artifact_id_bytes32), 2), accounts[4])
                print(f"Packaged {s.artifact_id} -> {d.artifact_id}")
            elif not existing["exists"] or existing["relationship_type"] != 2:
                raise RuntimeError("Conflicting packaging relationship")
        for edge in [e for e in links if e["relationship_type"] == 3]:
            c, d = rows[edge["source"]], rows[edge["target"]]
            if not registered(d):
                tx = send(w3, contract.functions.recordDeployment(b32(c.artifact_id_bytes32),
                     b32(d.artifact_id_bytes32), b32(d.content_hash_bytes32)), accounts[4])
                d.chain_tx_hash = tx
                print(f"Deployed {c.artifact_id} -> {d.artifact_id}")
            existing = link_state(c.artifact_id_bytes32, d.artifact_id_bytes32)
            if existing is None or not existing["exists"] or existing["relationship_type"] != 3:
                raise RuntimeError("Deployment link missing or incorrect")
            d.chain_registered = True
            db.commit()
        # Reconcile flags on all local rows; old registrations must not remain trusted.
        restored_ids = set(ids)
        for r in rows.values():
            if r.artifact_id not in restored_ids:
                r.chain_registered = registered(r)
                if not r.chain_registered:
                    r.chain_tx_hash = None
        db.commit()
        print("RESTORE COMPLETE: artifacts and provenance rebuilt; SQLite flags reconciled")
        print("NOTE: blocks, transaction hashes, timestamps, revoked-history and original senders are NOT preserved")
    finally:
        gen.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["snapshot", "restore"])
    parser.add_argument("--file", default="../backups/chaintrace_state.json")
    args = parser.parse_args()
    if args.action == "snapshot":
        snapshot(Path(args.file))
    else:
        restore(Path(args.file))


if __name__ == "__main__":
    main()
