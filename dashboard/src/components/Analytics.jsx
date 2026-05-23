import { useEffect, useMemo, useState } from "react"
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  BarChart,
  Bar,
} from "recharts"
import api from "../api/client"

const formatMinute = (value) => {
  if (!value) return ""
  return new Date(value).toLocaleTimeString()
}

const RANGE_OPTIONS = [
  { label: "Last 30m", value: 30 },
  { label: "Last 1h", value: 60 },
  { label: "Last 6h", value: 360 },
]

export default function Analytics() {
  const [range, setRange] = useState(60)
  const [keyInput, setKeyInput] = useState("")
  const [history, setHistory] = useState([])
  const [snapshot, setSnapshot] = useState(null)
  const [topKeys, setTopKeys] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    api.get("/v1/metrics")
      .then((res) => {
        setSnapshot(res.data)
        setTopKeys(res.data.top_throttled || [])
      })
      .catch(() => {})
  }, [])

  const rejectionSeries = useMemo(() => (
    [...history].reverse().map((item) => ({
      minute: item.minute,
      rejection_rate: item.rejection_rate,
    }))
  ), [history])

  const fetchHistory = async () => {
    if (!keyInput) return
    setLoading(true)
    setError("")
    try {
      const res = await api.get(`/v1/metrics/${encodeURIComponent(keyInput)}`, {
        params: { minutes: range },
      })
      setHistory(res.data.history || [])
    } catch {
      setError("Failed to load analytics history.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">Analytics</div>
          <h1>Signal Analytics</h1>
        </div>
      </div>

      <div className="toolbar">
        <select
          className="input select"
          value={range}
          onChange={(event) => setRange(Number(event.target.value))}
        >
          {RANGE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
        <input
          className="input"
          placeholder="Key filter"
          value={keyInput}
          onChange={(event) => setKeyInput(event.target.value)}
        />
        <button className="btn" onClick={fetchHistory} disabled={loading}>Load</button>
        <div className="toolbar-note">Aggregation: 1m</div>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="grid-cards">
        <div className="card">
          <div className="card-title">Avg RPS</div>
          <div className="card-metric">{snapshot?.rps?.toFixed(2) ?? "0.00"}</div>
        </div>
        <div className="card">
          <div className="card-title">Avg Acceptance</div>
          <div className="card-metric text-good">{snapshot?.acceptance_rate?.toFixed(1) ?? "0.0"}%</div>
        </div>
        <div className="card">
          <div className="card-title">Top Rejected Key</div>
          <div className="card-metric mono">{topKeys[0]?.key ?? "-"}</div>
        </div>
      </div>

      <div className="split">
        <div className="card chart-panel">
          <div className="card-title">Rejection Rate Over Time</div>
          <div className="chart-wrap">
            {rejectionSeries.length ? (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={rejectionSeries}>
                  <CartesianGrid stroke="#1f2a2e" strokeDasharray="4 6" />
                  <XAxis dataKey="minute" tickFormatter={formatMinute} stroke="#556" />
                  <YAxis stroke="#556" />
                  <Tooltip
                    contentStyle={{ background: "#0f1418", border: "1px solid #253037" }}
                    labelFormatter={formatMinute}
                  />
                  <Line type="monotone" dataKey="rejection_rate" stroke="#FF4D4D" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty">Load a key to see rejection trends.</div>
            )}
          </div>
        </div>

        <div className="card chart-panel">
          <div className="card-title">Per-Key Breakdown</div>
          <div className="chart-wrap">
            {topKeys.length ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={topKeys}>
                  <CartesianGrid stroke="#1f2a2e" strokeDasharray="4 6" />
                  <XAxis dataKey="key" stroke="#556" tickFormatter={(value) => String(value).slice(0, 8)} />
                  <YAxis stroke="#556" />
                  <Tooltip contentStyle={{ background: "#0f1418", border: "1px solid #253037" }} />
                  <Bar dataKey="rejected" fill="#FF4D4D" />
                  <Bar dataKey="allowed" fill="#2ED47A" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty">No breakdown data yet.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
