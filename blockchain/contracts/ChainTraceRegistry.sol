// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {AccessControl} from
    "@openzeppelin/contracts/access/AccessControl.sol";

contract ChainTraceRegistry is AccessControl {

    bytes32 public constant DATASET_PROVIDER_ROLE =
        keccak256("DATASET_PROVIDER_ROLE");

    bytes32 public constant MODEL_DEVELOPER_ROLE =
        keccak256("MODEL_DEVELOPER_ROLE");

    bytes32 public constant AUDITOR_ROLE =
        keccak256("AUDITOR_ROLE");

    bytes32 public constant DEPLOYMENT_OPERATOR_ROLE =
        keccak256("DEPLOYMENT_OPERATOR_ROLE");

    enum ArtifactType {
        Dataset,
        TrainingRun,
        Model,
        ContainerImage,
        Deployment
    }

    struct Artifact {
        bytes32 contentHash;
        ArtifactType artifactType;
        address registeredBy;
        uint256 registeredAt;
        bool exists;
    }

    mapping(bytes32 => Artifact) private artifacts;

    event ArtifactRegistered(
        bytes32 indexed artifactId,
        ArtifactType artifactType,
        bytes32 contentHash,
        address indexed registeredBy,
        uint256 registeredAt
    );

    error InvalidArtifactId();
    error InvalidContentHash();

    error ArtifactAlreadyExists(bytes32 artifactId);
    error ArtifactNotFound(bytes32 artifactId);

    constructor() {
        // The deploying address becomes the administrator.
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
    }

    function _checkRegistrationPermission(
        ArtifactType artifactType
    ) private view {

        if (artifactType == ArtifactType.Dataset) {

            _checkRole(DATASET_PROVIDER_ROLE);

        } else if (
            artifactType == ArtifactType.TrainingRun ||
            artifactType == ArtifactType.Model
        ) {

            _checkRole(MODEL_DEVELOPER_ROLE);

        } else {

            // ContainerImage and Deployment
            _checkRole(DEPLOYMENT_OPERATOR_ROLE);
        }
    }

    function registerArtifact(
        bytes32 artifactId,
        ArtifactType artifactType,
        bytes32 contentHash
    ) external {

        // Check whether the caller has the required role.
        _checkRegistrationPermission(artifactType);

        if (artifactId == bytes32(0)) {
            revert InvalidArtifactId();
        }

        if (contentHash == bytes32(0)) {
            revert InvalidContentHash();
        }

        if (artifacts[artifactId].exists) {
            revert ArtifactAlreadyExists(artifactId);
        }

        artifacts[artifactId] = Artifact({
            contentHash: contentHash,
            artifactType: artifactType,
            registeredBy: msg.sender,
            registeredAt: block.timestamp,
            exists: true
        });

        emit ArtifactRegistered(
            artifactId,
            artifactType,
            contentHash,
            msg.sender,
            block.timestamp
        );
    }

    function getArtifact(
        bytes32 artifactId
    ) external view returns (Artifact memory) {

        Artifact memory artifact = artifacts[artifactId];

        if (!artifact.exists) {
            revert ArtifactNotFound(artifactId);
        }

        return artifact;
    }

    function verifyArtifact(
        bytes32 artifactId,
        bytes32 suppliedHash
    ) external view returns (bool) {

        Artifact memory artifact = artifacts[artifactId];

        if (!artifact.exists) {
            revert ArtifactNotFound(artifactId);
        }

        return artifact.contentHash == suppliedHash;
    }

}
