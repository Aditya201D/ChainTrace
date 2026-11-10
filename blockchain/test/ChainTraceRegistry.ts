import { expect } from "chai";
import hre from "hardhat";

const { ethers } = await hre.network.create();

describe("ChainTraceRegistry - Role Based Access", function () {
    async function deployRegistry() {
        const [admin, datasetProvider, modelDeveloper, auditor, deploymentOperator, outsider] =
            await ethers.getSigners();

        const registry = await ethers.deployContract("ChainTraceRegistry");

        await registry.waitForDeployment();

        // Assign organizational roles.
        await registry.grantRole(await registry.DATASET_PROVIDER_ROLE(), await datasetProvider.getAddress());

        await registry.grantRole(await registry.MODEL_DEVELOPER_ROLE(), await modelDeveloper.getAddress());

        await registry.grantRole(await registry.AUDITOR_ROLE(), await auditor.getAddress());

        await registry.grantRole(await registry.DEPLOYMENT_OPERATOR_ROLE(), await deploymentOperator.getAddress());

        return {
            registry,
            admin,
            datasetProvider,
            modelDeveloper,
            auditor,
            deploymentOperator,
            outsider,
        };
    }

    const datasetId = ethers.id("dataset:fraud:v1");
    const modelId = ethers.id("model:fraud:v1");
    const trainingId = ethers.id("training:fraud:v1");
    const containerId = ethers.id("container:fraud:v1");
    const deploymentId = ethers.id("deployment:fraud:v1");

    const correctHash = "0x" + "a".repeat(64);
    const wrongHash = "0x" + "b".repeat(64);
    const auditEvidenceHash = "0x" + "c".repeat(64);
    const deploymentHash = "0x" + "d".repeat(64);

    async function prepareCompleteModel() {
        const context = await deployRegistry();

        const { registry, datasetProvider, modelDeveloper } = context;

        // Register dataset.
        await registry.connect(datasetProvider).registerArtifact(datasetId, 0, correctHash);

        // Register training run.
        await registry.connect(modelDeveloper).registerArtifact(trainingId, 1, correctHash);

        // Register model.
        await registry.connect(modelDeveloper).registerArtifact(modelId, 2, correctHash);

        // Dataset -> Training Run.
        await registry.connect(modelDeveloper).linkArtifacts(datasetId, trainingId, 0);

        // Training Run -> Model.
        await registry.connect(modelDeveloper).linkArtifacts(trainingId, modelId, 1);

        return context;
    }

    // 1. Verify administrator role.

    it("Should assign administrator role to deployer", async function () {
        const { registry, admin } = await deployRegistry();

        expect(await registry.hasRole(await registry.DEFAULT_ADMIN_ROLE(), await admin.getAddress())).to.equal(true);
    });

    // 2. Dataset provider permissions.

    it("Dataset provider should register datasets", async function () {
        const { registry, datasetProvider } = await deployRegistry();

        await expect(registry.connect(datasetProvider).registerArtifact(datasetId, 0, correctHash)).to.emit(
            registry,
            "ArtifactRegistered",
        );

        const artifact = await registry.getArtifact(datasetId);

        expect(artifact.contentHash).to.equal(correctHash);

        expect(artifact.registeredBy).to.equal(await datasetProvider.getAddress());
    });

    // 3. Model developer permissions.

    it("Model developer should register training runs and models", async function () {
        const { registry, modelDeveloper } = await deployRegistry();

        await registry.connect(modelDeveloper).registerArtifact(trainingId, 1, correctHash);

        await registry.connect(modelDeveloper).registerArtifact(modelId, 2, correctHash);

        expect((await registry.getArtifact(modelId)).exists).to.equal(true);
    });

    // 4. Deployment operator permissions.

    it("Deployment operator should register container images", async function () {
        const { registry, deploymentOperator } = await deployRegistry();

        await registry.connect(deploymentOperator).registerArtifact(containerId, 3, correctHash);

        const artifact = await registry.getArtifact(containerId);

        expect(artifact.exists).to.equal(true);

        expect(Number(artifact.artifactType)).to.equal(3);
    });

    // 5. Unauthorized registration.

    it("Model developer should not register datasets", async function () {
        const { registry, modelDeveloper } = await deployRegistry();

        await expect(registry.connect(modelDeveloper).registerArtifact(datasetId, 0, correctHash))
            .to.be.revertedWithCustomError(registry, "AccessControlUnauthorizedAccount")
            .withArgs(await modelDeveloper.getAddress(), await registry.DATASET_PROVIDER_ROLE());
    });

    it("Outsider should not register any artifact", async function () {
        const { registry, outsider } = await deployRegistry();

        await expect(
            registry.connect(outsider).registerArtifact(datasetId, 0, correctHash),
        ).to.be.revertedWithCustomError(registry, "AccessControlUnauthorizedAccount");
    });

    // 6. Auditor permissions.

    it("Auditor should not register artifacts in this iteration", async function () {
        const { registry, auditor } = await deployRegistry();

        await expect(registry.connect(auditor).registerArtifact(modelId, 2, correctHash)).to.be.revertedWithCustomError(
            registry,
            "AccessControlUnauthorizedAccount",
        );
    });

    // 7. Role revocation.

    it("Administrator should be able to revoke a role", async function () {
        const { registry, admin, datasetProvider } = await deployRegistry();

        const role = await registry.DATASET_PROVIDER_ROLE();

        await registry.connect(admin).revokeRole(role, await datasetProvider.getAddress());

        expect(await registry.hasRole(role, await datasetProvider.getAddress())).to.equal(false);

        await expect(
            registry.connect(datasetProvider).registerArtifact(datasetId, 0, correctHash),
        ).to.be.revertedWithCustomError(registry, "AccessControlUnauthorizedAccount");
    });

    // 8. Duplicate registration.

    it("Should reject duplicate artifact registration", async function () {
        const { registry, datasetProvider } = await deployRegistry();

        await registry.connect(datasetProvider).registerArtifact(datasetId, 0, correctHash);

        await expect(registry.connect(datasetProvider).registerArtifact(datasetId, 0, wrongHash))
            .to.be.revertedWithCustomError(registry, "ArtifactAlreadyExists")
            .withArgs(datasetId);
    });

    // 9. Hash validation.

    it("Should reject an empty content hash", async function () {
        const { registry, datasetProvider } = await deployRegistry();

        await expect(
            registry.connect(datasetProvider).registerArtifact(datasetId, 0, ethers.ZeroHash),
        ).to.be.revertedWithCustomError(registry, "InvalidContentHash");
    });

    // 10. Hash verification.

    it("Should verify a matching hash and reject a different hash", async function () {
        const { registry, datasetProvider } = await deployRegistry();

        await registry.connect(datasetProvider).registerArtifact(datasetId, 0, correctHash);

        expect(await registry.verifyArtifact(datasetId, correctHash)).to.equal(true);

        expect(await registry.verifyArtifact(datasetId, wrongHash)).to.equal(false);
    });

    // 11. Unknown artifact.

    it("Should reject retrieval of an unknown artifact", async function () {
        const { registry } = await deployRegistry();

        await expect(registry.getArtifact(ethers.id("unknown-artifact"))).to.be.revertedWithCustomError(
            registry,
            "ArtifactNotFound",
        );
    });

    it("Only administrator should be able to grant roles", async function () {
        const { registry, outsider, datasetProvider } = await deployRegistry();

        const role = await registry.DATASET_PROVIDER_ROLE();

        await expect(registry.connect(outsider).grantRole(role, await datasetProvider.getAddress()))
            .to.be.revertedWithCustomError(registry, "AccessControlUnauthorizedAccount")
            .withArgs(await outsider.getAddress(), await registry.DEFAULT_ADMIN_ROLE());
    });

    // ================================================
    // PROVENANCE LINKING TESTS
    // ================================================

    it("Should approve a model and record its complete deployment chain", async function () {
        const { registry, auditor, deploymentOperator } = await prepareCompleteModel();

        // Auditor approves the model.
        await expect(registry.connect(auditor).approveModel(modelId, auditEvidenceHash)).to.emit(
            registry,
            "ModelApproved",
        );

        // Check approval information.
        const approval = await registry.getModelApproval(modelId);

        expect(approval.approved).to.equal(true);

        expect(approval.approvedBy).to.equal(await auditor.getAddress());

        expect(approval.evidenceHash).to.equal(auditEvidenceHash);

        // Register a container image.
        await registry.connect(deploymentOperator).registerArtifact(containerId, 3, correctHash);

        // Approved model -> Container Image.
        await registry.connect(deploymentOperator).linkArtifacts(modelId, containerId, 2);

        // Record the deployment atomically.
        await expect(
            registry.connect(deploymentOperator).recordDeployment(containerId, deploymentId, deploymentHash),
        ).to.emit(registry, "ArtifactRegistered");

        // Confirm deployment artifact registration.
        const deployment = await registry.getArtifact(deploymentId);

        expect(deployment.exists).to.equal(true);

        expect(deployment.contentHash).to.equal(deploymentHash);

        // Confirm Container Image -> Deployment relationship.
        const link = await registry.getProvenanceLink(containerId, deploymentId);

        expect(Number(link.relationshipType)).to.equal(3);

        expect(link.linkedBy).to.equal(await deploymentOperator.getAddress());
    });

    it("Should reject invalid artifact type relationships", async function () {
        const { registry, datasetProvider, modelDeveloper } = await deployRegistry();

        await registry.connect(datasetProvider).registerArtifact(datasetId, 0, correctHash);

        await registry.connect(modelDeveloper).registerArtifact(modelId, 2, correctHash);

        // Dataset -> Model is not a permitted relationship.
        await expect(
            registry.connect(modelDeveloper).linkArtifacts(datasetId, modelId, 0),
        ).to.be.revertedWithCustomError(registry, "InvalidRelationship");
    });

    it("Should reject unauthorized provenance linking", async function () {
        const { registry, datasetProvider, modelDeveloper } = await deployRegistry();

        await registry.connect(datasetProvider).registerArtifact(datasetId, 0, correctHash);

        await registry.connect(modelDeveloper).registerArtifact(trainingId, 1, correctHash);

        // Dataset Provider cannot create training relationships.
        await expect(
            registry.connect(datasetProvider).linkArtifacts(datasetId, trainingId, 0),
        ).to.be.revertedWithCustomError(registry, "AccessControlUnauthorizedAccount");
    });

    it("Should reject duplicate provenance links", async function () {
        const { registry, datasetProvider, modelDeveloper } = await deployRegistry();

        await registry.connect(datasetProvider).registerArtifact(datasetId, 0, correctHash);

        await registry.connect(modelDeveloper).registerArtifact(trainingId, 1, correctHash);

        await registry.connect(modelDeveloper).linkArtifacts(datasetId, trainingId, 0);

        await expect(registry.connect(modelDeveloper).linkArtifacts(datasetId, trainingId, 0))
            .to.be.revertedWithCustomError(registry, "ProvenanceLinkAlreadyExists")
            .withArgs(datasetId, trainingId);
    });

    it("Should reject linking an unregistered artifact", async function () {
        const { registry, datasetProvider, modelDeveloper } = await deployRegistry();

        await registry.connect(datasetProvider).registerArtifact(datasetId, 0, correctHash);

        const unknownId = ethers.id("unknown-training-run");

        await expect(registry.connect(modelDeveloper).linkArtifacts(datasetId, unknownId, 0))
            .to.be.revertedWithCustomError(registry, "ArtifactNotFound")
            .withArgs(unknownId);
    });

    it("Should reject retrieval of a nonexistent provenance link", async function () {
        const { registry, datasetProvider, modelDeveloper } = await deployRegistry();

        await registry.connect(datasetProvider).registerArtifact(datasetId, 0, correctHash);

        await registry.connect(modelDeveloper).registerArtifact(trainingId, 1, correctHash);

        await expect(registry.getProvenanceLink(datasetId, trainingId)).to.be.revertedWithCustomError(
            registry,
            "ProvenanceLinkNotFound",
        );
    });

    // ================================================
    // MODEL APPROVAL TESTS
    // ================================================

    it("Should reject approval when model provenance is incomplete", async function () {
        const { registry, modelDeveloper, auditor } = await deployRegistry();

        await registry.connect(modelDeveloper).registerArtifact(modelId, 2, correctHash);

        await expect(registry.connect(auditor).approveModel(modelId, auditEvidenceHash)).to.be.revertedWithCustomError(
            registry,
            "IncompleteModelProvenance",
        );
    });

    it("Only an auditor should be able to approve a model", async function () {
        const { registry, modelDeveloper } = await prepareCompleteModel();

        await expect(
            registry.connect(modelDeveloper).approveModel(modelId, auditEvidenceHash),
        ).to.be.revertedWithCustomError(registry, "AccessControlUnauthorizedAccount");
    });

    it("Should prevent a model developer from approving their own model", async function () {
        const { registry, modelDeveloper } = await prepareCompleteModel();

        // Give the developer an auditor role too.
        // The separate self-approval check must still reject them.
        await registry.grantRole(await registry.AUDITOR_ROLE(), await modelDeveloper.getAddress());

        await expect(
            registry.connect(modelDeveloper).approveModel(modelId, auditEvidenceHash),
        ).to.be.revertedWithCustomError(registry, "SelfApprovalNotAllowed");
    });

    it("Should reject approval without an evidence hash", async function () {
        const { registry, auditor } = await prepareCompleteModel();

        await expect(registry.connect(auditor).approveModel(modelId, ethers.ZeroHash)).to.be.revertedWithCustomError(
            registry,
            "InvalidEvidenceHash",
        );
    });

    it("Should reject duplicate active model approval", async function () {
        const { registry, auditor } = await prepareCompleteModel();

        await registry.connect(auditor).approveModel(modelId, auditEvidenceHash);

        await expect(registry.connect(auditor).approveModel(modelId, auditEvidenceHash)).to.be.revertedWithCustomError(
            registry,
            "ModelAlreadyApproved",
        );
    });

    // ================================================
    // DEPLOYMENT RESTRICTION TESTS
    // ================================================

    it("Should prevent packaging an unapproved model", async function () {
        const { registry, deploymentOperator } = await prepareCompleteModel();

        await registry.connect(deploymentOperator).registerArtifact(containerId, 3, correctHash);

        await expect(
            registry.connect(deploymentOperator).linkArtifacts(modelId, containerId, 2),
        ).to.be.revertedWithCustomError(registry, "ModelNotApproved");
    });

    it("Should prevent direct registration of deployment artifacts", async function () {
        const { registry, deploymentOperator } = await deployRegistry();

        await expect(
            registry.connect(deploymentOperator).registerArtifact(deploymentId, 4, deploymentHash),
        ).to.be.revertedWithCustomError(registry, "DeploymentMustUseRecordFunction");
    });

    it("Should reject deployment if model approval is revoked", async function () {
        const { registry, auditor, deploymentOperator } = await prepareCompleteModel();

        // Approve the model.
        await registry.connect(auditor).approveModel(modelId, auditEvidenceHash);

        // Register and package the container.
        await registry.connect(deploymentOperator).registerArtifact(containerId, 3, correctHash);

        await registry.connect(deploymentOperator).linkArtifacts(modelId, containerId, 2);

        // Revoke approval.
        await registry.connect(auditor).revokeModelApproval(modelId);

        const approval = await registry.getModelApproval(modelId);

        expect(approval.approved).to.equal(false);

        expect(approval.revokedBy).to.equal(await auditor.getAddress());

        // Deployment must now be rejected.
        await expect(
            registry.connect(deploymentOperator).recordDeployment(containerId, deploymentId, deploymentHash),
        ).to.be.revertedWithCustomError(registry, "ModelNotApproved");
    });
});
