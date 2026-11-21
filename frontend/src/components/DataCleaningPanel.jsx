import { useState } from 'react'
import {
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Calendar,
  Layers,
  ArrowRight,
  ShieldCheck,
  Loader2,
  RefreshCw,
  Database,
  CopyCheck,
  Hash,
  FileSpreadsheet,
  XCircle,
  Info,
} from 'lucide-react'
import { cleanDataset } from '../api/client'

export default function DataCleaningPanel({
  dataset,
  cleaningResult: externalResult,
  onCleaningResultChange,
  onNavigateToOverview,
}) {
  const [internalResult, setInternalResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('summary') // 'summary', 'missing', 'outliers', 'dates_dedup'
  const [showAllColumns, setShowAllColumns] = useState(false)

  // Use external result from parent App state if provided, otherwise internal
  const cleaningResult = externalResult !== undefined ? externalResult : internalResult

  const setCleaningResult = (res) => {
    if (onCleaningResultChange) {
      onCleaningResultChange(res)
    } else {
      setInternalResult(res)
    }
  }

  const handleRunCleaning = async () => {
    if (!dataset?.file) {
      setError('No dataset file found. Please upload a CSV dataset from the Overview tab.')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const response = await cleanDataset(dataset.file)
      setCleaningResult(response)
    } catch (err) {
      setError(err.message || 'Cleaning pipeline failed. Please ensure the backend server is reachable.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleClearReport = () => {
    setCleaningResult(null)
    setError(null)
  }

  // Pre-cleaning explanation cards
  const cleaningModules = [
    {
      title: 'Missing Value Imputation',
      desc: 'Automatic numerical mean imputation and categorical mode imputation across all columns with full audit logs.',
      icon: Layers,
      status: 'clean_dataset() Active',
    },
    {
      title: 'Deduplication Engine',
      desc: 'Row-level duplicate detection and exact record removal with before and after row counts.',
      icon: CheckCircle2,
      status: 'clean_dataset() Active',
    },
    {
      title: 'Outlier Detection (IQR)',
      desc: 'Interquartile range analysis (Q1 - 1.5*IQR to Q3 + 1.5*IQR) with upper and lower boundary thresholds.',
      icon: AlertTriangle,
      status: 'clean_dataset() Active',
    },
    {
      title: 'DateTime Type Conversion',
      desc: 'Mixed date format detection and standardization to ISO 8601 datetime types.',
      icon: Calendar,
      status: 'clean_dataset() Active',
    },
  ]

  // Extract metrics from backend response
  const originalRows = cleaningResult?.original_rows ?? dataset?.totalRows ?? 0
  const cleanedRows = cleaningResult?.cleaned_rows ?? 0
  const report = cleaningResult?.cleaning_report || {}

  const missingBefore = report.missing_before || {}
  const missingAfter = report.missing_after || {}

  const totalMissingBefore = Object.values(missingBefore).reduce(
    (acc, item) => acc + (Number(item?.missing_count) || 0),
    0
  )
  const totalMissingAfter = Object.values(missingAfter).reduce(
    (acc, item) => acc + (Number(item?.missing_count) || 0),
    0
  )
  const missingFilledTotal = Math.max(0, totalMissingBefore - totalMissingAfter)

  const duplicatesDetected = report.duplicates_before?.duplicate_count ?? 0
  const duplicatesPercentage = report.duplicates_before?.duplicate_percentage ?? 0
  const duplicatesRemoved = report.duplicates_removed ?? 0

  const outliers = report.outliers || {}
  const outlierEntries = Object.entries(outliers)
  const totalOutliers = outlierEntries.reduce(
    (acc, [, item]) => acc + (Number(item?.outlier_count) || 0),
    0
  )

  const convertedDates = report.converted_date_columns || []
  const numericalFilled = report.numerical_values_filled || {}
  const totalNumericalFilled = Object.values(numericalFilled).reduce(
    (acc, val) => acc + (Number(val) || 0),
    0
  )

  const categoricalFilled = report.categorical_values_filled || {}
  const totalCategoricalFilled = Object.values(categoricalFilled).reduce(
    (acc, val) => acc + (Number(val) || 0),
    0
  )

  const skippedNumerical = report.skipped_numerical_columns || []
  const skippedCategorical = report.skipped_categorical_columns || []

  const allReportColumns = cleaningResult?.columns || Object.keys(missingBefore)
  const columnsWithMissing = allReportColumns.filter(
    (col) => (missingBefore[col]?.missing_count || 0) > 0
  )
  const columnsToDisplay = showAllColumns ? allReportColumns : columnsWithMissing

  const hasData = Boolean(dataset && dataset.fileName)

  return (
    <div className="cleaning-panel-wrap">
      {/* 1. Header Card */}
      <div className="section-intro-card">
        <div className="intro-card-header">
          <div className="intro-icon-box">
            <Sparkles className="w-6 h-6 text-purple-400" />
          </div>
          <div className="intro-title-wrap">
            <h2 className="intro-title">Data Cleaning Studio</h2>
            <p className="intro-subtitle">
              Automated data quality auditing, missing value imputation, deduplication, and IQR outlier detection
            </p>
          </div>
          <div className="header-action-wrap">
            <button
              type="button"
              className="btn-primary"
              onClick={handleRunCleaning}
              disabled={isLoading || !dataset?.file}
              title={
                !dataset?.file
                  ? 'Upload a CSV dataset in Overview first'
                  : 'Send file to FastAPI POST /clean'
              }
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Cleaning Dataset...
                </>
              ) : cleaningResult ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Re-run Cleaning
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-2" />
                  Run Cleaning
                </>
              )}
            </button>
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
            <span className="strip-label">Original Rows:</span>
            <span className="strip-val">
              {hasData ? `${dataset.totalRows.toLocaleString()} rows` : '--'}
            </span>
          </div>
          <div className="strip-item">
            <span className="strip-label">Backend Engine:</span>
            <span className="strip-val text-emerald-400">clean_dataset() Active</span>
          </div>
          <div className="strip-item">
            <span className="strip-label">Pipeline Status:</span>
            {isLoading ? (
              <span className="strip-val text-amber-400 animate-pulse">Running...</span>
            ) : cleaningResult ? (
              <span className="strip-val text-emerald-400">Cleaned & Audited</span>
            ) : error ? (
              <span className="strip-val text-rose-400">Failed</span>
            ) : (
              <span className="strip-val text-purple-400">
                {dataset?.file ? 'Ready to Clean' : 'Awaiting Dataset'}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 2. Loading State Banner */}
      {isLoading && (
        <div className="cleaning-loading-card" role="status" aria-live="polite">
          <div className="loading-card-icon-wrap">
            <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
          </div>
          <div className="loading-card-content">
            <h4 className="loading-card-title">Executing Data Cleaning Pipeline...</h4>
            <p className="loading-card-desc">
              Uploading <code>{dataset?.fileName}</code> to FastAPI <code>POST /clean</code>. Running deduplication, numerical mean imputation, categorical mode imputation, mixed date conversion, and IQR outlier boundary calculations.
            </p>
          </div>
        </div>
      )}

      {/* 3. Error State Banner */}
      {error && !isLoading && (
        <div className="cleaning-error-card" role="alert">
          <div className="error-card-icon-wrap">
            <XCircle className="w-6 h-6 text-rose-400" />
          </div>
          <div className="error-card-content">
            <h4 className="error-card-title">Cleaning Pipeline Error</h4>
            <p className="error-card-desc">{error}</p>
          </div>
          <div className="error-card-actions">
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={handleRunCleaning}
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              Try Again
            </button>
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={() => setError(null)}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* 4. Empty State (no dataset uploaded) */}
      {!hasData && !isLoading && (
        <div className="cleaning-empty-card">
          <div className="empty-icon-wrap">
            <FileSpreadsheet className="w-10 h-10 text-purple-400" />
          </div>
          <h3 className="empty-title">No Dataset Loaded</h3>
          <p className="empty-desc">
            To use the Data Cleaning Studio, please upload a CSV dataset from the Overview tab.
            The original CSV file is preserved in memory and sent via <code>multipart/form-data</code> to the FastAPI backend.
          </p>
          <button
            type="button"
            className="btn-primary btn-sm"
            onClick={onNavigateToOverview}
          >
            Go to Overview
            <ArrowRight className="w-4 h-4 ml-1.5" />
          </button>
        </div>
      )}

      {/* 5. Pre-Clean Action Card (Dataset ready, cleaning not yet executed) */}
      {hasData && !cleaningResult && !isLoading && (
        <>
          <div className="cleaning-action-card">
            <div className="action-card-info">
              <Sparkles className="w-5 h-5 text-purple-400 mr-2 flex-shrink-0" />
              <div>
                <h4 className="action-card-title">Run Automated Data Cleaning</h4>
                <p className="action-card-desc">
                  Audit and clean <code>{dataset.fileName}</code> ({dataset.totalRows.toLocaleString()} rows, {dataset.totalColumns} columns).
                  Imputes missing values, purges duplicate records, converts date strings, and computes IQR outlier boundaries without modifying your original session file.
                </p>
              </div>
            </div>
            <button
              type="button"
              className="btn-primary"
              onClick={handleRunCleaning}
              disabled={isLoading}
            >
              <Sparkles className="w-4 h-4 mr-2" />
              Run Cleaning
            </button>
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
        </>
      )}

      {/* 6. Post-Clean Results & Before/After Comparison */}
      {cleaningResult && !isLoading && (
        <div className="cleaning-results-section">
          {/* Success Banner */}
          <div className="cleaning-success-card">
            <div className="success-header-row">
              <div className="success-title-wrap">
                <CheckCircle2 className="w-5 h-5 text-emerald-400 mr-2 flex-shrink-0" />
                <div>
                  <h4 className="success-title">Cleaning Pipeline Completed Successfully</h4>
                  <p className="success-subtitle">
                    Processed {originalRows.toLocaleString()} original rows into {cleanedRows.toLocaleString()} verified cleaned rows.
                    All transformations were performed on the server via <code>POST /clean</code>.
                  </p>
                </div>
              </div>
              <div className="success-actions">
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={handleRunCleaning}
                  title="Re-run cleaning pipeline"
                >
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                  Re-run
                </button>
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={handleClearReport}
                  title="Clear report view"
                >
                  Clear View
                </button>
              </div>
            </div>

            {/* Non-destructive notice */}
            <div className="cleaning-safe-badge">
              <ShieldCheck className="w-4 h-4 text-emerald-400 mr-1.5 flex-shrink-0" />
              <span>
                <strong>Original File Preserved:</strong> The original uploaded CSV file (<code>{dataset?.fileName}</code>) and your current AI Analyst conversation context remain intact.
              </span>
            </div>
          </div>

          {/* Before & After KPI Comparison Grid */}
          <div className="cleaning-kpi-grid">
            {/* KPI 1: Row Count */}
            <div className="cleaning-kpi-card">
              <div className="kpi-header">
                <span className="kpi-label">Dataset Row Count</span>
                <Database className="w-4 h-4 text-purple-400" />
              </div>
              <div className="kpi-comparison-row">
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Before</span>
                  <span className="kpi-val">{originalRows.toLocaleString()}</span>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 kpi-arrow" />
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">After</span>
                  <span className="kpi-val text-emerald-400">{cleanedRows.toLocaleString()}</span>
                </div>
              </div>
              <div className="kpi-footer">
                <span className="kpi-delta-pill">
                  {duplicatesRemoved > 0 ? `-${duplicatesRemoved.toLocaleString()} duplicate rows` : '100% rows preserved'}
                </span>
              </div>
            </div>

            {/* KPI 2: Missing Values */}
            <div className="cleaning-kpi-card">
              <div className="kpi-header">
                <span className="kpi-label">Missing Values</span>
                <AlertTriangle className="w-4 h-4 text-amber-400" />
              </div>
              <div className="kpi-comparison-row">
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Before</span>
                  <span className="kpi-val">{totalMissingBefore.toLocaleString()}</span>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 kpi-arrow" />
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">After</span>
                  <span className="kpi-val text-emerald-400">{totalMissingAfter.toLocaleString()}</span>
                </div>
              </div>
              <div className="kpi-footer">
                <span className="kpi-delta-pill">
                  {missingFilledTotal > 0
                    ? `${missingFilledTotal.toLocaleString()} values imputed`
                    : '0 missing cells'}
                </span>
              </div>
            </div>

            {/* KPI 3: Duplicate Rows */}
            <div className="cleaning-kpi-card">
              <div className="kpi-header">
                <span className="kpi-label">Duplicate Rows</span>
                <CopyCheck className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="kpi-comparison-row">
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Detected</span>
                  <span className="kpi-val">{duplicatesDetected.toLocaleString()}</span>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 kpi-arrow" />
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Removed</span>
                  <span className="kpi-val text-emerald-400">{duplicatesRemoved.toLocaleString()}</span>
                </div>
              </div>
              <div className="kpi-footer">
                <span className="kpi-delta-pill">
                  {duplicatesDetected > 0 ? `${duplicatesPercentage}% duplicate rate` : '0 duplicates'}
                </span>
              </div>
            </div>

            {/* KPI 4: Outliers Detected */}
            <div className="cleaning-kpi-card">
              <div className="kpi-header">
                <span className="kpi-label">Outliers Flagged (IQR)</span>
                <Layers className="w-4 h-4 text-blue-400" />
              </div>
              <div className="kpi-comparison-row">
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Audited Columns</span>
                  <span className="kpi-val">{outlierEntries.length}</span>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 kpi-arrow" />
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Outliers</span>
                  <span className="kpi-val text-blue-400">{totalOutliers.toLocaleString()}</span>
                </div>
              </div>
              <div className="kpi-footer">
                <span className="kpi-delta-pill text-blue-300">Preserved in Dataset</span>
              </div>
            </div>

            {/* KPI 5: Datetime Conversions */}
            <div className="cleaning-kpi-card">
              <div className="kpi-header">
                <span className="kpi-label">Converted Date Columns</span>
                <Calendar className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="kpi-comparison-row">
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Converted</span>
                  <span className="kpi-val text-emerald-400">{convertedDates.length}</span>
                </div>
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Target Format</span>
                  <span className="kpi-val">ISO 8601</span>
                </div>
              </div>
              <div className="kpi-footer">
                <span className="kpi-delta-pill">
                  {convertedDates.length > 0 ? 'Datetime standardized' : 'No date cols'}
                </span>
              </div>
            </div>
          </div>

          {/* Sub-tab Navigation */}
          <div className="cleaning-subtabs-wrap">
            <button
              type="button"
              className={`cleaning-subtab-btn ${activeTab === 'summary' ? 'active' : ''}`}
              onClick={() => setActiveTab('summary')}
            >
              Before & After Comparison
            </button>
            <button
              type="button"
              className={`cleaning-subtab-btn ${activeTab === 'missing' ? 'active' : ''}`}
              onClick={() => setActiveTab('missing')}
            >
              Missing Values Imputation ({columnsWithMissing.length})
            </button>
            <button
              type="button"
              className={`cleaning-subtab-btn ${activeTab === 'outliers' ? 'active' : ''}`}
              onClick={() => setActiveTab('outliers')}
            >
              Outlier Detection IQR ({outlierEntries.length})
            </button>
            <button
              type="button"
              className={`cleaning-subtab-btn ${activeTab === 'dates_dedup' ? 'active' : ''}`}
              onClick={() => setActiveTab('dates_dedup')}
            >
              Date Conversions & Deduplication
            </button>
          </div>

          {/* Tab 1: Comprehensive Before & After Comparison Matrix */}
          {activeTab === 'summary' && (
            <div className="cleaning-tab-content">
              <div className="cleaning-table-card">
                <div className="table-card-header">
                  <h4 className="table-card-title">Before vs After Transformation Summary</h4>
                  <span className="table-card-badge">Server Audit Log</span>
                </div>
                <div className="table-scroll-wrap">
                  <table className="dataset-table" aria-label="Before vs After Comparison Matrix">
                    <thead>
                      <tr>
                        <th scope="col" className="table-header-cell">Pipeline Dimension</th>
                        <th scope="col" className="table-header-cell">Before Cleaning</th>
                        <th scope="col" className="table-header-cell">After Cleaning</th>
                        <th scope="col" className="table-header-cell">Transformation Action</th>
                        <th scope="col" className="table-header-cell">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="table-row">
                        <td className="table-cell font-semibold">Row Deduplication</td>
                        <td className="table-cell">{originalRows.toLocaleString()} rows ({duplicatesDetected} duplicates)</td>
                        <td className="table-cell text-emerald-400 font-semibold">{cleanedRows.toLocaleString()} unique rows</td>
                        <td className="table-cell">
                          {duplicatesRemoved > 0
                            ? `Purged ${duplicatesRemoved.toLocaleString()} duplicate records`
                            : 'Zero duplicate rows detected'}
                        </td>
                        <td className="table-cell">
                          <span className="audit-status-badge badge-success">Completed</span>
                        </td>
                      </tr>
                      <tr className="table-row">
                        <td className="table-cell font-semibold">Missing Value Imputation</td>
                        <td className="table-cell">{totalMissingBefore.toLocaleString()} null values</td>
                        <td className="table-cell text-emerald-400 font-semibold">{totalMissingAfter.toLocaleString()} null values</td>
                        <td className="table-cell">
                          {missingFilledTotal > 0
                            ? `Imputed ${totalNumericalFilled} numerical (mean) & ${totalCategoricalFilled} categorical (mode)`
                            : 'No missing values needed imputation'}
                        </td>
                        <td className="table-cell">
                          <span className="audit-status-badge badge-success">Completed</span>
                        </td>
                      </tr>
                      <tr className="table-row">
                        <td className="table-cell font-semibold">Date Format Standardization</td>
                        <td className="table-cell">Mixed string / object format</td>
                        <td className="table-cell text-emerald-400 font-semibold">ISO 8601 Datetime</td>
                        <td className="table-cell">
                          {convertedDates.length > 0
                            ? `Converted ${convertedDates.length} columns: ${convertedDates.join(', ')}`
                            : 'No datetime candidates detected'}
                        </td>
                        <td className="table-cell">
                          <span className="audit-status-badge badge-success">Completed</span>
                        </td>
                      </tr>
                      <tr className="table-row">
                        <td className="table-cell font-semibold">Outlier Anomaly Detection</td>
                        <td className="table-cell">Raw numerical distribution</td>
                        <td className="table-cell text-blue-400 font-semibold">{totalOutliers.toLocaleString()} outliers flagged</td>
                        <td className="table-cell">
                          Audited {outlierEntries.length} numerical columns using IQR method; values retained for analytical accuracy
                        </td>
                        <td className="table-cell">
                          <span className="audit-status-badge badge-info">Audited (Preserved)</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: Missing Values Imputation */}
          {activeTab === 'missing' && (
            <div className="cleaning-tab-content">
              <div className="cleaning-table-card">
                <div className="table-card-header">
                  <div>
                    <h4 className="table-card-title">Missing Values Imputation Breakdown</h4>
                    <p className="table-card-desc">
                      Total filled: {totalNumericalFilled} numerical values (mean strategy) and {totalCategoricalFilled} categorical values (mode strategy).
                    </p>
                  </div>
                  <div className="table-toggle-wrap">
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      onClick={() => setShowAllColumns(!showAllColumns)}
                    >
                      {showAllColumns ? 'Show Affected Columns Only' : 'Show All Columns'}
                    </button>
                  </div>
                </div>

                {columnsToDisplay.length === 0 ? (
                  <div className="cleaning-card-empty">
                    <CheckCircle2 className="w-8 h-8 text-emerald-400 mb-2" />
                    <p className="font-semibold text-emerald-400">Zero Missing Values</p>
                    <p className="text-muted text-xs">
                      No missing or null cells were detected in any column of this dataset.
                    </p>
                  </div>
                ) : (
                  <div className="table-scroll-wrap">
                    <table className="dataset-table" aria-label="Missing Values Breakdown">
                      <thead>
                        <tr>
                          <th scope="col" className="table-header-cell">Column Name</th>
                          <th scope="col" className="table-header-cell">Missing Before</th>
                          <th scope="col" className="table-header-cell">Missing After</th>
                          <th scope="col" className="table-header-cell">Values Imputed</th>
                          <th scope="col" className="table-header-cell">Strategy</th>
                        </tr>
                      </thead>
                      <tbody>
                        {columnsToDisplay.map((colName) => {
                          const beforeInfo = missingBefore[colName] || { missing_count: 0, missing_percentage: 0 }
                          const afterInfo = missingAfter[colName] || { missing_count: 0, missing_percentage: 0 }
                          const numCount = numericalFilled[colName] ?? 0
                          const catCount = categoricalFilled[colName] ?? 0
                          const filledCount = numCount + catCount
                          const strategy = numCount > 0
                            ? 'Numerical Mean'
                            : catCount > 0
                            ? 'Categorical Mode'
                            : beforeInfo.missing_count > 0 && afterInfo.missing_count === beforeInfo.missing_count
                            ? 'Skipped (All Null)'
                            : 'None Needed'

                          return (
                            <tr key={colName} className="table-row">
                              <td className="table-cell font-semibold">{colName}</td>
                              <td className="table-cell">
                                {beforeInfo.missing_count.toLocaleString()}{' '}
                                <span className="text-muted">({beforeInfo.missing_percentage}%)</span>
                              </td>
                              <td className="table-cell">
                                <span className={afterInfo.missing_count === 0 ? 'text-emerald-400' : 'text-amber-400'}>
                                  {afterInfo.missing_count.toLocaleString()} ({afterInfo.missing_percentage}%)
                                </span>
                              </td>
                              <td className="table-cell font-semibold text-emerald-400">
                                {filledCount > 0 ? `+${filledCount.toLocaleString()}` : '0'}
                              </td>
                              <td className="table-cell">
                                <span className="audit-pill">{strategy}</span>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                {(skippedNumerical.length > 0 || skippedCategorical.length > 0) && (
                  <div className="table-skipped-notice">
                    <Info className="w-4 h-4 text-amber-400 mr-2 flex-shrink-0" />
                    <span>
                      Columns skipped from imputation (100% missing):{' '}
                      {[...skippedNumerical, ...skippedCategorical].join(', ')}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab 3: Outlier Detection (IQR Method) */}
          {activeTab === 'outliers' && (
            <div className="cleaning-tab-content">
              <div className="cleaning-table-card">
                <div className="table-card-header">
                  <div>
                    <h4 className="table-card-title">Interquartile Range (IQR) Outlier Audit</h4>
                    <p className="table-card-desc">
                      Outliers are calculated as values outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR]. Outliers are flagged for reporting but preserved in the cleaned dataset to avoid discarding legitimate extreme values.
                    </p>
                  </div>
                </div>

                {outlierEntries.length === 0 ? (
                  <div className="cleaning-card-empty">
                    <Layers className="w-8 h-8 text-blue-400 mb-2" />
                    <p className="font-semibold">No Numerical Columns</p>
                    <p className="text-muted text-xs">
                      This dataset does not contain numerical columns eligible for IQR outlier analysis.
                    </p>
                  </div>
                ) : (
                  <div className="table-scroll-wrap">
                    <table className="dataset-table" aria-label="Outlier Detection Breakdown">
                      <thead>
                        <tr>
                          <th scope="col" className="table-header-cell">Numerical Column</th>
                          <th scope="col" className="table-header-cell">Outliers Detected</th>
                          <th scope="col" className="table-header-cell">Outlier Rate</th>
                          <th scope="col" className="table-header-cell">Lower Bound (Q1 - 1.5*IQR)</th>
                          <th scope="col" className="table-header-cell">Upper Bound (Q3 + 1.5*IQR)</th>
                          <th scope="col" className="table-header-cell">Handling Policy</th>
                        </tr>
                      </thead>
                      <tbody>
                        {outlierEntries.map(([colName, info]) => {
                          const count = info.outlier_count || 0
                          const rate = originalRows > 0 ? ((count / originalRows) * 100).toFixed(2) : '0.00'
                          return (
                            <tr key={colName} className="table-row">
                              <td className="table-cell font-semibold">
                                <div className="flex items-center gap-1.5">
                                  <Hash className="w-3.5 h-3.5 text-blue-400" />
                                  {colName}
                                </div>
                              </td>
                              <td className="table-cell font-semibold text-blue-400">
                                {count.toLocaleString()}
                              </td>
                              <td className="table-cell">{rate}%</td>
                              <td className="table-cell font-mono text-xs">
                                {typeof info.lower_bound === 'number' ? info.lower_bound.toFixed(2) : String(info.lower_bound)}
                              </td>
                              <td className="table-cell font-mono text-xs">
                                {typeof info.upper_bound === 'number' ? info.upper_bound.toFixed(2) : String(info.upper_bound)}
                              </td>
                              <td className="table-cell">
                                <span className="audit-pill text-blue-300">Report Only (Preserved)</span>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab 4: Date Conversions & Deduplication */}
          {activeTab === 'dates_dedup' && (
            <div className="cleaning-tab-content">
              <div className="cleaning-dual-grid">
                {/* Date Conversions Card */}
                <div className="cleaning-sub-card">
                  <div className="sub-card-header">
                    <Calendar className="w-5 h-5 text-purple-400 mr-2" />
                    <h4 className="sub-card-title">DateTime Conversions</h4>
                  </div>
                  <p className="sub-card-desc">
                    Columns evaluated for datetime compatibility (&gt;80% parseable dates) and converted into ISO 8601 standard datetime format.
                  </p>
                  {convertedDates.length > 0 ? (
                    <div className="converted-dates-list">
                      {convertedDates.map((col) => (
                        <div key={col} className="converted-date-pill">
                          <Calendar className="w-3.5 h-3.5 text-emerald-400 mr-1.5" />
                          <span className="font-semibold">{col}</span>
                          <span className="date-format-tag">ISO Datetime</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="cleaning-card-empty-sm">
                      <p className="text-muted text-xs">No string columns met the datetime threshold for conversion.</p>
                    </div>
                  )}
                </div>

                {/* Deduplication Audit Card */}
                <div className="cleaning-sub-card">
                  <div className="sub-card-header">
                    <CopyCheck className="w-5 h-5 text-emerald-400 mr-2" />
                    <h4 className="sub-card-title">Deduplication Audit</h4>
                  </div>
                  <p className="sub-card-desc">
                    Row-level exact duplicate identification. Matches are purged to prevent skewed statistical distributions.
                  </p>
                  <div className="dedup-stat-summary">
                    <div className="dedup-stat-item">
                      <span className="dedup-stat-label">Duplicates Detected</span>
                      <span className="dedup-stat-val text-amber-400">{duplicatesDetected.toLocaleString()}</span>
                    </div>
                    <div className="dedup-stat-item">
                      <span className="dedup-stat-label">Duplicates Removed</span>
                      <span className="dedup-stat-val text-emerald-400">{duplicatesRemoved.toLocaleString()}</span>
                    </div>
                    <div className="dedup-stat-item">
                      <span className="dedup-stat-label">Duplicate Rate</span>
                      <span className="dedup-stat-val">{duplicatesPercentage}%</span>
                    </div>
                    <div className="dedup-stat-item">
                      <span className="dedup-stat-label">Clean Unique Rows</span>
                      <span className="dedup-stat-val text-purple-400">{cleanedRows.toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
