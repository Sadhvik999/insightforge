import { ArrowUpRight } from 'lucide-react'

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  accent = 'purple',
  hasData = false,
  trendText,
}) {
  const accentClasses = {
    purple: 'stat-accent-purple',
    blue: 'stat-accent-blue',
    amber: 'stat-accent-amber',
    emerald: 'stat-accent-emerald',
  }

  const selectedAccent = accentClasses[accent] || accentClasses.purple

  return (
    <div className={`stat-card ${selectedAccent} ${!hasData ? 'stat-card-empty' : ''}`}>
      <div className="stat-card-glow" />
      <div className="stat-card-inner">
        <div className="stat-header">
          <span className="stat-title">{title}</span>
          <div className="stat-icon-wrap">
            {Icon && <Icon className="w-4 h-4 stat-icon" />}
          </div>
        </div>

        <div className="stat-value-row">
          <span className="stat-value">
            {hasData ? (
              typeof value === 'number' ? value.toLocaleString() : value
            ) : (
              <span className="stat-placeholder">--</span>
            )}
          </span>
          {hasData && trendText && (
            <span className="stat-trend">
              <ArrowUpRight className="w-3 h-3" />
              {trendText}
            </span>
          )}
        </div>

        <div className="stat-footer">
          <span className="stat-subtitle">
            {hasData ? subtitle : 'Upload dataset to compute'}
          </span>
        </div>
      </div>
    </div>
  )
}
