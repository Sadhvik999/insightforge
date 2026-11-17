import {
  LayoutDashboard,
  TableProperties,
  Bot,
  Sparkles,
  Settings,
  X,
  Cpu,
  ShieldCheck,
  Flame,
} from 'lucide-react'

export default function Sidebar({ activeTab, onSelectTab, isOpen, onClose }) {
  const navItems = [
    {
      id: 'overview',
      label: 'Overview',
      icon: LayoutDashboard,
      description: 'Dataset metrics & quick actions',
    },
    {
      id: 'explorer',
      label: 'Data Explorer',
      icon: TableProperties,
      description: 'Tabular preview & schema',
    },
    {
      id: 'analyst',
      label: 'AI Analyst',
      icon: Bot,
      badge: 'Local Qwen',
      description: 'Natural language analysis',
    },
    {
      id: 'cleaning',
      label: 'Data Cleaning',
      icon: Sparkles,
      description: 'Deduplication & imputation',
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: Settings,
      description: 'Ollama & system parameters',
    },
  ]

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="sidebar-backdrop"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside className={`sidebar ${isOpen ? 'sidebar-open' : ''}`}>
        {/* Brand Header */}
        <div className="sidebar-brand">
          <div className="brand-logo-wrap">
            <div className="brand-logo-glow" />
            <div className="brand-icon">
              <Flame className="w-5 h-5 text-purple-400" />
            </div>
          </div>
          <div className="brand-info">
            <div className="brand-title-row">
              <span className="brand-name">InsightForge</span>
              <span className="brand-tag">v1.0</span>
            </div>
            <span className="brand-subtitle">AI Data Analyst</span>
          </div>

          <button
            type="button"
            className="sidebar-close-btn"
            onClick={onClose}
            aria-label="Close navigation menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation List */}
        <nav className="sidebar-nav" aria-label="Main Navigation">
          <div className="sidebar-section-label">WORKSPACE</div>
          <ul className="nav-list">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = activeTab === item.id
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    className={`nav-item ${isActive ? 'nav-item-active' : ''}`}
                    onClick={() => {
                      onSelectTab(item.id)
                      if (onClose) onClose()
                    }}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    <span className="nav-item-icon-wrap">
                      <Icon className="w-4 h-4" />
                    </span>
                    <span className="nav-item-text">{item.label}</span>
                    {item.badge && (
                      <span className="nav-item-badge">{item.badge}</span>
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        </nav>

        {/* System & Hardware Health Pill */}
        <div className="sidebar-system-card">
          <div className="system-card-header">
            <div className="system-indicator">
              <span className="system-indicator-dot" />
              <span className="system-status-text">Local Engine Active</span>
            </div>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>

          <div className="system-meta-item">
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            <span>qwen2.5:1.5b (Ollama)</span>
          </div>

          <div className="system-tags-row">
            <span className="system-pill">M3 8GB RAM</span>
            <span className="system-pill system-pill-free">₹0 API Cost</span>
          </div>
        </div>
      </aside>
    </>
  )
}
