import { useEffect, useState } from "react"
import api from "../api/client"

export default function ConfigEditor() {
  const [rules, setRules] = useState([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState("")

  const loadRules = async () => {
    setLoading(true)
    try {
      const res = await api.get("/v1/rules")
      setRules(res.data.rules || [])
    } catch {
      setMessage("Failed to load rules.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRules()
  }, [])

  const handleReload = async () => {
    setMessage("")
    setLoading(true)
    try {
      const res = await api.post("/v1/config/reload")
      setMessage(`Reloaded. Rules: ${res.data.rules_count}`)
      await loadRules()
    } catch {
      setMessage("Reload failed.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">Config</div>
          <h1>Active Rules</h1>
        </div>
        <button className="btn" onClick={handleReload} disabled={loading}>Reload Config</button>
      </div>

      {message ? <div className="info-banner">{message}</div> : null}

      <div className="split">
        <div className="card">
          <div className="card-title">Rules</div>
          <div className="table">
            <div className="table-head">
              <span>Rule</span>
              <span>Limiter</span>
              <span>Burst</span>
              <span>Rate</span>
              <span>Scope</span>
              <span>Updated</span>
            </div>
            {rules.length ? (
              rules.map((rule) => (
                <div key={rule.key_pattern} className="table-row">
                  <span className="mono">{rule.key_pattern}</span>
                  <span>{rule.algorithm}</span>
                  <span>{rule.burst ?? rule.capacity ?? "-"}</span>
                  <span>{rule.rate ?? rule.refill_rate ?? rule.limit ?? "-"}</span>
                  <span>{rule.scope ?? "global"}</span>
                  <span>{rule.updated_at ?? "-"}</span>
                </div>
              ))
            ) : (
              <div className="empty">No rules found.</div>
            )}
          </div>
        </div>

        <div className="card sidebar">
          <div className="card-title">Config Status</div>
          <div className="metric-list">
            <div>
              <span>Status</span>
              <span className="text-good">Active</span>
            </div>
            <div>
              <span>Last Reload</span>
              <span className="mono">{new Date().toLocaleString()}</span>
            </div>
            <div>
              <span>Source</span>
              <span className="mono">config.yaml</span>
            </div>
          </div>
          <div className="empty">Reload triggers a hot config refresh across nodes.</div>
        </div>
      </div>
    </div>
  )
}
