import {
  Menu,
  FileSpreadsheet,
  AlertCircle,
  CheckCircle2,
  Cpu,
} from 'lucide-react'

export default function Header({ activeTab, dataset, onToggleSidebar, aiConfig = {} }) {
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
      subtitle: 'Interact in natural language with your configured AI engine',
    },
    cleaning: {
      title: 'Data Cleaning Studio',
      subtitle: 'Audit missing values, detect IQR outliers and duplicates',
    },
    settings: {
      title: 'Platform Settings',
      subtitle: 'Configure AI provider credentials, model parameters, and local inference',
    },
  }

  const current = titles[activeTab] || titles.overview

  const providerDisplay =
    aiConfig.provider === 'ollama' || !aiConfig.provider
      ? 'Local Ollama'
      : aiConfig.provider === 'openai_compatible' || aiConfig.provider === 'openai'
      ? 'OpenAI'
      : aiConfig.provider === 'groq'
      ? 'Groq Cloud'
      : aiConfig.provider === 'openrouter'
      ? 'OpenRouter'
      : aiConfig.provider === 'custom'
      ? 'Custom API'
      : aiConfig.provider

  const modelDisplay = aiConfig.model || 'qwen2.5:1.5b'

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
          <div
            className="dataset-status-pill dataset-status-ready"
            title={`File: ${dataset.fileName} (${dataset.totalRows.toLocaleString()} rows)`}
          >
            <FileSpreadsheet className="w-4 h-4 status-ready-icon" />
            <div className="status-text-group">
              <span className="status-primary">{dataset.fileName}</span>
              <span className="status-secondary">
                {dataset.totalRows.toLocaleString()} rows • {dataset.totalColumns} cols
              </span>
            </div>
            <CheckCircle2 className="w-4 h-4 status-check-icon" />
          </div>
        ) : (
          <div className="dataset-status-pill dataset-status-empty">
            <AlertCircle className="w-4 h-4 status-empty-icon" />
            <span className="status-primary">No Dataset Uploaded</span>
          </div>
        )}

        {/* AI Provider Status Pill */}
        <div
          className="user-profile-pill"
          title={`Active Engine: ${providerDisplay} (${modelDisplay})`}
        >
          <div className="user-avatar-wrap">
            <div className="user-avatar">
              <Cpu className="w-4 h-4 user-avatar-icon" />
            </div>
            <span className="user-status-dot" />
          </div>
          <div className="user-meta">
            <span className="user-name">{providerDisplay}</span>
            <span className="user-role">{modelDisplay}</span>
          </div>
        </div>
      </div>
    </header>
  )
}
