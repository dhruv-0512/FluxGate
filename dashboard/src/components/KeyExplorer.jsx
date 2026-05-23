import { useEffect, useMemo, useState } from "react"
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts"
import api from "../api/client"

const formatMinute = (value) => {
  if (!value) return ""
  return new Date(value).toLocaleTimeString()
}

export default function KeyExplorer() {
  const [keyInput, setKeyInput] = useState("")
  const [activeKey, setActiveKey] = useState("")
  const [status, setStatus] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const chartData = useMemo(() => (
    [...history].reverse().map((item) => ({
      minute: item.minute,
      allowed: item.allowed,
      rejected: item.rejected,
    }))
  ), [history])

  const fetchKey = async (key) => {
    if (!key) return
    setLoading(true)
    setError("")
    try {
      const [statusRes, metricsRes] = await Promise.all([
        api.get(`/v1/status/${encodeURIComponent(key)}`),
        api.get(`/v1/metrics/${encodeURIComponent(key)}`),
      ])
      setStatus(statusRes.data)
      setHistory(metricsRes.data.history || [])
      setActiveKey(key)
    } catch (err) {
      setError("Failed to load key data.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (activeKey) {
      fetchKey(activeKey)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleReset = async () => {
    if (!activeKey) return
    setLoading(true)
    try {
      await api.post(`/v1/reset/${encodeURIComponent(activeKey)}`)
      await fetchKey(activeKey)
    } catch {
      setError("Failed to reset key.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">Keys</div>
          <h1>Key Explorer</h1>
        </div>
      </div>

      <div className="toolbar">
        <input
          className="input"
          placeholder="Search key (e.g. user:123)"
          value={keyInput}
          onChange={(event) => setKeyInput(event.target.value)}
        />
        <button className="btn" onClick={() => fetchKey(keyInput)}>Lookup</button>
        <div className="toolbar-note">Active: {activeKey || "None"}</div>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="split">
        <div className="card">
          <div className="card-title">Current Bucket State</div>
          {status ? (
            <div className="metric-list">
              <div>
                <span>Algorithm</span>
                <span className="mono">{status.algorithm}</span>
              </div>
              <div>
                <span>Remaining</span>
                <span className="mono">{status.remaining}</span>
              </div>
              <div>
                <span>Reset After (ms)</span>
                <span className="mono">{status.reset_after_ms}</span>
              </div>
            </div>
          ) : (
            <div className="empty">Awaiting key input.</div>
          )}
          <div className="card-actions">
            <button className="btn" onClick={() => fetchKey(activeKey)} disabled={!activeKey || loading}>
              Refresh
            </button>
            <button className="btn btn-danger" onClick={handleReset} disabled={!activeKey || loading}>
              Reset Key
            </button>
          </div>
        </div>

        <div className="card chart-panel">
          <div className="card-title">Traffic History</div>
          <div className="chart-wrap">
            {history.length ? (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={chartData}>
                  <CartesianGrid stroke="#1f2a2e" strokeDasharray="4 6" />
                  <XAxis dataKey="minute" tickFormatter={formatMinute} stroke="#556" />
                  <YAxis stroke="#556" />
                  <Tooltip
                    contentStyle={{ background: "#0f1418", border: "1px solid #253037" }}
                    labelFormatter={formatMinute}
                  />
                  <Line type="monotone" dataKey="allowed" stroke="#2ED47A" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="rejected" stroke="#FF4D4D" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty">No history yet.</div>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Recent Events</div>
        <div className="empty">Event logging UI placeholder. Wire this to your events feed when ready.</div>
      </div>
    </div>
  )
}
