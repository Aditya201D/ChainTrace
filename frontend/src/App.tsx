import { useQuery } from "@tanstack/react-query";
import {
    Activity,
    ArrowLeftRight,
    ArrowRight,
    Boxes,
    ChevronDown,
    CircleHelp,
    Database,
    Fingerprint,
    GitBranch,
    LayoutGrid,
    Menu,
    Radar,
    ShieldCheck,
    X,
} from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { Pill } from "./components/Ui";
import Artifacts from "./pages/Artifacts";
import Audits from "./pages/Audits";
import Deployments from "./pages/Deployments";
import Lineage from "./pages/Lineage";
import Overview from "./pages/Overview";
import Transactions from "./pages/Transactions";
import Verify from "./pages/Verify";
import WalletButton from "./wallet/WalletButton";

const nav = [
    { to: "/", label: "Overview", icon: LayoutGrid },
    { to: "/artifacts", label: "Artifact registry", icon: Database },
    { to: "/lineage", label: "Provenance explorer", icon: GitBranch },
    { to: "/audits", label: "Auditor console", icon: ShieldCheck },
    { to: "/deployments", label: "Deployments", icon: Boxes },
    { to: "/verify", label: "Verification portal", icon: Radar },
    { to: "/transactions", label: "Transactions", icon: ArrowLeftRight },
];

export default function App() {
    const [open, setOpen] = useState(false);
    const location = useLocation();
    const network = useQuery({ queryKey: ["chainStatus"], queryFn: api.status, refetchInterval: 20_000 });
    const online = network.data?.rpc_connected && network.data?.contract_deployed;
    const navName = nav.find(item => item.to === location.pathname)?.label || "Workspace";

    return (
        <div className="app-root">
            {open && <button className="mobile-overlay" aria-label="Close menu" onClick={() => setOpen(false)} />}
            <aside className={"sidebar " + (open ? "sidebar-open" : "")}>
                <div className="brand-area">
                    <Link to="/" className="brand-link" onClick={() => setOpen(false)}>
                        <span className="brand-logo">
                            <span></span>
                            <span></span>
                            <span></span>
                        </span>
                        <span className="brand-text">
                            <strong>
                                chaintrace<span className="brand-period">.</span>
                            </strong>
                            <small>MODEL TRUST INFRASTRUCTURE</small>
                        </span>
                    </Link>
                    <button
                        className="mobile-close icon-button"
                        onClick={() => setOpen(false)}
                        aria-label="Close navigation"
                    >
                        <X size={18} />
                    </button>
                </div>
                <div className="sidebar-label">
                    WORKSPACE <ChevronDown size={12} />
                </div>
                <nav className="nav-list" aria-label="Primary navigation">
                    {nav.map(({ to, label, icon: Icon }) => (
                        <NavLink
                            key={to}
                            end={to === "/"}
                            to={to}
                            onClick={() => setOpen(false)}
                            className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
                        >
                            <Icon size={17} strokeWidth={1.8} />
                            <span>{label}</span>
                            {to === "/verify" && <span className="nav-tiny">↗</span>}
                        </NavLink>
                    ))}
                </nav>
                <div className="sidebar-bottom">
                    <div className="sidebar-divider" />
                    <div className="workspace-help">
                        <CircleHelp size={15} />
                        <span>Development workspace</span>
                    </div>
                    <div className="node-status">
                        <div className="node-status-title">
                            <Activity size={15} /> LOCAL NETWORK
                        </div>
                        <div className="node-status-row">
                            <Pill
                                label={network.isPending ? "Checking" : online ? "Connected" : "Offline"}
                                variant={network.isPending ? "muted" : online ? "good" : "bad"}
                            />
                            <span className="mono node-chain">
                                {network.data?.chain_id ? `#${network.data.chain_id}` : "—"}
                            </span>
                        </div>
                        <div className="node-status-foot">
                            {network.data?.latest_block != null
                                ? `Latest block ${network.data.latest_block.toLocaleString()}`
                                : "Hardhat / localhost:8545"}
                        </div>
                    </div>
                </div>
            </aside>
            <div className="main-shell">
                <header className="topbar">
                    <div className="topbar-left">
                        <button
                            className="mobile-menu icon-button"
                            onClick={() => setOpen(true)}
                            aria-label="Open navigation"
                        >
                            <Menu size={19} />
                        </button>
                        <span className="topbar-crumb">Workspace</span>
                        <span className="crumb-slash">/</span>
                        <strong>{navName}</strong>
                    </div>
                    <div className="topbar-right">
                        <span className="topbar-env">
                            <span className={"live-indicator " + (online ? "" : "offline")} />
                            {online ? "HARDHAT LOCAL" : "NETWORK OFFLINE"}
                        </span>
                        <span className="topbar-sep" />
                        <WalletButton />
                    </div>
                </header>
                <div className="main-content">
                    <Routes>
                        <Route path="/" element={<Overview />} />
                        <Route path="/artifacts" element={<Artifacts />} />
                        <Route path="/lineage" element={<Lineage />} />
                        <Route path="/audits" element={<Audits />} />
                        <Route path="/deployments" element={<Deployments />} />
                        <Route path="/verify" element={<Verify />} />
                        <Route path="/transactions" element={<Transactions />} />
                        <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>
                </div>
                <footer className="app-footer">
                    <span>
                        <Fingerprint size={13} /> CHAINTRACE / LOCAL DEVELOPMENT
                    </span>
                    <span>
                        Recorded provenance ≠ proof of model safety{" "}
                        <Link to="/verify">
                            Explore verification <ArrowRight size={12} />
                        </Link>
                    </span>
                </footer>
            </div>
        </div>
    );
}
