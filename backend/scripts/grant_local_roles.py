
from urllib.parse import urlparse

from web3 import Web3

from app.config import RPC_URL
from app.services.blockchain import blockchain_service


def main():

    # SAFETY: This script is only for a local
    # Hardhat development network.
    hostname = urlparse(RPC_URL).hostname

    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError(
            "Refusing to grant development roles "
            "on a non-local RPC endpoint."
        )

    w3 = blockchain_service.w3

    if not w3.is_connected():
        raise ConnectionError("Hardhat node is not running.")

    contract = blockchain_service.get_contract()

    accounts = [
        Web3.to_checksum_address(account)
        for account in w3.eth.accounts
    ]

    if len(accounts) < 5:
        raise RuntimeError("At least five local accounts are required.")

    # Find the actual contract administrator.
    admin_role = contract.functions.DEFAULT_ADMIN_ROLE().call()

    admin = None

    for account in accounts:

        if contract.functions.hasRole(
            admin_role,
            account
        ).call():

            admin = account
            break

    if admin is None:
        raise RuntimeError(
            "No administrator account found among local Hardhat accounts."
        )

    # Assign four separate accounts to the four roles.
    available_accounts = [
        account for account in accounts
        if account.lower() != admin.lower()
    ]

    role_assignments = [
        (
            "DATASET_PROVIDER_ROLE",
            available_accounts[0]
        ),
        (
            "MODEL_DEVELOPER_ROLE",
            available_accounts[1]
        ),
        (
            "AUDITOR_ROLE",
            available_accounts[2]
        ),
        (
            "DEPLOYMENT_OPERATOR_ROLE",
            available_accounts[3]
        )
    ]

    print("\nChainTrace local role configuration")
    print("-----------------------------------")

    print(f"Chain ID: {w3.eth.chain_id}")
    print(f"Contract: {contract.address}")
    print(f"Administrator: {admin}")

    for role_name, account in role_assignments:

        role = getattr(
            contract.functions,
            role_name
        )().call()

        if contract.functions.hasRole(
            role,
            account
        ).call():

            print(f"\n{role_name}: Already assigned")
            print(f"Account: {account}")
            continue

        tx_hash = contract.functions.grantRole(
            role,
            account
        ).transact({
            "from": admin
        })

        receipt = w3.eth.wait_for_transaction_receipt(
            tx_hash
        )

        if receipt["status"] != 1:
            raise RuntimeError(
                f"Failed to grant {role_name}"
            )

        print(f"\n{role_name}: Assigned")
        print(f"Account: {account}")
        print(f"Transaction: {tx_hash.hex()}")

    print("\nAll local roles configured successfully.")


if __name__ == "__main__":
    main()
