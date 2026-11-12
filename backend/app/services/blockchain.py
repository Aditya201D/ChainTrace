import json

from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.exceptions import ContractLogicError

from app.config import (
    RPC_URL,
    CONTRACT_ADDRESS,
    CONTRACT_ARTIFACT_PATH
)

from web3.logs import DISCARD
from web3.exceptions import TransactionNotFound


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

    
    # ================================================
    # PREPARE ARTIFACT REGISTRATION
    # ================================================

    def prepare_artifact_registration(
        self,
        artifact_id_bytes32: str,
        artifact_type_code: int,
        content_hash_bytes32: str,
        registrar_address: str
    ) -> dict:

        if not Web3.is_address(registrar_address):
            raise ValueError("Invalid registrar address.")

        def decode_bytes32(value: str) -> bytes:

            if (
                not isinstance(value, str)
                or len(value) != 66
                or not value.startswith("0x")
            ):
                raise ValueError("Invalid bytes32 value.")

            try:
                result = bytes.fromhex(value[2:])
            except ValueError as exc:
                raise ValueError("Invalid hexadecimal value.") from exc

            if len(result) != 32:
                raise ValueError("Expected exactly 32 bytes.")

            return result

        artifact_id = decode_bytes32(artifact_id_bytes32)
        content_hash = decode_bytes32(content_hash_bytes32)

        if artifact_type_code not in range(5):
            raise ValueError("Unsupported artifact type.")

        contract = self.get_contract()

        registrar = Web3.to_checksum_address(
            registrar_address
        )

        function = contract.functions.registerArtifact(
            artifact_id,
            artifact_type_code,
            content_hash
        )

        try:

            # Simulate the transaction first.
            # This checks role permissions and contract rules
            # without changing blockchain state.
            function.call({
                "from": registrar
            })

            # Build an unsigned transaction.
            prepared = function.build_transaction({
                "from": registrar,
                "chainId": self.w3.eth.chain_id,
                "value": 0
            })

        except ContractLogicError as exc:

            raise PermissionError(
                "The smart contract rejected this registration. "
                "Check the registrar's role and artifact state."
            ) from exc

        return {
            "from": registrar,
            "to": Web3.to_checksum_address(contract.address),
            "data": prepared["data"],
            "value": "0x0",
            "chain_id": self.w3.eth.chain_id
        }


    # ================================================
    # CONFIRM ARTIFACT REGISTRATION
    # ================================================

    def confirm_artifact_registration(
        self,
        tx_hash: str,
        expected_artifact_id: str,
        expected_artifact_type: int,
        expected_content_hash: str
    ) -> dict:

        contract = self.get_contract()

        # Retrieve the transaction and its receipt.
        transaction = self.w3.eth.get_transaction(tx_hash)

        receipt = self.w3.eth.get_transaction_receipt(tx_hash)

        if receipt["status"] != 1:
            raise ValueError("Blockchain transaction failed.")

        # Make sure the transaction targeted our contract.
        if (
            transaction["to"] is None
            or Web3.to_checksum_address(transaction["to"])
            != Web3.to_checksum_address(contract.address)
        ):
            raise ValueError(
                "Transaction was not sent to the ChainTrace contract."
            )

        # Decode ArtifactRegistered events.
        events = contract.events.ArtifactRegistered().process_receipt(
            receipt,
            errors=DISCARD
        )

        # Find an event corresponding to this artifact.
        matching_events = []

        for event in events:

            args = event["args"]

            event_id = Web3.to_hex(
                args["artifactId"]
            ).lower()

            if event_id == expected_artifact_id.lower():
                matching_events.append(event)

        if len(matching_events) != 1:
            raise ValueError(
                "Expected exactly one matching ArtifactRegistered event."
            )

        args = matching_events[0]["args"]

        event_hash = Web3.to_hex(
            args["contentHash"]
        ).lower()

        event_type = int(args["artifactType"])

        registered_by = Web3.to_checksum_address(
            args["registeredBy"]
        )

        transaction_sender = Web3.to_checksum_address(
            transaction["from"]
        )

        # Validate the actual blockchain event against
        # our locally stored artifact metadata.

        if event_hash != expected_content_hash.lower():
            raise ValueError("Registered hash does not match the artifact.")

        if event_type != expected_artifact_type:
            raise ValueError("Registered artifact type does not match.")

        if registered_by != transaction_sender:
            raise ValueError("Transaction sender mismatch.")

        return {
            "transaction_hash": Web3.to_hex(
                receipt["transactionHash"]
            ),
            "block_number": int(receipt["blockNumber"]),
            "registered_by": registered_by,
            "registered_at": int(args["registeredAt"]),
            "artifact_id": Web3.to_hex(args["artifactId"]),
            "content_hash": event_hash,
            "artifact_type": event_type,
            "transaction_status": "confirmed"
        }

        # ================================================
    # PROVENANCE LINKING
    # ================================================

    @staticmethod
    def _decode_bytes32(value: str, field_name: str) -> bytes:

        if (
            not isinstance(value, str)
            or not value.startswith("0x")
            or len(value) != 66
        ):
            raise ValueError(f"Invalid {field_name}.")

        try:
            result = bytes.fromhex(value[2:])
        except ValueError as exc:
            raise ValueError(
                f"Invalid hexadecimal {field_name}."
            ) from exc

        if len(result) != 32:
            raise ValueError(f"{field_name} must be exactly 32 bytes.")

        return result


    def prepare_training_link(
        self,
        source_artifact_id: str,
        target_artifact_id: str,
        registrar_address: str,
        relationship_type: int = 0
    ) -> dict:
        
        if relationship_type not in (0, 1):
            raise ValueError("Unsupported relationship type.")

        # Validate identifiers.
        source_id = self._decode_bytes32(
            source_artifact_id,
            "source artifact ID"
        )

        target_id = self._decode_bytes32(
            target_artifact_id,
            "target artifact ID"
        )

        # Validate wallet address.
        if not Web3.is_address(registrar_address):
            raise ValueError("Invalid registrar address.")

        registrar = Web3.to_checksum_address(
            registrar_address
        )

        contract = self.get_contract()

        # RelationshipType.UsedForTraining = 0.
        function = contract.functions.linkArtifacts(
            source_id,
            target_id,
            relationship_type
        )

        try:

            # Simulate the transaction.
            # This checks the contract's validation rules
            # and the registrar's permissions.
            function.call({
                "from": registrar
            })

            # Build an unsigned transaction.
            prepared = function.build_transaction({
                "from": registrar,
                "chainId": self.w3.eth.chain_id,
                "value": 0
            })

        except ContractLogicError as exc:

            raise ValueError(
                f"Smart contract rejected the provenance link: {exc}"
            ) from exc

        return {
            "from": registrar,
            "to": Web3.to_checksum_address(contract.address),
            "data": prepared["data"],
            "value": "0x0",
            "chain_id": self.w3.eth.chain_id
        }


    def confirm_training_link(
        self,
        tx_hash: str,
        expected_source_id: str,
        expected_target_id: str,
        relationship_type: int = 0
    ) -> dict:

        if relationship_type not in (0, 1):
            raise ValueError("Unsupported relationship type.")

        contract = self.get_contract()

        source_id = self._decode_bytes32(
            expected_source_id,
            "source artifact ID"
        )

        target_id = self._decode_bytes32(
            expected_target_id,
            "target artifact ID"
        )

        # Retrieve transaction and receipt.
        transaction = self.w3.eth.get_transaction(tx_hash)

        receipt = self.w3.eth.get_transaction_receipt(tx_hash)

        if receipt["status"] != 1:
            raise ValueError("Provenance transaction failed.")

        # Ensure transaction targeted our contract.
        if (
            transaction["to"] is None
            or Web3.to_checksum_address(transaction["to"])
            != Web3.to_checksum_address(contract.address)
        ):
            raise ValueError(
                "Transaction was not sent to the ChainTrace contract."
            )

        # Decode ArtifactLinked events.
        events = contract.events.ArtifactLinked().process_receipt(
            receipt,
            errors=DISCARD
        )

        matching_events = []

        for event in events:

            args = event["args"]

            event_source = Web3.to_bytes(
                primitive=args["sourceArtifactId"]
            )

            event_target = Web3.to_bytes(
                primitive=args["targetArtifactId"]
            )

            event_relationship_type = int(args["relationshipType"])

            if (
                event_source == source_id
                and event_target == target_id
                and event_relationship_type == relationship_type
            ):
                matching_events.append(event)

        if len(matching_events) != 1:
            raise ValueError(
                "Expected exactly one matching ArtifactLinked event."
            )

        args = matching_events[0]["args"]

        linked_by = Web3.to_checksum_address(
            args["linkedBy"]
        )

        transaction_sender = Web3.to_checksum_address(
            transaction["from"]
        )

        if linked_by != transaction_sender:
            raise ValueError("Transaction sender mismatch.")

        return {
            "transaction_hash": Web3.to_hex(
                receipt["transactionHash"]
            ),
            "block_number": int(receipt["blockNumber"]),
            "source_artifact_id": Web3.to_hex(
                args["sourceArtifactId"]
            ),
            "target_artifact_id": Web3.to_hex(
                args["targetArtifactId"]
            ),
            "relationship_type": (
                "UsedForTraining" if relationship_type == 0 else "Produced"
            ),
            "linked_by": linked_by,
            "linked_at": int(args["linkedAt"]),
            "transaction_status": "confirmed"
        }


    def get_provenance_link(
        self,
        source_artifact_id: str,
        target_artifact_id: str
    ) -> dict:

        source_id = self._decode_bytes32(
            source_artifact_id,
            "source artifact ID"
        )

        target_id = self._decode_bytes32(
            target_artifact_id,
            "target artifact ID"
        )

        contract = self.get_contract()

        result = contract.functions.getProvenanceLink(
            source_id,
            target_id
        ).call()

        relationship_names = {
            0: "UsedForTraining",
            1: "Produced",
            2: "PackagedAs",
            3: "DeployedAs"
        }

        relationship_type = int(result[0])

        return {
            "source_artifact_id": source_artifact_id,
            "target_artifact_id": target_artifact_id,
            "relationship_type": relationship_type,
            "relationship_name": relationship_names.get(
                relationship_type,
                "Unknown"
            ),
            "linked_by": Web3.to_checksum_address(result[1]),
            "linked_at": int(result[2]),
            "exists": bool(result[3])
        }

    def get_outgoing_links(
        self,
        artifact_id_bytes32: str
    ) -> list[str]:

        artifact_id = self._decode_bytes32(
            artifact_id_bytes32,
            "artifact ID"
        )

        contract = self.get_contract()

        linked_ids = contract.functions.getOutgoingLinks(
            artifact_id
        ).call()

        return [
            Web3.to_hex(linked_id)
            for linked_id in linked_ids
        ]

    
    # ================================================
    # AUDITOR APPROVAL
    # ================================================

    def get_model_approval(self, model_id: str) -> dict:
        model_bytes = self._decode_bytes32(
            model_id, "model artifact ID"
        )

        result = self.get_contract().functions.getModelApproval(
            model_bytes
        ).call()

        return {
            "approved": bool(result[0]),
            "approved_by": Web3.to_checksum_address(result[1]),
            "approved_at": int(result[2]),
            "evidence_hash": Web3.to_hex(result[3]),
            "revoked_by": Web3.to_checksum_address(result[4]),
            "revoked_at": int(result[5])
        }


    def prepare_model_approval(
        self,
        model_id: str,
        evidence_hash: str,
        auditor_address: str
    ) -> dict:
        model_bytes = self._decode_bytes32(
            model_id, "model artifact ID"
        )

        evidence_bytes = self._decode_bytes32(
            evidence_hash, "evidence hash"
        )

        if evidence_bytes == bytes(32):
            raise ValueError("Evidence hash cannot be zero.")

        if not Web3.is_address(auditor_address):
            raise ValueError("Invalid auditor address.")

        auditor = Web3.to_checksum_address(auditor_address)
        contract = self.get_contract()

        function = contract.functions.approveModel(
            model_bytes,
            evidence_bytes
        )

        try:
            # Simulate before requesting a signature.
            function.call({"from": auditor})

            transaction = function.build_transaction({
                "from": auditor,
                "chainId": self.w3.eth.chain_id,
                "value": 0
            })

        except ContractLogicError as exc:
            raise ValueError(
                f"Contract rejected model approval: {exc}"
            ) from exc

        return {
            "from": auditor,
            "to": contract.address,
            "data": transaction["data"],
            "value": "0x0",
            "chain_id": self.w3.eth.chain_id
        }


    def confirm_model_approval(
        self,
        tx_hash: str,
        expected_model_id: str,
        expected_model_hash: str,
        expected_evidence_hash: str
    ) -> dict:
        model_bytes = self._decode_bytes32(
            expected_model_id, "model artifact ID"
        )
        model_hash = self._decode_bytes32(
            expected_model_hash, "model hash"
        )
        evidence_hash = self._decode_bytes32(
            expected_evidence_hash, "evidence hash"
        )

        contract = self.get_contract()

        transaction = self.w3.eth.get_transaction(tx_hash)
        receipt = self.w3.eth.get_transaction_receipt(tx_hash)

        if receipt["status"] != 1:
            raise ValueError("Approval transaction failed.")

        if (
            transaction["to"] is None
            or Web3.to_checksum_address(transaction["to"])
            != Web3.to_checksum_address(contract.address)
        ):
            raise ValueError("Incorrect contract destination.")

        events = contract.events.ModelApproved().process_receipt(
            receipt,
            errors=DISCARD
        )

        matching = []

        for event in events:
            args = event["args"]

            if (
                bytes(args["modelArtifactId"]) == model_bytes
                and bytes(args["modelHash"]) == model_hash
                and bytes(args["evidenceHash"]) == evidence_hash
                and Web3.to_checksum_address(args["approvedBy"])
                == Web3.to_checksum_address(transaction["from"])
            ):
                matching.append(event)

        if len(matching) != 1:
            raise ValueError(
                "Expected exactly one matching ModelApproved event."
            )

        args = matching[0]["args"]

        # An approval may subsequently be revoked.
        # This method confirms the historical transaction,
        # while the status endpoint reports current state.
        return {
            "transaction_hash": Web3.to_hex(
                receipt["transactionHash"]
            ),
            "block_number": int(receipt["blockNumber"]),
            "model_artifact_id": Web3.to_hex(
                args["modelArtifactId"]
            ),
            "model_hash": Web3.to_hex(args["modelHash"]),
            "evidence_hash": Web3.to_hex(args["evidenceHash"]),
            "approved_by": Web3.to_checksum_address(
                args["approvedBy"]
            ),
            "approved_at": int(args["approvedAt"]),
            "transaction_status": "confirmed"
        }


blockchain_service = BlockchainService()
