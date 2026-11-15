import { useQuery } from "@tanstack/react-query";
import { ArrowRight, GitBranch } from "lucide-react";
import { Component, lazy, Suspense, useMemo, useState, type ErrorInfo, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { ConsumerReport, ModelReport } from "../types";
import LineageGraph from "../components/LineageGraph";
import { Heading, Panel, Pill, State } from "../components/Ui";

const LineageGraph3D = lazy(() => import("../components/LineageGraph3D"));

interface ErrorBoundaryProps {
    fallback: (retry: () => void, error: Error | null) => ReactNode;
    children: ReactNode;
}
interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}
class Graph3DErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    state: ErrorBoundaryState = { hasError: false, error: null };
    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }
    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("Three.js 3D Graph Error:", error, errorInfo);
    }
    render() {
        if (this.state.hasError) {
            return this.props.fallback(() => this.setState({ hasError: false, error: null }), this.state.error);
        }
        return this.props.children;
    }
}

export default function Lineage() {
    const [kind, setKind] = useState<"Deployment" | "Model">("Deployment");
    const [viewMode, setViewMode] = useState<"2d" | "3d">("2d");
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
                        <div className="segmented">
                            <button
                                type="button"
                                onClick={() => setViewMode("2d")}
                                className={viewMode === "2d" ? "selected" : ""}
                            >
                                2D Graph
                            </button>
                            <button
                                type="button"
                                onClick={() => setViewMode("3d")}
                                className={viewMode === "3d" ? "selected" : ""}
                            >
                                3D Graph ✨
                            </button>
                        </div>
                        <div className="explorer-status-row">
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
                    viewMode === "3d" ? (
                        <Graph3DErrorBoundary
                            fallback={(_retry, err) => (
                                <div className="state-view state-error">
                                    <p>3D visualization error: {err?.message || "Graphics error on this device."}</p>
                                    <button
                                        type="button"
                                        className="btn btn-secondary"
                                        onClick={() => setViewMode("2d")}
                                        style={{ marginTop: 8 }}
                                    >
                                        Switch to 2D Graph
                                    </button>
                                </div>
                            )}
                        >
                            <Suspense fallback={<State type="loading" message="Initializing 3D engine and shaders…" />}>
                                <LineageGraph3D key={`${target}-3d`} report={report} />
                            </Suspense>
                        </Graph3DErrorBoundary>
                    ) : (
                        <LineageGraph key={target} report={report} />
                    )
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
