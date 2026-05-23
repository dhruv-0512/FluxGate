import { useEffect, useMemo, useRef, useState } from "react"
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  RadialBar,
  RadialBarChart,
  PolarAngleAxis,
} from "recharts"
import api from "../api/client"

const formatTime = (unixSeconds) => {
  if (!unixSeconds) return ""
  return new Date(unixSeconds * 1000).toLocaleTimeString()
}

const initialMetrics = {
  rps: 0,
  acceptance_rate: 100,
  total_allowed: 0,
  total_rejected: 0,
  top_throttled: [],
  timestamp: null,
}

export default function LiveDashboard() {
  const [metrics, setMetrics] = useState(initialMetrics)
  const [history, setHistory] = useState([])
  const [socketStatus, setSocketStatus] = useState("connecting")
  const socketRef = useRef(null)

  useEffect(() => {
    let isMounted = true
    api.get("/v1/metrics")
      .then((res) => {
        if (!isMounted) return
        setMetrics((prev) => ({ ...prev, ...res.data }))
      })
      .catch(() => {})

    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    const ws = new WebSocket(`ws://${window.location.host}/ws/metrics`)
    socketRef.current = ws

    ws.addEventListener("open", () => setSocketStatus("connected"))
    ws.addEventListener("close", () => setSocketStatus("disconnected"))
    ws.addEventListener("error", () => setSocketStatus("error"))
    ws.addEventListener("message", (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (payload.type && payload.type !== "metrics") return
        setMetrics(payload)
        setHistory((prev) => {
          const next = [
            ...prev,
            {
              timestamp: payload.timestamp || Date.now() / 1000,
              rps: payload.rps,
              acceptance_rate: payload.acceptance_rate,
              allowed: payload.total_allowed,
              rejected: payload.total_rejected,
            },
          ]
          return next.slice(-60)
        })
      } catch {
        // Ignore malformed payloads
      }
    })

    return () => {
      ws.close()
    }
  }, [])

  const gaugeData = useMemo(() => ([
    { name: "Acceptance", value: metrics.acceptance_rate ?? 0, fill: "#2ED47A" },
  ]), [metrics.acceptance_rate])

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">Realtime Metrics</div>
          <h1>FluxGate Dashboard</h1>
        </div>
        <div className={`status-pill status-${socketStatus}`}>
          <span className="status-dot" />
          {socketStatus.toUpperCase()}
        </div>
      </div>

      <div className="grid-cards">
        <div className="card">
          <div className="card-title">Live RPS</div>
          <div className="card-metric">{metrics.rps?.toFixed(2) ?? "0.00"}</div>
          <div className="card-sub">Updated {formatTime(metrics.timestamp)}</div>
        </div>
        <div className="card card-gauge">
          <div className="card-title">Acceptance Rate</div>
          <div className="gauge-wrap">
            <ResponsiveContainer width="100%" height={150}>
              <RadialBarChart
                cx="50%"
                cy="90%"
                innerRadius={70}
                outerRadius={100}
                startAngle={180}
                endAngle={0}
                data={gaugeData}
              >
                <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                <RadialBar dataKey="value" cornerRadius={10} />
              </RadialBarChart>
            </ResponsiveContainer>
            <div className="gauge-label">{metrics.acceptance_rate?.toFixed(1) ?? "0.0"}%</div>
          </div>
        </div>
        <div className="card">
          <div className="card-title">Total Allowed</div>
          <div className="card-metric text-good">{metrics.total_allowed ?? 0}</div>
          <div className="card-sub">Across all keys</div>
        </div>
        <div className="card">
          <div className="card-title">Total Rejected</div>
          <div className="card-metric text-bad">{metrics.total_rejected ?? 0}</div>
          <div className="card-sub">Across all keys</div>
        </div>
      </div>

      <div className="card chart-panel">
        <div className="card-title">Requests Over Time</div>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={history}>
              <CartesianGrid stroke="#1f2a2e" strokeDasharray="4 6" />
              <XAxis dataKey="timestamp" tickFormatter={formatTime} stroke="#556" />
              <YAxis stroke="#556" />
              <Tooltip
                contentStyle={{ background: "#0f1418", border: "1px solid #253037" }}
                labelFormatter={formatTime}
              />
              <Line type="monotone" dataKey="allowed" stroke="#2ED47A" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="rejected" stroke="#FF4D4D" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Top Throttled Keys</div>
        <div className="table">
          <div className="table-head">
            <span>Key</span>
            <span>Allowed</span>
            <span>Rejected</span>
            <span>Rejection Rate</span>
          </div>
          {metrics.top_throttled?.length ? (
            metrics.top_throttled.map((row) => (
              <div key={row.key} className="table-row">
                <span className="mono">{row.key}</span>
                <span>{row.allowed ?? 0}</span>
                <span className="text-bad">{row.rejected ?? row.rejected_count ?? 0}</span>
                <span className={row.rejection_rate > 10 ? "text-bad" : "text-good"}>
                  {(row.rejection_rate ?? 0).toFixed(1)}%
                </span>
              </div>
            ))
          ) : (
            <div className="empty">No throttled keys yet.</div>
          )}
        </div>
      </div>
    </div>
  )
}
