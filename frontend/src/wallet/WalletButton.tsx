import { ChevronDown, Copy, RefreshCcw, Wallet } from "lucide-react";
import { useState } from "react";
import { useWallet } from "./WalletContext";
import Blockies from "../components/Blockies";

export default function WalletButton() {
    const wallet = useWallet();
    const [open, setOpen] = useState(false);
    const short = wallet.address ? wallet.address.slice(0, 6) + "…" + wallet.address.slice(-4) : "";
    return (
        <div className="wallet-menu-wrap">
            {!wallet.address ? (
                <button className="wallet-action" disabled={wallet.pending} onClick={() => void wallet.connect()}>
                    <Wallet size={16} />
                    {wallet.pending ? "Connecting…" : "Connect wallet"}
                </button>
            ) : (
                <button className="wallet-action wallet-connected" onClick={() => setOpen(!open)}>
                    <Blockies address={wallet.address} size={18} />
                    {short}
                    <ChevronDown size={14} />
                </button>
            )}
            {(open || wallet.error) && (
                <div className="wallet-dropdown">
                    {wallet.error && <p className="wallet-error">{wallet.error}</p>}
                    {wallet.address && (
                        <>
                            <div className="wallet-label">CONNECTED ACCOUNT</div>
                            <div className="wallet-account-header">
                                <Blockies address={wallet.address} size={26} />
                                <div className="wallet-mono">{wallet.address}</div>
                            </div>
                            <div className="wallet-label">ON-CHAIN ROLES</div>
                            <div className="wallet-roles">
                                {wallet.roles.length
                                    ? wallet.roles.map(r => <span key={r}>{r}</span>)
                                    : "No assigned roles"}
                            </div>
                            <div className="wallet-label">NETWORK</div>
                            <p className={wallet.chainId === 31337 ? "wallet-ok" : "wallet-error"}>
                                {wallet.chainId === 31337
                                    ? "Hardhat Local · 31337"
                                    : `Incorrect chain · ${wallet.chainId ?? "unknown"}`}
                            </p>
                            <button
                                className="wallet-row"
                                onClick={() => void navigator.clipboard.writeText(wallet.address!)}
                            >
                                <Copy size={14} /> Copy address
                            </button>
                            <button className="wallet-row" onClick={() => void wallet.refresh()}>
                                <RefreshCcw size={14} /> Refresh roles
                            </button>
                        </>
                    )}
                    {wallet.chainId !== 31337 && (
                        <button className="btn btn-primary btn-full" onClick={() => void wallet.switchToHardhat()}>
                            Switch to Hardhat Local
                        </button>
                    )}
                    <small className="wallet-caption">Account permissions are controlled in MetaMask.</small>
                </div>
            )}
        </div>
    );
}
