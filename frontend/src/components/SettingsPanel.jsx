import {
  Settings,
  Cpu,
  Server,
  DollarSign,
  ShieldCheck,
  HardDrive,
  CheckCircle2,
} from 'lucide-react'

export default function SettingsPanel() {
  const configs = [
    {
      label: 'Local LLM Inference',
      value: 'Ollama (qwen2.5:1.5b)',
      icon: Cpu,
      status: 'Active',
      detail: 'Local Metal GPU-accelerated weights',
    },
    {
      label: 'Inference Endpoint',
      value: 'http://localhost:11434/api/chat',
      icon: Server,
      status: 'Configured',
      detail: 'Zero latency over loopback network',
    },
    {
      label: 'Target Hardware',
      value: 'MacBook Pro M3 (8GB Unified Memory)',
      icon: HardDrive,
      status: 'Optimized',
      detail: 'Memory constrained footprint (<1.5GB)',
    },
    {
      label: 'API Budget & Billing',
      value: '₹0.00 (Completely Free)',
      icon: DollarSign,
      status: 'Enforced',
      detail: 'No external paid cloud APIs used',
    },
  ]

  return (
    <div className="settings-panel-wrap">
      <div className="section-intro-card">
        <div className="intro-card-header">
          <div className="intro-icon-box">
            <Settings className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h2 className="intro-title">Platform & Local Engine Settings</h2>
            <p className="intro-subtitle">
              Verify local model configuration, resource budgets, and runtime environment
            </p>
          </div>
        </div>
      </div>

      <div className="settings-grid">
        {configs.map((cfg, i) => {
          const Icon = cfg.icon
          return (
            <div key={i} className="setting-card">
              <div className="setting-header">
                <div className="setting-icon-box">
                  <Icon className="w-4 h-4 text-purple-400" />
                </div>
                <span className="setting-status-badge">
                  <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-400" />
                  {cfg.status}
                </span>
              </div>
              <h3 className="setting-label">{cfg.label}</h3>
              <p className="setting-value">{cfg.value}</p>
              <p className="setting-detail">{cfg.detail}</p>
            </div>
          )
        })}
      </div>

      <div className="settings-privacy-banner">
        <ShieldCheck className="w-5 h-5 text-emerald-400 mr-2.5 flex-shrink-0" />
        <div>
          <h4 className="privacy-title">Data Privacy & Sovereignty Assured</h4>
          <p className="privacy-desc">
            All dataset records and natural language questions remain 100% on your local machine. No data is sent to external servers or proprietary model providers.
          </p>
        </div>
      </div>
    </div>
  )
}
