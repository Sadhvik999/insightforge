import {
  Menu,
  FileSpreadsheet,
  AlertCircle,
  CheckCircle2,
  User,
  Sparkles,
} from 'lucide-react'

export default function Header({ activeTab, dataset, onToggleSidebar }) {
  const titles = {
    overview: {
      title: 'Dashboard Overview',
      subtitle: 'Monitor dataset metrics, health statistics & visual insights',
    },
    explorer: {
      title: 'Data Explorer',
      subtitle: 'Inspect dataset schema, raw rows and column attributes',
    },
    analyst: {
      title: 'AI Analyst Chat',
      subtitle: 'Interact in natural language with local Qwen 2.5 1.5B',
    },
    cleaning: {
      title: 'Data Cleaning Studio',
      subtitle: 'Audit missing values, detect IQR outliers and duplicates',
    },
    settings: {
      title: 'Platform Settings',
      subtitle: 'Manage local inference settings, RAM limits and API configs',
    },
  }

  const current = titles[activeTab] || titles.overview

  return (
    <header className="app-header">
      <div className="header-left">
        <button
          type="button"
          className="header-menu-btn"
          onClick={onToggleSidebar}
          aria-label="Toggle navigation sidebar"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="header-titles">
          <div className="header-breadcrumb">
            <span>InsightForge</span>
            <span className="breadcrumb-separator">/</span>
            <span className="breadcrumb-current">{current.title}</span>
          </div>
          <h1 className="header-heading">{current.title}</h1>
        </div>
      </div>

      <div className="header-right">
        {/* Dataset Status Badge */}
        {dataset && dataset.fileName ? (
          <div className="dataset-status-pill dataset-status-ready" title={`File: ${dataset.fileName} (${dataset.totalRows.toLocaleString()} rows)`}>
            <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
            <div className="status-text-group">
              <span className="status-primary">{dataset.fileName}</span>
              <span className="status-secondary">
                {dataset.totalRows.toLocaleString()} rows • {dataset.totalColumns} cols
              </span>
            </div>
            <CheckCircle2 className="w-4 h-4 text-emerald-400 status-check-icon" />
          </div>
        ) : (
          <div className="dataset-status-pill dataset-status-empty">
            <AlertCircle className="w-4 h-4 text-amber-400" />
            <span className="status-primary">No Dataset Uploaded</span>
          </div>
        )}

        {/* User Profile Pill */}
        <div className="user-profile-pill" title="Local Data Analyst (Offline Session)">
          <div className="user-avatar-wrap">
            <div className="user-avatar">
              <User className="w-4 h-4 text-purple-300" />
            </div>
            <span className="user-status-dot" />
          </div>
          <div className="user-meta">
            <span className="user-name">Local Analyst</span>
            <span className="user-role">
              <Sparkles className="w-2.5 h-2.5 text-purple-400 inline mr-0.5" />
              Offline M3
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}
