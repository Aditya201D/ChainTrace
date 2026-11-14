import { useQuery } from "@tanstack/react-query";
import { ArrowRight, GitBranch } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import LineageGraph from "../components/LineageGraph";
import { Heading, Panel, Pill, State } from "../components/Ui";

export default function Lineage() {
    const [kind, setKind] = useState<"Deployment" | "Model">("Deployment");
    const [selection, setSelection] = useState("");
    const items = useQuery({ queryKey: ["artifacts", kind], queryFn: () => api.artifacts(kind) });
    const ids = useMemo(() => items.data?.items.map(a => a.artifact_id) || [], [items.data]);
    const target = ids.includes(selection) ? selection : ids[0] || "";
    const lineage = useQuery<ConsumerReport | ModelReport>({
        queryKey: ["lineage", kind, target],
        queryFn: () => (kind === "Deployment" ? api.verifyDeployment(target) : api.modelProvenance(target)),
        enabled: !!target,
        retry: false,
    });
    const report = lineage.data;
    const complete = report
        ? "deployment_id" in report
            ? report.provenance_integrity_verified
            : report.overall_verified
        : false;
    return (
        <div className="page-container">
            <Heading
                eyebrow="PROVENANCE / EXPLORER"
                title="Follow the evidence."
                desc="Trace the declared lineage of a model from its originating dataset to its final deployment."
                action={
                    <Link to="/verify" className="btn btn-secondary">
                        Verification portal <ArrowRight size={15} />
                    </Link>
                }
            />
            <Panel className="lineage-panel">
                <div className="explorer-controls">
                    <div className="explorer-left">
                        <div className="eyebrow">TRACE TARGET</div>
                        <div className="inline-controls">
                            <div className="segmented">
                                <button
                                    onClick={() => {
                                        setKind("Deployment");
                                        setSelection("");
                                    }}
                                    className={kind === "Deployment" ? "selected" : ""}
                                >
                                    Deployment
                                </button>
                                <button
                                    onClick={() => {
                                        setKind("Model");
                                        setSelection("");
                                    }}
                                    className={kind === "Model" ? "selected" : ""}
                                >
                                    Model
                                </button>
                            </div>
                            <select
                                aria-label="Select artifact"
                                className="select explorer-select"
                                value={target}
                                onChange={e => setSelection(e.target.value)}
                                disabled={!ids.length}
                            >
                                {!ids.length ? (
                                    <option value="">No {kind.toLowerCase()} artifacts</option>
                                ) : (
                                    ids.map(id => (
                                        <option value={id} key={id}>
                                            {id}
                                        </option>
                                    ))
                                )}
                            </select>
                        </div>
                    </div>
                    <div className="explorer-result">
                        <span>CHAIN INTEGRITY</span>
                        {lineage.isLoading ? (
                            <Pill label="Checking" />
                        ) : report ? (
                            <Pill
                                label={complete ? "Verified" : "Attention required"}
                                variant={complete ? "good" : "bad"}
                            />
                        ) : (
                            <Pill label="Not available" />
                        )}
                    </div>
                </div>
                {!target ? (
                    <State
                        type={items.isLoading ? "loading" : items.isError ? "error" : "empty"}
                        message={
                            items.isError
                                ? (items.error as Error).message
                                : items.isLoading
                                  ? "Loading registry…"
                                  : `No ${kind.toLowerCase()} artifacts found. Add one to the registry first.`
                        }
                    />
                ) : lineage.isLoading ? (
                    <State type="loading" message="Querying provenance graph and hashes…" />
                ) : lineage.isError ? (
                    <State type="error" message={(lineage.error as Error).message} />
                ) : report ? (
                    <LineageGraph key={target} report={report} />
                ) : null}
            </Panel>
            <div className="explorer-note">
                <GitBranch size={18} />
                <p>
                    <b>Reading the graph:</b> Lines represent relationship records on the current blockchain. Green
                    artifacts have matching local files and on-chain hashes. A valid lineage is a record of declared
                    dependencies, not cryptographic proof of the training computation itself.
                </p>
            </div>
        </div>
    );
}
