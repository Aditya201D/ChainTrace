
import json

from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.exceptions import ContractLogicError

from app.config import (
    RPC_URL,
    CONTRACT_ADDRESS,
    CONTRACT_ARTIFACT_PATH
)


class BlockchainService:

    def __init__(self):

        # Connect to the local Ethereum-compatible node.
        self.w3 = Web3(
            HTTPProvider(
                RPC_URL,
                request_kwargs={"timeout": 5}
            )
        )

        self._contract = None


    def get_status(self) -> dict:

        connected = self.w3.is_connected()

        if not connected:

            return {
                "rpc_connected": False,
                "chain_id": None,
                "latest_block": None,
                "contract_deployed": False
            }

        chain_id = self.w3.eth.chain_id
        latest_block = self.w3.eth.block_number

        contract_deployed = False

        if CONTRACT_ADDRESS:

            address = Web3.to_checksum_address(
                CONTRACT_ADDRESS
            )

            code = self.w3.eth.get_code(address)

            contract_deployed = len(code) > 0

        return {
            "rpc_connected": True,
            "chain_id": chain_id,
            "latest_block": latest_block,
            "contract_address": CONTRACT_ADDRESS or None,
            "contract_deployed": contract_deployed,
            "abi_available": CONTRACT_ARTIFACT_PATH.is_file()
        }


    def get_contract(self):

        if self._contract is not None:
            return self._contract

        if not self.w3.is_connected():
            raise ConnectionError("Blockchain RPC is unavailable.")

        if not CONTRACT_ADDRESS:
            raise RuntimeError("Contract address is not configured.")

        if not CONTRACT_ARTIFACT_PATH.is_file():
            raise FileNotFoundError(
                "Compiled contract artifact was not found."
            )

        with CONTRACT_ARTIFACT_PATH.open("r") as file:
            artifact_data = json.load(file)

        abi = artifact_data["abi"]

        address = Web3.to_checksum_address(
            CONTRACT_ADDRESS
        )

        code = self.w3.eth.get_code(address)

        if len(code) == 0:
            raise RuntimeError(
                "No contract code found at the configured address."
            )

        self._contract = self.w3.eth.contract(
            address=address,
            abi=abi
        )

        return self._contract


    def get_artifact(self, artifact_id_bytes32: str) -> dict:

        if (
            not artifact_id_bytes32.startswith("0x")
            or len(artifact_id_bytes32) != 66
        ):
            raise ValueError("Invalid bytes32 artifact ID.")

        contract = self.get_contract()

        artifact_id = Web3.to_bytes(
            hexstr=artifact_id_bytes32
        )

        result = contract.functions.getArtifact(
            artifact_id
        ).call()

        return {
            "content_hash": Web3.to_hex(result[0]),
            "artifact_type": int(result[1]),
            "registered_by": result[2],
            "registered_at": int(result[3]),
            "exists": bool(result[4])
        }


    def verify_artifact(
        self,
        artifact_id_bytes32: str,
        content_hash_bytes32: str
    ) -> bool:

        if len(artifact_id_bytes32) != 66 or not artifact_id_bytes32.startswith("0x"):
            raise ValueError("Invalid artifact ID.")

        if len(content_hash_bytes32) != 66 or not content_hash_bytes32.startswith("0x"):
            raise ValueError("Invalid content hash.")

        contract = self.get_contract()

        return contract.functions.verifyArtifact(
            Web3.to_bytes(hexstr=artifact_id_bytes32),
            Web3.to_bytes(hexstr=content_hash_bytes32)
        ).call()


blockchain_service = BlockchainService()
