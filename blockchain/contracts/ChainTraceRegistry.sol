
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {AccessControl} from
    "@openzeppelin/contracts/access/AccessControl.sol";

contract ChainTraceRegistry is AccessControl {

    // =================================================
    // 1. ROLES
    // =================================================

    bytes32 public constant DATASET_PROVIDER_ROLE =
        keccak256("DATASET_PROVIDER_ROLE");

    bytes32 public constant MODEL_DEVELOPER_ROLE =
        keccak256("MODEL_DEVELOPER_ROLE");

    bytes32 public constant AUDITOR_ROLE =
        keccak256("AUDITOR_ROLE");

    bytes32 public constant DEPLOYMENT_OPERATOR_ROLE =
        keccak256("DEPLOYMENT_OPERATOR_ROLE");


    // =================================================
    // 2. ARTIFACT TYPES
    // =================================================

    enum ArtifactType {
        Dataset,
        TrainingRun,
        Model,
        ContainerImage,
        Deployment
    }


    // =================================================
    // 3. RELATIONSHIP TYPES
    // =================================================

    enum RelationshipType {
        UsedForTraining,
        Produced,
        PackagedAs,
        DeployedAs
    }


    // =================================================
    // 4. DATA STRUCTURES
    // =================================================

    struct Artifact {
        bytes32 contentHash;
        ArtifactType artifactType;
        address registeredBy;
        uint256 registeredAt;
        bool exists;
    }

    struct ProvenanceLink {
        RelationshipType relationshipType;
        address linkedBy;
        uint256 linkedAt;
        bool exists;
    }


    // =================================================
    // 5. STORAGE
    // =================================================

    mapping(bytes32 => Artifact) private artifacts;

    // Stores a relationship between two artifacts.
    mapping(bytes32 => mapping(bytes32 => ProvenanceLink))
        private provenanceLinks;

    // Stores the IDs of artifacts linked from a source.
    mapping(bytes32 => bytes32[]) private outgoingLinks;


    // =================================================
    // 6. EVENTS
    // =================================================

    event ArtifactRegistered(
        bytes32 indexed artifactId,
        ArtifactType artifactType,
        bytes32 contentHash,
        address indexed registeredBy,
        uint256 registeredAt
    );

    event ArtifactLinked(
        bytes32 indexed sourceArtifactId,
        bytes32 indexed targetArtifactId,
        RelationshipType relationshipType,
        address indexed linkedBy,
        uint256 linkedAt
    );


    // =================================================
    // 7. CUSTOM ERRORS
    // =================================================

    error InvalidArtifactId();
    error InvalidContentHash();

    error ArtifactAlreadyExists(bytes32 artifactId);
    error ArtifactNotFound(bytes32 artifactId);

    error InvalidRelationship(
        ArtifactType sourceType,
        ArtifactType targetType,
        RelationshipType relationshipType
    );

    error ProvenanceLinkAlreadyExists(
        bytes32 sourceArtifactId,
        bytes32 targetArtifactId
    );

    error ProvenanceLinkNotFound(
        bytes32 sourceArtifactId,
        bytes32 targetArtifactId
    );


    // =================================================
    // 8. CONSTRUCTOR
    // =================================================

    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
    }


    // =================================================
    // 9. REGISTRATION PERMISSIONS
    // =================================================

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

            _checkRole(DEPLOYMENT_OPERATOR_ROLE);
        }
    }


    // =================================================
    // 10. LINKING PERMISSIONS
    // =================================================

    function _checkLinkPermission(
        RelationshipType relationshipType
    ) private view {

        if (
            relationshipType == RelationshipType.UsedForTraining ||
            relationshipType == RelationshipType.Produced
        ) {

            _checkRole(MODEL_DEVELOPER_ROLE);

        } else {

            _checkRole(DEPLOYMENT_OPERATOR_ROLE);
        }
    }


    // =================================================
    // 11. ARTIFACT REGISTRATION
    // =================================================

    function registerArtifact(
        bytes32 artifactId,
        ArtifactType artifactType,
        bytes32 contentHash
    ) external {

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


    // =================================================
    // 12. CREATE PROVENANCE LINK
    // =================================================

    function linkArtifacts(
        bytes32 sourceArtifactId,
        bytes32 targetArtifactId,
        RelationshipType relationshipType
    ) external {

        // Check the caller's permissions.
        _checkLinkPermission(relationshipType);

        // Validate artifact IDs.
        if (
            sourceArtifactId == bytes32(0) ||
            targetArtifactId == bytes32(0)
        ) {
            revert InvalidArtifactId();
        }

        if (sourceArtifactId == targetArtifactId) {
            revert InvalidArtifactId();
        }

        // Both artifacts must already be registered.
        if (!artifacts[sourceArtifactId].exists) {
            revert ArtifactNotFound(sourceArtifactId);
        }

        if (!artifacts[targetArtifactId].exists) {
            revert ArtifactNotFound(targetArtifactId);
        }

        ArtifactType sourceType =
            artifacts[sourceArtifactId].artifactType;

        ArtifactType targetType =
            artifacts[targetArtifactId].artifactType;

        // Validate the relationship between artifact types.
        bool validRelationship =
            (
                relationshipType == RelationshipType.UsedForTraining &&
                sourceType == ArtifactType.Dataset &&
                targetType == ArtifactType.TrainingRun
            ) ||
            (
                relationshipType == RelationshipType.Produced &&
                sourceType == ArtifactType.TrainingRun &&
                targetType == ArtifactType.Model
            ) ||
            (
                relationshipType == RelationshipType.PackagedAs &&
                sourceType == ArtifactType.Model &&
                targetType == ArtifactType.ContainerImage
            ) ||
            (
                relationshipType == RelationshipType.DeployedAs &&
                sourceType == ArtifactType.ContainerImage &&
                targetType == ArtifactType.Deployment
            );

        if (!validRelationship) {
            revert InvalidRelationship(
                sourceType,
                targetType,
                relationshipType
            );
        }

        // Prevent duplicate relationships.
        if (
            provenanceLinks[sourceArtifactId][targetArtifactId].exists
        ) {
            revert ProvenanceLinkAlreadyExists(
                sourceArtifactId,
                targetArtifactId
            );
        }

        // Store the relationship.
        provenanceLinks[sourceArtifactId][targetArtifactId] =
            ProvenanceLink({
                relationshipType: relationshipType,
                linkedBy: msg.sender,
                linkedAt: block.timestamp,
                exists: true
            });

        // Add the target to the source's outgoing links.
        outgoingLinks[sourceArtifactId].push(targetArtifactId);

        // Emit an event for off-chain indexing.
        emit ArtifactLinked(
            sourceArtifactId,
            targetArtifactId,
            relationshipType,
            msg.sender,
            block.timestamp
        );
    }


    // =================================================
    // 13. RETRIEVE ARTIFACT
    // =================================================

    function getArtifact(
        bytes32 artifactId
    ) external view returns (Artifact memory) {

        Artifact memory artifact = artifacts[artifactId];

        if (!artifact.exists) {
            revert ArtifactNotFound(artifactId);
        }

        return artifact;
    }


    // =================================================
    // 14. VERIFY ARTIFACT HASH
    // =================================================

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


    // =================================================
    // 15. RETRIEVE PROVENANCE LINK
    // =================================================

    function getProvenanceLink(
        bytes32 sourceArtifactId,
        bytes32 targetArtifactId
    ) external view returns (ProvenanceLink memory) {

        ProvenanceLink memory link =
            provenanceLinks[sourceArtifactId][targetArtifactId];

        if (!link.exists) {
            revert ProvenanceLinkNotFound(
                sourceArtifactId,
                targetArtifactId
            );
        }

        return link;
    }


    // =================================================
    // 16. RETRIEVE OUTGOING LINKS
    // =================================================

    function getOutgoingLinks(
        bytes32 artifactId
    ) external view returns (bytes32[] memory) {

        if (!artifacts[artifactId].exists) {
            revert ArtifactNotFound(artifactId);
        }

        return outgoingLinks[artifactId];
    }

}
