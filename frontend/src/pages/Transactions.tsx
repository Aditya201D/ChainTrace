import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ExternalLink, Fingerprint, ShieldAlert, Wallet } from "lucide-react";
import { useMemo, useState } from "react";
import { api, apiPath, idPath } from "../api";
import { Heading, Panel, Pill } from "../components/Ui";
import type { Artifact, ArtifactType } from "../types";
import { useWallet, type PreparedTx } from "../wallet/WalletContext";

type Action =
    | "register"
    | "dataset-training"
    | "training-model"
    | "model-container"
    | "deployment"
    | "approve"
    | "revoke";
const options: { value: Action; label: string; source: ArtifactType; target?: ArtifactType; role: string }[] = [
    { value: "register", label: "Register artifact", source: "Dataset", role: "Provider / Developer / Operator" },
    {
        value: "dataset-training",
        label: "Dataset → Training run",
        source: "Dataset",
        target: "TrainingRun",
        role: "Model Developer",
    },
    {
        value: "training-model",
        label: "Training run → Model",
        source: "TrainingRun",
        target: "Model",
        role: "Model Developer",
    },
    {
        value: "model-container",
        label: "Model → Container image",
        source: "Model",
        target: "ContainerImage",
        role: "Deployment Operator",
    },
    {
        value: "deployment",
        label: "Container → Deployment",
        source: "ContainerImage",
        target: "Deployment",
        role: "Deployment Operator",
    },
    { value: "approve", label: "Approve model", source: "Model", role: "Auditor" },
    { value: "revoke", label: "Revoke model approval", source: "Model", role: "Auditor" },
];

type PreparedResponse = { transaction: PreparedTx };
async function post<T>(url: string, body: object): Promise<T> {
    const response = await fetch(apiPath(url), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        const json = (await response.json().catch(() => null)) as { detail?: unknown } | null;
        throw new Error(typeof json?.detail === "string" ? json.detail : `API returned ${response.status}`);
    }
    return response.json() as Promise<T>;
}
const kindLabel: Record<ArtifactType, string> = {
    Dataset: "Dataset",
    TrainingRun: "Training run",
    Model: "Model",
    ContainerImage: "Container image",
    Deployment: "Deployment",
};

