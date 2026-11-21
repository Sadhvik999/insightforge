import { ArrowUpRight } from 'lucide-react'

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  accent,
  isWarning = false,
  hasData = false,
  trendText,
}) {
  // Tweak 1: Unify metric card icons to a single neutral (#71717A),
  // and only use color when an actual warning or error triggers.
  const isAlert =
    isWarning ||
    (hasData && (title === 'Missing Values' || title === 'Duplicate Rows') && Number(value) > 0) ||
    accent === 'warning' ||
    accent === 'danger'

  return (
    <div
      className={`stat-card ${
        isAlert ? 'stat-card-warning' : 'stat-card-neutral'
      } ${!hasData ? 'stat-card-empty' : ''}`}
    >
      <div className="stat-card-inner">
        <div className="stat-header">
          <div className="stat-title-wrap">
            <span className="stat-title">{title}</span>
            {isAlert && (
              <span className="stat-warning-badge" aria-hidden="true">
                Requires Review
              </span>
            )}
          </div>
          <div
            className={`stat-icon-wrap ${
              isAlert ? 'stat-icon-warning' : 'stat-icon-neutral'
            }`}
          >
            {Icon && <Icon className="w-4 h-4 stat-icon" />}
          </div>
        </div>

        <div className="stat-value-row">
          <span className="stat-value">
            {hasData ? (
              typeof value === 'number' ? (
                value.toLocaleString()
              ) : (
                value
              )
            ) : (
              <span className="stat-placeholder">--</span>
            )}
          </span>
          {hasData && trendText && (
            <span className={`stat-trend ${isAlert ? 'stat-trend-warning' : ''}`}>
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
