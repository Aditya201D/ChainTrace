
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
    // 2. ENUMS
    // =================================================

    enum ArtifactType {
        Dataset,
        TrainingRun,
        Model,
        ContainerImage,
        Deployment
    }

    enum RelationshipType {
        UsedForTraining,
        Produced,
        PackagedAs,
        DeployedAs
    }


    // =================================================
    // 3. STRUCTURES
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

    struct ModelApproval {
        bool approved;
        address approvedBy;
        uint256 approvedAt;
        bytes32 evidenceHash;
        address revokedBy;
        uint256 revokedAt;
    }


    // =================================================
    // 4. STORAGE
    // =================================================

    mapping(bytes32 => Artifact) private artifacts;

    mapping(bytes32 => mapping(bytes32 => ProvenanceLink))
        private provenanceLinks;

    mapping(bytes32 => bytes32[]) private outgoingLinks;

    // Whether a training run has at least one dataset.
    mapping(bytes32 => bool) private trainingRunHasDataset;

    // The training run associated with each model.
    mapping(bytes32 => bytes32) private modelTrainingRun;

    // The model packaged into each container image.
    mapping(bytes32 => bytes32) private containerModel;

    // Current approval state of each model.
    mapping(bytes32 => ModelApproval) private modelApprovals;

    mapping(bytes32 => bool) private trainingRunHasModel;


    // =================================================
    // 5. EVENTS
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

    event ModelApproved(
        bytes32 indexed modelArtifactId,
        bytes32 indexed modelHash,
        address indexed approvedBy,
        bytes32 evidenceHash,
        uint256 approvedAt
    );

    event ModelApprovalRevoked(
        bytes32 indexed modelArtifactId,
        address indexed revokedBy,
        uint256 revokedAt
    );


    // =================================================
    // 6. CUSTOM ERRORS
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

    error ModelAlreadyLinkedToTrainingRun(bytes32 modelArtifactId);
    error IncompleteModelProvenance(bytes32 modelArtifactId);

    error InvalidModelArtifact(bytes32 artifactId);
    error SelfApprovalNotAllowed();
    error InvalidEvidenceHash();

    error ModelAlreadyApproved(bytes32 modelArtifactId);
    error ModelNotApproved(bytes32 modelArtifactId);

    error ContainerAlreadyLinkedToModel(bytes32 containerId);
    error ContainerNotLinkedToModel(bytes32 containerId);

    error DeploymentMustUseRecordFunction();

    error TrainingRunProvenanceFinalized(bytes32 trainingRunId);


    // =================================================
    // 7. CONSTRUCTOR
    // =================================================

    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
    }


    // =================================================
    // 8. PERMISSION HELPERS
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
    // 9. REGISTER ARTIFACT
    // =================================================

    function registerArtifact(
        bytes32 artifactId,
        ArtifactType artifactType,
        bytes32 contentHash
    ) external {

        _checkRegistrationPermission(artifactType);

        // Deployments must be registered through
        // recordDeployment(), which checks model approval.
        if (artifactType == ArtifactType.Deployment) {
            revert DeploymentMustUseRecordFunction();
        }

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
    // 10. CREATE PROVENANCE LINKS
    // =================================================

    function linkArtifacts(
        bytes32 sourceArtifactId,
        bytes32 targetArtifactId,
        RelationshipType relationshipType
    ) external {

        _checkLinkPermission(relationshipType);

        // Deployment links must be created atomically
        // through recordDeployment().
        if (relationshipType == RelationshipType.DeployedAs) {
            revert DeploymentMustUseRecordFunction();
        }

        // Once a training run has produced a model,
        // its dataset lineage cannot be changed.
        if (
            relationshipType == RelationshipType.UsedForTraining &&
            trainingRunHasModel[targetArtifactId]
        ) {
            revert TrainingRunProvenanceFinalized(targetArtifactId);
        }

        if (
            sourceArtifactId == bytes32(0) ||
            targetArtifactId == bytes32(0) ||
            sourceArtifactId == targetArtifactId
        ) {
            revert InvalidArtifactId();
        }

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
            );

        if (!validRelationship) {
            revert InvalidRelationship(
                sourceType,
                targetType,
                relationshipType
            );
        }

        if (
            provenanceLinks[sourceArtifactId][targetArtifactId].exists
        ) {
            revert ProvenanceLinkAlreadyExists(
                sourceArtifactId,
                targetArtifactId
            );
        }

        // A training run must have at least one dataset.
        if (
            relationshipType == RelationshipType.Produced &&
            !trainingRunHasDataset[sourceArtifactId]
        ) {
            revert IncompleteModelProvenance(targetArtifactId);
        }

        // A model can have only one producing training run.
        if (
            relationshipType == RelationshipType.Produced &&
            modelTrainingRun[targetArtifactId] != bytes32(0)
        ) {
            revert ModelAlreadyLinkedToTrainingRun(targetArtifactId);
        }

        // A model must be approved before packaging.
        if (relationshipType == RelationshipType.PackagedAs) {

            if (!modelApprovals[sourceArtifactId].approved) {
                revert ModelNotApproved(sourceArtifactId);
            }

            // One container image represents one model
            // in this prototype.
            if (containerModel[targetArtifactId] != bytes32(0)) {
                revert ContainerAlreadyLinkedToModel(targetArtifactId);
            }
        }

        provenanceLinks[sourceArtifactId][targetArtifactId] =
            ProvenanceLink({
                relationshipType: relationshipType,
                linkedBy: msg.sender,
                linkedAt: block.timestamp,
                exists: true
            });

        outgoingLinks[sourceArtifactId].push(targetArtifactId);

        // Maintain indexes for workflow validation.
        if (relationshipType == RelationshipType.UsedForTraining) {
            trainingRunHasDataset[targetArtifactId] = true;
        }

        if (relationshipType == RelationshipType.Produced) {
            modelTrainingRun[targetArtifactId] = sourceArtifactId;
            trainingRunHasModel[sourceArtifactId] = true;
        }

        if (relationshipType == RelationshipType.PackagedAs) {
            containerModel[targetArtifactId] = sourceArtifactId;
        }

        emit ArtifactLinked(
            sourceArtifactId,
            targetArtifactId,
            relationshipType,
            msg.sender,
            block.timestamp
        );
    }


    // =================================================
    // 11. APPROVE MODEL
    // =================================================

    function approveModel(
        bytes32 modelArtifactId,
        bytes32 evidenceHash
    ) external {

        _checkRole(AUDITOR_ROLE);

        Artifact storage model = artifacts[modelArtifactId];

        if (
            !model.exists ||
            model.artifactType != ArtifactType.Model
        ) {
            revert InvalidModelArtifact(modelArtifactId);
        }

        // Require a dataset -> training run -> model chain.
        if (modelTrainingRun[modelArtifactId] == bytes32(0)) {
            revert IncompleteModelProvenance(modelArtifactId);
        }

        if (
            !trainingRunHasDataset[
                modelTrainingRun[modelArtifactId]
            ]
        ) {
            revert IncompleteModelProvenance(modelArtifactId);
        }

        // The model creator cannot approve their own model.
        if (model.registeredBy == msg.sender) {
            revert SelfApprovalNotAllowed();
        }

        if (evidenceHash == bytes32(0)) {
            revert InvalidEvidenceHash();
        }

        ModelApproval storage approval =
            modelApprovals[modelArtifactId];

        if (approval.approved) {
            revert ModelAlreadyApproved(modelArtifactId);
        }

        approval.approved = true;
        approval.approvedBy = msg.sender;
        approval.approvedAt = block.timestamp;
        approval.evidenceHash = evidenceHash;
        approval.revokedBy = address(0);
        approval.revokedAt = 0;

        emit ModelApproved(
            modelArtifactId,
            model.contentHash,
            msg.sender,
            evidenceHash,
            block.timestamp
        );
    }


    // =================================================
    // 12. REVOKE MODEL APPROVAL
    // =================================================

    function revokeModelApproval(
        bytes32 modelArtifactId
    ) external {

        _checkRole(AUDITOR_ROLE);

        ModelApproval storage approval =
            modelApprovals[modelArtifactId];

        if (!approval.approved) {
            revert ModelNotApproved(modelArtifactId);
        }

        approval.approved = false;
        approval.revokedBy = msg.sender;
        approval.revokedAt = block.timestamp;

        emit ModelApprovalRevoked(
            modelArtifactId,
            msg.sender,
            block.timestamp
        );
    }


    // =================================================
    // 13. RECORD DEPLOYMENT
    // =================================================

    function recordDeployment(
        bytes32 containerImageId,
        bytes32 deploymentArtifactId,
        bytes32 deploymentHash
    ) external {

        _checkRole(DEPLOYMENT_OPERATOR_ROLE);

        if (
            containerImageId == bytes32(0) ||
            deploymentArtifactId == bytes32(0)
        ) {
            revert InvalidArtifactId();
        }

        if (deploymentHash == bytes32(0)) {
            revert InvalidContentHash();
        }

        Artifact memory container =
            artifacts[containerImageId];

        if (!container.exists) {
            revert ArtifactNotFound(containerImageId);
        }

        if (container.artifactType != ArtifactType.ContainerImage) {
            revert InvalidRelationship(
                container.artifactType,
                ArtifactType.Deployment,
                RelationshipType.DeployedAs
            );
        }

        // Retrieve the model associated with this container.
        bytes32 modelArtifactId = containerModel[containerImageId];

        if (modelArtifactId == bytes32(0)) {
            revert ContainerNotLinkedToModel(containerImageId);
        }

        // The model must still have active approval.
        if (!modelApprovals[modelArtifactId].approved) {
            revert ModelNotApproved(modelArtifactId);
        }

        if (artifacts[deploymentArtifactId].exists) {
            revert ArtifactAlreadyExists(deploymentArtifactId);
        }

        // Create the deployment artifact.
        artifacts[deploymentArtifactId] = Artifact({
            contentHash: deploymentHash,
            artifactType: ArtifactType.Deployment,
            registeredBy: msg.sender,
            registeredAt: block.timestamp,
            exists: true
        });

        // Create ContainerImage -> Deployment relationship.
        provenanceLinks[containerImageId][deploymentArtifactId] =
            ProvenanceLink({
                relationshipType: RelationshipType.DeployedAs,
                linkedBy: msg.sender,
                linkedAt: block.timestamp,
                exists: true
            });

        outgoingLinks[containerImageId].push(deploymentArtifactId);

        emit ArtifactRegistered(
            deploymentArtifactId,
            ArtifactType.Deployment,
            deploymentHash,
            msg.sender,
            block.timestamp
        );

        emit ArtifactLinked(
            containerImageId,
            deploymentArtifactId,
            RelationshipType.DeployedAs,
            msg.sender,
            block.timestamp
        );
    }


    // =================================================
    // 14. READ FUNCTIONS
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


    function getOutgoingLinks(
        bytes32 artifactId
    ) external view returns (bytes32[] memory) {

        if (!artifacts[artifactId].exists) {
            revert ArtifactNotFound(artifactId);
        }

        return outgoingLinks[artifactId];
    }


    function getModelApproval(
        bytes32 modelArtifactId
    ) external view returns (ModelApproval memory) {

        Artifact memory model = artifacts[modelArtifactId];

        if (
            !model.exists ||
            model.artifactType != ArtifactType.Model
        ) {
            revert InvalidModelArtifact(modelArtifactId);
        }

        return modelApprovals[modelArtifactId];
    }

}
