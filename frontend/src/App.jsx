import React, {useEffect, useState} from "react";
import API from "./api";

function copy(text){
  navigator.clipboard?.writeText(text);
}

export default function App(){
  const [list, setList] = useState([]);
  const [name, setName] = useState("");
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(false);

  async function reload(){
    setLoading(true);
    const data = await API.list();
    setList(Array.isArray(data)?data:[]);
    setLoading(false);
  }

  async function loadSettings(){
    const s = await API.settings();
    setSettings(s);
  }

  useEffect(()=>{ reload(); loadSettings(); }, []);

  async function createOne(){
    if(!name.trim()) return alert("Enter a name");
    const res = await API.create(name.trim());
    if(res.error) return alert(res.error);
    setName("");
    reload();
  }

  async function remove(ps){
    if(!confirm(`Delete ${ps}?`)) return;
    await API.deleteOne(ps);
    reload();
  }

  async function clearAll(){
    if(!confirm("Clear ALL configs? This cannot be undone.")) return;
    await API.clear();
    reload();
  }

  async function saveSettings(){
    const s = {...settings};
    const res = await API.saveSettings(s);
    setSettings(res);
    alert("Saved");
  }

  return (
    <div className="app">
      <div className="header">
        <div className="brand">
          <div className="logo">VM</div>
          <div>
            <div className="h1">VMess Manager</div>
            <div className="small">Single-container v2ray + API + UI</div>
          </div>
        </div>
        <div className="controls">
          <button className="btn" onClick={reload}>Refresh</button>
          <button className="btn" onClick={clearAll}>Delete All</button>
        </div>
      </div>

      <div className="card">
        <div className="row" style={{justifyContent:"space-between"}}>
          <div style={{display:"flex",gap:8,alignItems:"center"}}>
            <input className="input" placeholder="Name (ps)" value={name} onChange={e=>setName(e.target.value)} />
            <button className="btn primary" onClick={createOne}>Create</button>
          </div>
          <div className="badge">Subscription: <span style={{marginLeft:8}}>{settings.SUBSCRIPTION_URL || '/'}</span></div>
        </div>

        <div className="list">
          {loading ? <div className="small">Loading...</div> : null}
          {list.length === 0 && !loading ? <div className="small">No vmess entries</div> : null}
          {list.map((it, idx) => (
            <div key={idx} className="item">
              <div className="meta">
                <div style={{fontWeight:600}}>{it.ps || "(unknown)"}</div>
                <div className="small">{it.add}:{it.port} • id: {it.id ? it.id.slice(0,8) : "—"}</div>
              </div>
              <div className="actions">
                <button className="btn" onClick={()=>copy(it._raw || JSON.stringify(it))}>Copy Link</button>
                <button className="btn" onClick={()=>copy(JSON.stringify(it))}>Copy JSON</button>
                <button className="btn" onClick={()=>remove(it.ps)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
          <div><strong>Settings</strong><div className="small">Change values below and save</div></div>
          <div className="small">VMess IP: {settings.VMESS_IP}</div>
        </div>

        <div className="settings" style={{marginTop:12}}>
          <div style={{display:"flex",flexDirection:"column",gap:6}}>
            <label className="small">VMESS_IP</label>
            <input className="input" value={settings.VMESS_IP || ""} onChange={e=>setSettings({...settings, VMESS_IP: e.target.value})}/>
          </div>
          <div style={{display:"flex",flexDirection:"column",gap:6}}>
            <label className="small">VMESS_PORT</label>
            <input className="input" value={settings.VMESS_PORT || ""} onChange={e=>setSettings({...settings, VMESS_PORT: Number(e.target.value)})}/>
          </div>
          <div style={{display:"flex",flexDirection:"column",gap:6}}>
            <label className="small">SUBSCRIPTION_URL</label>
            <input className="input" value={settings.SUBSCRIPTION_URL || ""} onChange={e=>setSettings({...settings, SUBSCRIPTION_URL: e.target.value})}/>
          </div>
          <div style={{display:"flex",flexDirection:"column",gap:6}}>
            <label className="small">SUBSCRIPTION_PORT</label>
            <input className="input" value={settings.SUBSCRIPTION_PORT || ""} onChange={e=>setSettings({...settings, SUBSCRIPTION_PORT: Number(e.target.value)})}/>
          </div>
        </div>
        <div style={{marginTop:12, display:"flex", gap:8}}>
          <button className="btn primary" onClick={saveSettings}>Save Settings</button>
        </div>
      </div>

      <div className="footer">
        <div>Tip: subscription endpoint: <code>{settings.SUBSCRIPTION_URL || '/subscription'}</code></div>
      </div>
    </div>
  );
}