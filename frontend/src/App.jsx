import React, { useEffect, useState } from "react";
import API from "./api";
import QRCode from "qrcode";

function copy(text) {
    navigator.clipboard?.writeText(text).then(() => alert("Copied to clipboard"))
}

export default function App() {
    const [list, setList] = useState([]);
    const [name, setName] = useState("");
    const [settings, setSettings] = useState({});
    const [loading, setLoading] = useState(false);
    const [qrDataUrl, setQrDataUrl] = useState(null);
    const [qrOpen, setQrOpen] = useState(false);

    async function reload() {
        setLoading(true);
        const data = await API.list();
        setList(Array.isArray(data) ? data : []);
        setLoading(false);
    }

    async function loadSettings() {
        const s = await API.settings();
        setSettings(s);
    }

    useEffect(() => { reload(); loadSettings(); }, []);

    async function createOne() {
        if (!name.trim()) return alert("Enter a name");
        const res = await API.create(name.trim());
        if (res.error) return alert(res.error);
        setName("");
        reload();
    }

    async function remove(ps) {
        if (!confirm(`Delete ${ps}?`)) return;
        await API.deleteOne(ps);
        reload();
    }

    async function clearAll() {
        if (!confirm("Clear ALL configs? This cannot be undone.")) return;
        await API.clear();
        reload();
    }

    async function saveSettings() {
        // Only SUBSCRIPTION_URL is editable and will be saved
        const payload = { SUBSCRIPTION_URL: settings.SUBSCRIPTION_URL || "/subscription" };
        const res = await API.saveSettings(payload);
        setSettings(res);
        alert("Saved");
    }

    const subscriptionPath = () => {
        const urlPath = settings.SUBSCRIPTION_URL || "/subscription";
        const port = settings.PORT || window.location.port || (window.location.protocol === "https:" ? 443 : 80);
        const proto = window.location.protocol;
        const host = window.location.hostname;
        // show explicit port
        return `${proto}//${host}:${port}${urlPath}`;
    };

    async function showQr() {
        const link = subscriptionPath();
        try {
            const data = await QRCode.toDataURL(link);
            setQrDataUrl(data);
            setQrOpen(true);
        } catch (e) {
            alert("QR generation failed");
        }
    }

    return (
        <div className="app">
            <div className="header">
                <div className="brand">
                    <div className="logo">D1</div>
                    <div>
                        <div className="h1">D1ve</div>
                        <div className="small2">vmess manager</div>
                    </div>
                </div>
                <div className="controls">
                    <button className="btn" onClick={reload}>Refresh</button>
                    <button className="btn" onClick={clearAll}>Delete All</button>
                </div>
            </div>

            <div className="card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                        <input
                            className="input"
                            placeholder="Name (ps)"
                            value={name}
                            onKeyDown={e => {
                                if (e.key === "Enter") createOne();
                            }}
                            onChange={e => setName(e.target.value)} />
                        <button className="btn primary" onClick={createOne}>Create</button>
                    </div>
                    <div className="badge subscription-box" style={{ display: "flex", alignItems: "center" }}>
                        <a
                            href={subscriptionPath()}
                            target="_blank"
                            rel="noreferrer"
                            style={{ color: "#ffffff", textDecoration: "none", flex: 1 }}
                        >
                            Subscription
                        </a>
                        <div style={{ display: "flex", gap: 8, marginLeft: 8 }}>
                            <button
                                onClick={(e) => { e.preventDefault(); copy(subscriptionPath()) }}
                                className="copy-btn"
                            >
                                Copy
                            </button>
                            <button
                                onClick={(e) => { e.preventDefault(); showQr() }}
                                className="qr-btn"
                                title="Show QR"
                            >
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="3" width="6" height="6" stroke="currentColor" /><rect x="15" y="3" width="6" height="6" stroke="currentColor" /><rect x="3" y="15" width="6" height="6" stroke="currentColor" /><path d="M15 15h2v2h-2zM19 15h2v2h-2zM15 19h2v2h-2zM19 19h2v2h-2z" stroke="currentColor" /></svg>
                            </button>
                        </div>
                    </div>

                </div>

                <div className="list">
                    {loading ? <div className="small">Loading...</div> : null}
                    {list.length === 0 && !loading ? <div className="small2">No vmess entries</div> : null}
                    {list.map((it, idx) => (
                        <div key={idx} className="item">
                            <div className="meta">
                                <div style={{ fontWeight: 600 }}>{it.ps || "(unknown)"}</div>
                                <div className="small">{it.add}:{it.port} • id: {it.id ? it.id.slice(0, 8) : "—"}</div>
                            </div>
                            <div className="actions">
                                <button className="btn" onClick={() => copy(it._raw || JSON.stringify(it))}>Copy Link</button>
                                <button className="btn" onClick={() => copy(JSON.stringify(it))}>Copy JSON</button>
                                <button className="btn" onClick={() => remove(it.ps)}>Delete</button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                        <strong>Settings</strong>
                        <div className="small" style={{ marginTop: 6, whiteSpace: "pre-line" }}>
                            {`Only SUBSCRIPTION_URL is editable here. To change IP or PORT edit the .env and reload the container (all runtime configs will be lost).`}
                        </div>
                    </div>
                </div>

                <div className="settings" style={{ marginTop: 12 }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        <label className="small">SUBSCRIPTION_URL</label>
                        <input className="input" value={settings.SUBSCRIPTION_URL || ""} onChange={e => setSettings({ ...settings, SUBSCRIPTION_URL: e.target.value })} />
                    </div>
                     <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        <label className="small">IP</label>
                        <input className="input" value={settings.IP || ""} disabled />
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        <label className="small">HOST_PORT</label>
                        <input className="input" value={settings.HOST_PORT || ""} disabled />
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        <label className="small">VMESS_PORT</label>
                        <input className="input" value={settings.VMESS_PORT || ""} disabled />
                    </div>
                </div>
                <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
                    <button className="btn primary" onClick={saveSettings}>Save Settings</button>
                </div>
            </div>

            <div className="footer">
                <div>
                    This project provides a single-container UI + API to manage v2ray VMess configs and a subscription endpoint.<br />
                    coded by <a href="https://github.com/MohammadHuseyn/d1ve" target="_blank" rel="noreferrer">mahse1n</a>.
                </div>
            </div>
            {qrOpen && (
                <div className="modal-overlay" onClick={() => setQrOpen(false)}>
                    <div
                        className="modal"
                        onClick={(e) => e.stopPropagation()}
                        style={{ width: 400, maxWidth: "90%", padding: 24 }}
                    >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <strong>Subscription QR</strong>
                            <button className="btn" onClick={() => setQrOpen(false)}>Close</button>
                        </div>

                        <div style={{ marginTop: 24, display: "flex", justifyContent: "center" }}>
                            {qrDataUrl ? (
                                <img
                                    className="qr-img"
                                    src={qrDataUrl}
                                    alt="QR"
                                    style={{ width: 250, height: 250 }}
                                />
                            ) : (
                                <div className="small">Generating...</div>
                            )}
                        </div>

                        <div style={{ marginTop: 16, display: "flex", justifyContent: "center", gap: 8 }}>
                            <button className="btn" onClick={() => copy(subscriptionPath())}>Copy Link</button>
                            {qrDataUrl && (

                                <button
                                    className="btn"
                                    onClick={() => {
                                        const link = document.createElement("a");
                                        link.href = qrDataUrl;
                                        link.download = "subscription_qr.png";
                                        link.click();
                                    }}
                                >
                                    Download QR
                                </button>


                            )}
                        </div>
                    </div>
                </div>
            )}

        </div>
    );
}