export default function Transactions() {
    const wallet = useWallet();
    const qc = useQueryClient();
    const [action, setAction] = useState<Action>("register");
    const [source, setSource] = useState("");
    const [target, setTarget] = useState("");
    const [evidence, setEvidence] = useState("");
    const [working, setWorking] = useState(false);
    const [error, setError] = useState("");
    const [result, setResult] = useState("");
    const [recoveryHash, setRecoveryHash] = useState("");
    const list = useQuery({ queryKey: ["tx-artifacts"], queryFn: () => api.artifacts("All", "", 200) });
    const cfg = options.find(o => o.value === action)!;
    const records = useMemo(() => list.data?.items ?? [], [list.data]);
    const sources = records.filter(a =>
        action === "register"
            ? a.artifact_type !== "Deployment" && !a.chain_registered
            : a.artifact_type === cfg.source,
    );
    const targets = records.filter(a => a.artifact_type === cfg.target);
    const sourceId = sources.some(a => a.artifact_id === source) ? source : sources[0]?.artifact_id || "";
    const targetId = targets.some(a => a.artifact_id === target) ? target : targets[0]?.artifact_id || "";
    const isReady = Boolean(wallet.address && wallet.chainId === 31337 && sourceId && (!cfg.target || targetId));
    const canPerform =
        action === "register"
            ? sources.find(a => a.artifact_id === sourceId)?.artifact_type === "Dataset"
                ? wallet.roles.includes("DATASET PROVIDER")
                : sources.find(a => a.artifact_id === sourceId)?.artifact_type === "ContainerImage"
                  ? wallet.roles.includes("DEPLOYMENT OPERATOR")
                  : wallet.roles.includes("MODEL DEVELOPER")
            : action === "approve" || action === "revoke"
              ? wallet.roles.includes("AUDITOR")
              : action === "model-container" || action === "deployment"
                ? wallet.roles.includes("DEPLOYMENT OPERATOR")
                : wallet.roles.includes("MODEL DEVELOPER");

    async function makeRequest(): Promise<{ url: string; confirmUrl: string; body: object; confirmBody: object }> {
        const address = wallet.address!;
        switch (action) {
            case "register":
                return {
                    url: `/api/v1/blockchain/artifacts/${idPath(sourceId)}/prepare-registration`,
                    confirmUrl: `/api/v1/blockchain/artifacts/${idPath(sourceId)}/confirm-registration`,
                    body: { registrar_address: address },
                    confirmBody: {},
                };
            case "dataset-training":
                return {
                    url: "/api/v1/blockchain/provenance/prepare-training-link",
                    confirmUrl: "/api/v1/blockchain/provenance/confirm-training-link",
                    body: { source_artifact_id: sourceId, target_artifact_id: targetId, registrar_address: address },
                    confirmBody: { source_artifact_id: sourceId, target_artifact_id: targetId },
                };
            case "training-model":
                return {
                    url: "/api/v1/blockchain/provenance/prepare-model-link",
                    confirmUrl: "/api/v1/blockchain/provenance/confirm-model-link",
                    body: { training_run_id: sourceId, model_artifact_id: targetId, registrar_address: address },
                    confirmBody: { training_run_id: sourceId, model_artifact_id: targetId },
                };
            case "model-container":
                return {
                    url: "/api/v1/blockchain/packaging/prepare",
                    confirmUrl: "/api/v1/blockchain/packaging/confirm",
                    body: { model_artifact_id: sourceId, container_artifact_id: targetId, operator_address: address },
                    confirmBody: { model_artifact_id: sourceId, container_artifact_id: targetId },
                };
            case "deployment":
                return {
                    url: "/api/v1/blockchain/deployments/prepare",
                    confirmUrl: "/api/v1/blockchain/deployments/confirm",
                    body: {
                        container_artifact_id: sourceId,
                        deployment_artifact_id: targetId,
                        operator_address: address,
                    },
                    confirmBody: { container_artifact_id: sourceId, deployment_artifact_id: targetId },
                };
            case "approve":
                return {
                    url: `/api/v1/blockchain/audit/models/${idPath(sourceId)}/prepare-approval`,
                    confirmUrl: `/api/v1/blockchain/audit/models/${idPath(sourceId)}/confirm-approval`,
                    body: { auditor_address: address, evidence_hash: evidence },
                    confirmBody: {},
                };
            case "revoke":
                return {
                    url: `/api/v1/blockchain/audit/models/${idPath(sourceId)}/prepare-revocation`,
                    confirmUrl: `/api/v1/blockchain/audit/models/${idPath(sourceId)}/confirm-revocation`,
                    body: { auditor_address: address },
                    confirmBody: {},
                };
        }
    }

    async function submit() {
        if (!isReady || !canPerform || working) return;
        setError("");
        setResult("");
        setRecoveryHash("");
        setWorking(true);
        try {
            const req = await makeRequest();
            if (action === "approve" && !/^0x[0-9a-fA-F]{64}$/.test(evidence))
                throw new Error("Provide the SHA-256 of a genuine audit evidence file, prefixed with 0x.");
            const prepared = await post<PreparedResponse>(req.url, req.body);
            // Do not continue if the user rejects MetaMask signing.
            const hash = await wallet.sendPrepared(prepared.transaction);
            setRecoveryHash(hash);
            const confirmed = await post<Record<string, unknown>>(req.confirmUrl, {
                ...req.confirmBody,
                tx_hash: hash,
            });
            setResult(`Confirmed on-chain: ${hash}\n\n${JSON.stringify(confirmed, null, 2)}`);
            await qc.invalidateQueries();
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setWorking(false);
        }
    }

    const displayed = (rows: Artifact[]) =>
        rows.map(a => (
            <option key={a.artifact_id} value={a.artifact_id}>
                {a.original_filename} · {a.artifact_id.slice(0, 24)}…
            </option>
        ));
    return (
        <div className="page-container">
            <Heading
                eyebrow="WALLET / SIGNED OPERATIONS"
                title="Transaction workspace"
                desc="Prepare actions through FastAPI, authorize them in MetaMask, and verify the mined events against ChainTrace."
                action={
                    <Pill
                        label={wallet.address ? "WALLET CONNECTED" : "CONNECT WALLET"}
                        variant={wallet.address ? "good" : "warn"}
                    />
                }
            />
            <div className="tx-layout">
                <Panel title="New transaction" sub="Each action is independently validated by the smart contract">
                    <div className="tx-form">
                        <label className="field-label" htmlFor="tx-action">
                            Operation
                        </label>
                        <select
                            id="tx-action"
                            className="select"
                            value={action}
                            onChange={e => {
                                setAction(e.target.value as Action);
                                setSource("");
                                setTarget("");
                                setError("");
                                setResult("");
                                setRecoveryHash("");
                            }}
                        >
                            {options.map(o => (
                                <option value={o.value} key={o.value}>
                                    {o.label}
                                </option>
                            ))}
                        </select>
                        <label className="field-label" htmlFor="tx-source">
                            {action === "register" ? "Artifact" : kindLabel[cfg.source]}
                        </label>
                        <select
                            id="tx-source"
                            className="select"
                            value={sourceId}
                            onChange={e => setSource(e.target.value)}
                        >
                            <option value="" disabled>
                                Select artifact
                            </option>
                            {displayed(sources)}
                        </select>
                        {cfg.target && (
                            <>
                                <label className="field-label" htmlFor="tx-target">
                                    {kindLabel[cfg.target]}
                                </label>
                                <select
                                    id="tx-target"
                                    className="select"
                                    value={targetId}
                                    onChange={e => setTarget(e.target.value)}
                                >
                                    <option value="" disabled>
                                        Select artifact
                                    </option>
                                    {displayed(targets)}
                                </select>
                            </>
                        )}
                        {list.isLoading && <p className="tx-hint">Loading artifacts...</p>}

                        {list.isError && (
                            <p className="form-error">Failed to load artifacts: {(list.error as Error).message}</p>
                        )}

                        {list.isSuccess && sources.length === 0 && (
                            <p className="tx-hint">No eligible artifacts found for this operation.</p>
                        )}
                        {action === "approve" && (
                            <>
                                <label className="field-label" htmlFor="tx-evidence">
                                    Audit evidence SHA-256 (0x + 64 hexadecimal characters)
                                </label>
                                <input
                                    id="tx-evidence"
                                    className="tx-input mono"
                                    value={evidence}
                                    onChange={e => setEvidence(e.target.value.trim())}
                                    placeholder="0x…"
                                />
                                <div className="tx-hint">
                                    Hash the final audit report file. MetaMask signs the approval; the file itself is
                                    not uploaded by this operation.
                                </div>
                            </>
                        )}
                        <div className="tx-rule">
                            <ShieldAlert size={17} />
                            <span>
                                Required role: {cfg.role}. Contract checks, not UI labels, determine authorization.
                            </span>
                        </div>
                        {!wallet.address && (
                            <button className="btn btn-secondary btn-full" onClick={() => void wallet.connect()}>
                                <Wallet size={16} /> Connect MetaMask
                            </button>
                        )}
                        {wallet.address && wallet.chainId !== 31337 && (
                            <button
                                className="btn btn-secondary btn-full"
                                onClick={() => void wallet.switchToHardhat()}
                            >
                                Switch to Hardhat Local
                            </button>
                        )}
                        <button
                            className="btn btn-primary btn-full"
                            disabled={
                                !isReady ||
                                !canPerform ||
                                working ||
                                (action === "approve" && !/^0x[0-9a-fA-F]{64}$/.test(evidence))
                            }
                            onClick={() => void submit()}
                        >
                            {working ? "Waiting for wallet / confirmation…" : "Prepare & sign"} <ArrowRight size={16} />
                        </button>
                        {wallet.address && !canPerform && (
                            <p className="form-error">
                                The connected account does not have the expected on-chain role for this action.
                            </p>
                        )}
                        {error && <p className="form-error">{error}</p>}
                        {recoveryHash && (
                            <div className="tx-hash">
                                Transaction hash: <code>{recoveryHash}</code>
                                <p>
                                    If confirmation fails, do not submit this action again. Retry the corresponding
                                    confirmation endpoint using this hash.
                                </p>
                            </div>
                        )}
                        {result && <pre className="tx-result">{result}</pre>}
                    </div>
                </Panel>
                <div className="tx-side">
                    <Panel title="Execution model" sub="Wallet-authorized, verifiable changes">
                        <div className="tx-steps">
                            <div>
                                <span>01</span>
                                <b>Prepare</b>
                                <p>FastAPI validates artifacts and builds transaction calldata.</p>
                            </div>
                            <div>
                                <span>02</span>
                                <b>Authorize</b>
                                <p>MetaMask requests approval from your connected Hardhat account.</p>
                            </div>
                            <div>
                                <span>03</span>
                                <b>Confirm</b>
                                <p>Backend verifies the transaction receipt and contract event.</p>
                            </div>
                        </div>
                    </Panel>
                    <div className="tx-note">
                        <Fingerprint size={20} />
                        <p>
                            Use dedicated Hardhat development accounts only. Never import your real wallet's seed phrase
                            into a development tool.
                        </p>
                    </div>
                    <a
                        href="https://support.metamask.io/configure/networks/how-to-add-a-custom-network-rpc/"
                        className="text-action"
                        target="_blank"
                        rel="noreferrer"
                    >
                        MetaMask network setup <ExternalLink size={14} />
                    </a>
                </div>
            </div>
        </div>
    );
}
