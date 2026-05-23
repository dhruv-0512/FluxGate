import { useState } from "react"
import LiveDashboard from "./components/LiveDashboard"
import KeyExplorer from "./components/KeyExplorer"
import Analytics from "./components/Analytics"
import ConfigEditor from "./components/ConfigEditor"

const TABS = [
  { label: "Dashboard", value: "dashboard" },
  { label: "Key Explorer", value: "keys" },
  { label: "Analytics", value: "analytics" },
  { label: "Config", value: "config" },
]

export default function App() {
  const [tab, setTab] = useState("dashboard")

  return (
    <div className="app-shell">
      <div className="top-nav">
        <div className="logo">FluxGate</div>
        <div className="nav-links">
          {TABS.map((tabItem) => (
            <button
              key={tabItem.value}
              onClick={() => setTab(tabItem.value)}
              className={tab === tabItem.value ? "nav-link active" : "nav-link"}
            >
              {tabItem.label}
            </button>
          ))}
        </div>
      </div>

      <main className="page-shell">
        {tab === "dashboard" && <LiveDashboard />}
        {tab === "keys" && <KeyExplorer />}
        {tab === "analytics" && <Analytics />}
        {tab === "config" && <ConfigEditor />}
      </main>
    </div>
  )
}