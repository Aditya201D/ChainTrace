// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

contract ChainTraceRegistry {
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

    // FUNCTION TO REGISTER AN ARTIFACT
    function registerArtifact(bytes32 artifactId, ArtifactType artifactType, bytes32 contentHash) external {
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

    // FUNCTION TO GET AN ARTIFACT
    function getArtifact(bytes32 artifactId) external view returns (Artifact memory) {
        Artifact memory artifact = artifacts[artifactId];
        if (!artifact.exists) {
            revert ArtifactNotFound(artifactId);
        }

        return artifact;
    }

    // function to verify artifact with the supplied hash value
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
