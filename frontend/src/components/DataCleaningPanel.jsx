import {
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Calendar,
  Layers,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react'

export default function DataCleaningPanel({ dataset, onNavigateToOverview }) {
  const cleaningModules = [
    {
      title: 'Missing Value Imputation',
      desc: 'Automatic numerical mean/median imputation and categorical mode imputation.',
      icon: Layers,
      status: 'Engine Built (cleaner.py)',
    },
    {
      title: 'Deduplication Engine',
      desc: 'Row-level duplicate detection and exact record removal with audit logging.',
      icon: CheckCircle2,
      status: 'Engine Built (cleaner.py)',
    },
    {
      title: 'Outlier Detection (IQR)',
      desc: 'Interquartile range analysis with upper and lower boundary thresholds.',
      icon: AlertTriangle,
      status: 'Engine Built (cleaner.py)',
    },
    {
      title: 'DateTime Type Conversion',
      desc: 'Mixed date format detection and conversion to ISO datetime dtypes.',
      icon: Calendar,
      status: 'Engine Built (cleaner.py)',
    },
  ]

  return (
    <div className="cleaning-panel-wrap">
      <div className="section-intro-card">
        <div className="intro-card-header">
          <div className="intro-icon-box">
            <Sparkles className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h2 className="intro-title">Data Cleaning Studio</h2>
            <p className="intro-subtitle">
              Automated data quality auditing, missing value imputation, and anomaly filtering
            </p>
          </div>
        </div>

        <div className="cleaning-status-strip">
          <div className="strip-item">
            <span className="strip-label">Target Dataset:</span>
            <span className="strip-val">
              {dataset?.fileName || 'None Selected (Upload in Overview)'}
            </span>
          </div>
          <div className="strip-item">
            <span className="strip-label">Backend Engine:</span>
            <span className="strip-val text-emerald-400">clean_dataset() Active</span>
          </div>
          <div className="strip-item">
            <span className="strip-label">Integration Phase:</span>
            <span className="strip-val text-purple-400">Milestone 4: Studio UI</span>
          </div>
        </div>
      </div>

      <div className="cleaning-modules-grid">
        {cleaningModules.map((mod, i) => {
          const Icon = mod.icon
          return (
            <div key={i} className="cleaning-module-card">
              <div className="module-icon-wrap">
                <Icon className="w-5 h-5 text-purple-400" />
              </div>
              <h3 className="module-title">{mod.title}</h3>
              <p className="module-desc">{mod.desc}</p>
              <div className="module-footer">
                <span className="module-status-pill">{mod.status}</span>
              </div>
            </div>
          )
        })}
      </div>

      <div className="cleaning-action-card">
        <div className="action-card-info">
          <ShieldAlert className="w-5 h-5 text-purple-400 mr-2 flex-shrink-0" />
          <div>
            <h4 className="action-card-title">One-Click Cleaning Workflow</h4>
            <p className="action-card-desc">
              Upload your dataset from the Overview tab, then run the multi-step cleaning pipeline with side-by-side comparison.
            </p>
          </div>
        </div>
        <button
          type="button"
          className="btn-primary btn-sm"
          onClick={onNavigateToOverview}
        >
          Go to Overview
          <ArrowRight className="w-4 h-4 ml-1.5" />
        </button>
      </div>
    </div>
  )
}
