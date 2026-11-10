import { expect } from "chai";
import hre from "hardhat";

// Create a local simulated blockchain for these tests.
const { ethers } = await hre.network.create();

describe("ChainTraceRegistry", function () {
    async function deployRegistry() {
        const registry = await ethers.deployContract("ChainTraceRegistry");

        await registry.waitForDeployment();

        return registry;
    }

    // Generate a deterministic artifact identifier.
    const artifactId = ethers.id("dataset:fraud-detection:v1");

    // Simulated SHA-256 digest (32 bytes).
    const correctHash = "0x" + "a".repeat(64);

    const wrongHash = "0x" + "b".repeat(64);

    it("Should register an artifact successfully", async function () {
        const registry = await deployRegistry();

        const [registrar] = await ethers.getSigners();

        await expect(
            registry.registerArtifact(
                artifactId,
                0, // Dataset
                correctHash,
            ),
        ).to.emit(registry, "ArtifactRegistered");

        const artifact = await registry.getArtifact(artifactId);

        expect(artifact.contentHash).to.equal(correctHash);

        expect(Number(artifact.artifactType)).to.equal(0);

        expect(artifact.registeredBy).to.equal(await registrar.getAddress());

        expect(artifact.exists).to.equal(true);
    });

    it("Should verify a matching hash", async function () {
        const registry = await deployRegistry();

        await registry.registerArtifact(artifactId, 0, correctHash);

        const result = await registry.verifyArtifact(artifactId, correctHash);

        expect(result).to.equal(true);
    });

    it("Should reject a mismatching hash", async function () {
        const registry = await deployRegistry();

        await registry.registerArtifact(artifactId, 0, correctHash);

        const result = await registry.verifyArtifact(artifactId, wrongHash);

        expect(result).to.equal(false);
    });

    it("Should reject duplicate artifact registration", async function () {
        const registry = await deployRegistry();

        await registry.registerArtifact(artifactId, 0, correctHash);

        await expect(registry.registerArtifact(artifactId, 0, wrongHash))
            .to.be.revertedWithCustomError(registry, "ArtifactAlreadyExists")
            .withArgs(artifactId);
    });

    it("Should reject an artifact with an empty hash", async function () {
        const registry = await deployRegistry();

        await expect(registry.registerArtifact(artifactId, 0, ethers.ZeroHash)).to.be.revertedWithCustomError(
            registry,
            "InvalidContentHash",
        );
    });

    it("Should reject retrieval of an unknown artifact", async function () {
        const registry = await deployRegistry();

        const unknownId = ethers.id("unknown-dataset");

        await expect(registry.getArtifact(unknownId)).to.be.revertedWithCustomError(registry, "ArtifactNotFound");
    });
});
