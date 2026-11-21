import { useState, useMemo } from 'react'
import {
  RefreshCw,
  Loader2,
  XCircle,
  CheckCircle2,
  AlertTriangle,
  FileSpreadsheet,
  ArrowRight,
  Layers,
  SlidersHorizontal,
  Calendar,
  CopyCheck,
  Hash,
  ShieldAlert,
  ShieldCheck,
  Info,
  Trash2,
  Shield,
  CheckSquare,
  Square,
  Settings,
  Database,
  Filter,
  Download,
} from 'lucide-react'
import { cleanDataset, downloadCleanedDataset } from '../api/client'

// Identifier detection regex helper for client-side pre-cleaning preview
const IDENTIFIER_REGEX = /(^|[\s_-])(id|identifier|key|uuid|guid|code|pk|fk|ssn|ein|tin)([\s_-]|$)|[a-z0-9]id$/i

function isIdentifierColumnName(colName) {
  return IDENTIFIER_REGEX.test(String(colName).trim())
}

export default function DataCleaningPanel({
  dataset,
  cleaningResult: externalResult,
  onCleaningResultChange,
  onNavigateToOverview,
}) {
  const [internalResult, setInternalResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('summary') // 'summary', 'intel', 'missing', 'outliers', 'dates_dedup', 'quality'
  const [showAllColumns, setShowAllColumns] = useState(false)

  // Configurable Missingness Threshold (default: 75%)
  const [threshold, setThreshold] = useState(75)

  // Configurable Engine Parameters
  const [numericalStrategy, setNumericalStrategy] = useState('median')
  const [outlierTreatment, setOutlierTreatment] = useState('detect') // 'detect', 'cap', 'remove'
  const [removeDuplicates, setRemoveDuplicates] = useState(true)

  // User-approved columns for removal (list of column names)
  const [approvedDrops, setApprovedDrops] = useState([])

  // Download state management
  const [isDownloading, setIsDownloading] = useState(false)
  const [downloadSuccessMessage, setDownloadSuccessMessage] = useState(null)
  const [downloadErrorMessage, setDownloadErrorMessage] = useState(null)

  // Use external result from parent App state if provided, otherwise internal
  const cleaningResult = externalResult !== undefined ? externalResult : internalResult

  const setCleaningResult = (res) => {
    if (onCleaningResultChange) {
      onCleaningResultChange(res)
    } else {
      setInternalResult(res)
    }
  }

  // Pre-cleaning Missing Value Intelligence analysis computed from dataset schema/inspection
  const preCleaningIntelligence = useMemo(() => {
    if (!dataset || !dataset.columnNames || dataset.totalRows === 0) {
      return {
        columns: {},
        recommendedDropColumns: [],
        reviewColumns: [],
        protectedIdentifierColumns: [],
        lowMissingColumns: [],
        noMissingColumns: [],
      }
    }

    const missingDict = dataset.backendReport?.missing_values || {}
    const dataTypes = dataset.dataTypes || {}
    const totalRows = dataset.totalRows

    const columns = {}
    const recommendedDropColumns = []
    const reviewColumns = []
    const protectedIdentifierColumns = []
    const lowMissingColumns = []
    const noMissingColumns = []

    dataset.columnNames.forEach((col) => {
      const missingCount = Number(missingDict[col]) || 0
      const missingPercentage = totalRows > 0 ? Number(((missingCount / totalRows) * 100).toFixed(2)) : 0
      const isId = isIdentifierColumnName(col)
      const rawType = String(dataTypes[col] || '').toLowerCase()
      const isNumeric = rawType.includes('int') || rawType.includes('float') || rawType.includes('numeric')

      let classification
      let recommendedAction
      let recommendationReason

      if (missingCount === 0) {
        classification = 'none'
        recommendedAction = 'no_action'
        recommendationReason = 'Column has 0 missing values. No cleaning action required.'
        noMissingColumns.push(col)
      } else if (missingPercentage <= 30.0) {
        classification = 'low'
        recommendedAction = 'impute'
        recommendationReason = `Missingness is low (${missingPercentage}% <= 30%). Eligible for automated ${isNumeric ? numericalStrategy : 'mode'} imputation.`
        lowMissingColumns.push(col)
      } else if (missingPercentage < threshold) {
        classification = 'moderate'
        recommendedAction = 'review'
        recommendationReason = `Missingness is moderate (${missingPercentage}%). Exceeds 30% standard limit but below ${threshold}% threshold. Retained and imputed.`
        reviewColumns.push(col)
      } else {
        // missingPercentage >= threshold: MANDATORY DROP RULE
        classification = 'high'
        recommendedAction = 'drop'
        recommendationReason = `Column has ${missingPercentage}% missing values (>= ${threshold}% threshold). Mandatory rule: drop the entire column${isId ? ' (including identifier columns)' : ''}.`
        recommendedDropColumns.push(col)
      }

      if (isId && missingCount > 0 && missingPercentage < threshold) {
        protectedIdentifierColumns.push(col)
      }

      columns[col] = {
        columnName: col,
        dataType: dataTypes[col] || 'unknown',
        isNumeric,
        isIdentifier: isId,
        missingCount,
        missingPercentage,
        classification,
        recommendedAction,
        recommendationReason,
      }
    })

    return {
      columns,
      recommendedDropColumns,
      reviewColumns,
      protectedIdentifierColumns,
      lowMissingColumns,
      noMissingColumns,
    }
  }, [dataset, threshold, numericalStrategy])

  // Toggle approval for dropping a specific column
  const toggleColumnApproval = (colName) => {
    setApprovedDrops((prev) =>
      prev.includes(colName) ? prev.filter((c) => c !== colName) : [...prev, colName]
    )
  }

  // Bulk actions for column approval
  const handleApproveAllRecommended = () => {
    setApprovedDrops([...preCleaningIntelligence.recommendedDropColumns])
  }

  const handleRejectAll = () => {
    setApprovedDrops([])
  }

  const hasDownloadRef = Boolean(
    cleaningResult && (cleaningResult.download_url || cleaningResult.download_id)
  )
  const canDownload = Boolean(hasDownloadRef && !isDownloading)

  const handleDownloadCleaned = async () => {
    if (isDownloading) return

    const downloadRef = cleaningResult?.download_url || cleaningResult?.download_id
    if (!downloadRef) {
      setDownloadErrorMessage('No download reference available. Please run the cleaning pipeline first.')
      return
    }

    setIsDownloading(true)
    setDownloadSuccessMessage(null)
    setDownloadErrorMessage(null)

    const fallbackName =
      cleaningResult?.download_filename ||
      (dataset?.fileName
        ? `${dataset.fileName.replace(/\.csv$/i, '')}_cleaned.csv`
        : 'cleaned_dataset.csv')

    try {
      const res = await downloadCleanedDataset(downloadRef, fallbackName)
      setDownloadSuccessMessage(`Cleaned dataset downloaded successfully as ${res.filename}`)
    } catch (err) {
      setDownloadErrorMessage(err.message || 'Failed to download cleaned dataset.')
    } finally {
      setIsDownloading(false)
    }
  }

  const handleRunCleaning = async () => {
    if (!dataset?.file) {
      setError('No dataset file found. Please upload a CSV dataset from the Overview tab.')
      return
    }

    setIsLoading(true)
    setError(null)
    setDownloadSuccessMessage(null)
    setDownloadErrorMessage(null)

    try {
      const response = await cleanDataset(dataset.file, {
        threshold,
        numericalStrategy,
        outlierTreatment,
        removeDuplicates,
        approvedDropColumns: approvedDrops,
      })
      setCleaningResult(response)
    } catch (err) {
      setError(err.message || 'Cleaning pipeline failed. Please ensure the backend server is reachable.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleClearReport = () => {
    setCleaningResult(null)
    setApprovedDrops([])
    setError(null)
    setDownloadSuccessMessage(null)
    setDownloadErrorMessage(null)
  }

  // Pre-cleaning explanation cards
  const cleaningModules = [
    {
      title: 'Mandatory Missing-Value Engine',
      desc: `Strict rule: columns with >= ${threshold}% missing values are completely dropped (including sparse identifier columns). Columns < ${threshold}% are retained and imputed.`,
      icon: ShieldAlert,
      status: `Active (>= ${threshold}% Threshold)`,
    },
    {
      title: 'Type-Safe Imputation',
      desc: `Numerical columns imputed using ${numericalStrategy} (median default). Categorical columns imputed using mode with 'Unknown' fallback. Datetime columns safely preserved.`,
      icon: Layers,
      status: `${numericalStrategy} / mode Active`,
    },
    {
      title: 'IQR Outlier Treatment',
      desc: `Detects values outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR]. Current mode: ${outlierTreatment === 'detect' ? 'Detection Only (Default)' : outlierTreatment === 'cap' ? 'Cap Values (Winsorization)' : 'Remove Outlier Rows'}.`,
      icon: Hash,
      status: `${outlierTreatment.toUpperCase()} Mode`,
    },
    {
      title: 'Deduplication & Format Engine',
      desc: `Row-level exact duplicate identification and removal (preserving first occurrence) with mixed datetime standardization to ISO 8601.`,
      icon: Calendar,
      status: removeDuplicates ? 'Deduplication ON' : 'Deduplication OFF',
    },
  ]

  // Extract metrics from backend response
  const originalRows = cleaningResult?.original_rows ?? dataset?.totalRows ?? 0
  const cleanedRows = cleaningResult?.cleaned_rows ?? 0
  const originalCols = cleaningResult?.original_columns ?? dataset?.totalColumns ?? 0
  const cleanedCols = cleaningResult?.cleaned_columns ?? (cleaningResult?.columns?.length ?? 0)
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

  // Missing Value Intelligence summary from backend report
  const mviReport = report.missing_value_intelligence || {}
  const mviColumns = mviReport.columns || {}
  const mviSummary = mviReport.summary || {}
  const appliedThreshold = mviReport.threshold ?? threshold

  const columnsActuallyRemoved = mviSummary.columns_actually_removed || mviReport.columns_actually_removed || report.columns_dropped || []
  const columnsPreserved = mviSummary.columns_preserved || mviReport.columns_preserved || []
  const highMissingnessColumns = mviSummary.high_missingness_columns || mviReport.high_missingness_columns || []

  // Data Quality checks
  const qualityChecks = report.quality_checks || {}
  const emptyRowsRemoved = report.empty_rows_removed || 0
  const constantCols = qualityChecks.constant_columns || []
  const nearConstantCols = Object.keys(qualityChecks.near_constant_columns || {})
  const duplicateCols = qualityChecks.duplicate_columns || []

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
            <SlidersHorizontal className="w-6 h-6 text-blue-400" />
          </div>
          <div className="intro-title-wrap">
            <h2 className="intro-title">Rule-Based Data Cleaning Studio</h2>
            <p className="intro-subtitle">
              Configurable 11-stage pipeline: mandatory &gt;= {threshold}% column drop rule, robust median/mode imputation, IQR outlier treatment, and deduplication
            </p>
          </div>
          <div className="header-action-wrap flex items-center gap-2">
            <button
              type="button"
              className="btn-primary"
              onClick={handleRunCleaning}
              disabled={isLoading || !dataset?.file}
              title={
                !dataset?.file
                  ? 'Upload a CSV dataset in Overview first'
                  : 'Execute Data Cleaning Pipeline with current configuration'
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
                  <SlidersHorizontal className="w-4 h-4 mr-2" />
                  Run Complete Cleaning
                </>
              )}
            </button>
            <button
              type="button"
              className={`btn-header-download ${canDownload ? 'btn-header-download-active' : 'btn-header-download-disabled'}`}
              onClick={handleDownloadCleaned}
              disabled={!canDownload}
              title={
                !cleaningResult
                  ? 'Run cleaning first to enable download'
                  : isDownloading
                  ? 'Downloading cleaned CSV...'
                  : 'Download cleaned dataset as CSV'
              }
              aria-label="Download Cleaned CSV"
            >
              {isDownloading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Downloading...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4 mr-2" />
                  Download Cleaned CSV
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
            <span className="strip-label">Original Dimension:</span>
            <span className="strip-val">
              {hasData ? `${dataset.totalRows.toLocaleString()} rows × ${dataset.totalColumns} cols` : '--'}
            </span>
          </div>
          <div className="strip-item">
            <span className="strip-label">Drop Rule:</span>
            <span className="strip-val text-rose-400 font-mono font-bold">
              &gt;= {threshold}% Missing (Drop)
            </span>
          </div>
          <div className="strip-item">
            <span className="strip-label">Pipeline Status:</span>
            {isLoading ? (
              <span className="strip-val text-amber-400 animate-pulse">Running Pipeline...</span>
            ) : cleaningResult ? (
              <span className="strip-val text-emerald-400">Cleaned &amp; Audited</span>
            ) : error ? (
              <span className="strip-val text-rose-400">Pipeline Failed</span>
            ) : (
              <span className="strip-val text-purple-400">
                {dataset?.file ? 'Ready to Execute' : 'Awaiting Dataset'}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 2. Pipeline Configuration Bar */}
      {hasData && (
        <div className="cleaning-config-card">
          <div className="config-card-header">
            <div className="flex items-center gap-2">
              <Settings className="w-4 h-4 text-purple-400" />
              <h4 className="config-card-title">Engine Configuration Controls</h4>
            </div>
            <span className="config-card-desc">Customize cleaning rules before running the pipeline</span>
          </div>

          <div className="cleaning-config-grid">
            {/* Control 1: Missingness Threshold Slider */}
            <div className="config-control-box">
              <div className="config-label-row">
                <span className="config-label">
                  <SlidersHorizontal className="w-3.5 h-3.5 mr-1 text-purple-400" />
                  Drop Threshold (&gt;=):
                </span>
                <span className="threshold-pill font-mono">{threshold}%</span>
                {threshold !== 75 && (
                  <button
                    type="button"
                    className="threshold-reset-btn"
                    onClick={() => setThreshold(75)}
                    title="Reset to 75% default"
                  >
                    Reset (75%)
                  </button>
                )}
              </div>
              <input
                type="range"
                min="10"
                max="95"
                step="5"
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="threshold-slider"
                disabled={isLoading}
                aria-label="Configurable Missingness Threshold"
              />
              <div className="threshold-range-labels">
                <span>10% (Aggressive)</span>
                <span>Default: 75%</span>
                <span>95% (Conservative)</span>
              </div>
            </div>

            {/* Control 2: Numerical Imputation Strategy */}
            <div className="config-control-box">
              <label htmlFor="num-strat-select" className="config-label-row">
                <span className="config-label">
                  <Layers className="w-3.5 h-3.5 mr-1 text-blue-400" />
                  Numerical Strategy:
                </span>
              </label>
              <select
                id="num-strat-select"
                className="config-select"
                value={numericalStrategy}
                onChange={(e) => setNumericalStrategy(e.target.value)}
                disabled={isLoading}
              >
                <option value="median">Median (Default - Robust to outliers)</option>
                <option value="mean">Mean (Parametric average)</option>
              </select>
              <span className="config-hint">Applied to retained numerical columns with &lt; {threshold}% missingness.</span>
            </div>

            {/* Control 3: Outlier Treatment Policy */}
            <div className="config-control-box">
              <label htmlFor="outlier-treat-select" className="config-label-row">
                <span className="config-label">
                  <Filter className="w-3.5 h-3.5 mr-1 text-amber-400" />
                  IQR Outlier Policy:
                </span>
              </label>
              <select
                id="outlier-treat-select"
                className="config-select"
                value={outlierTreatment}
                onChange={(e) => setOutlierTreatment(e.target.value)}
                disabled={isLoading}
              >
                <option value="detect">Detect Only (Default - Preserves data)</option>
                <option value="cap">Cap Values (IQR Bounds Winsorization)</option>
                <option value="remove">Remove Rows (Purge extreme anomalies)</option>
              </select>
              <span className="config-hint">Evaluates [Q1 - 1.5*IQR, Q3 + 1.5*IQR] across numerical columns.</span>
            </div>

            {/* Control 4: Duplicate Rows Removal */}
            <div className="config-control-box">
              <div className="config-label-row">
                <span className="config-label">
                  <CopyCheck className="w-3.5 h-3.5 mr-1 text-emerald-400" />
                  Row Deduplication:
                </span>
              </div>
              <label className="config-toggle-label">
                <input
                  type="checkbox"
                  checked={removeDuplicates}
                  onChange={(e) => setRemoveDuplicates(e.target.checked)}
                  disabled={isLoading}
                  className="config-checkbox"
                />
                <span>Purge Exact Duplicate Rows (Preserve 1st)</span>
              </label>
              <span className="config-hint">Deterministic exact duplicate removal.</span>
            </div>
          </div>
        </div>
      )}

      {/* 3. Loading State Banner */}
      {isLoading && (
        <div className="cleaning-loading-card" role="status" aria-live="polite">
          <div className="loading-card-icon-wrap">
            <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
          </div>
          <div className="loading-card-content">
            <h4 className="loading-card-title">Executing Complete 11-Stage Cleaning Pipeline...</h4>
            <p className="loading-card-desc">
              Normalizing column names, standardizing sentinels (&apos;NA&apos;, &apos;null&apos;, &apos;None&apos;), enforcing mandatory &gt;= {threshold}% column drop rule,
              running {numericalStrategy} numerical imputation, mode categorical imputation, IQR outlier treatment ({outlierTreatment}), and deduplication.
            </p>
          </div>
        </div>
      )}

      {/* 4. Error State Banner */}
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

      {/* 5. Empty State (no dataset uploaded) */}
      {!hasData && !isLoading && (
        <div className="cleaning-empty-card">
          <div className="empty-icon-wrap">
            <FileSpreadsheet className="w-10 h-10 text-purple-400" />
          </div>
          <h3 className="empty-title">No Dataset Loaded</h3>
          <p className="empty-desc">
            To use the Rule-Based Data Cleaning Studio, please upload a CSV dataset from the Overview tab.
            The original CSV file is preserved in memory and all operations run on an immutable copy.
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

      {/* 6. Pre-Clean Rule Preview (Dataset ready, cleaning not yet executed) */}
      {hasData && !cleaningResult && !isLoading && (
        <div className="intel-section-card">
          <div className="intel-section-header">
            <div className="intel-title-group">
              <div className="intel-icon-box">
                <ShieldAlert className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <h3 className="intel-title">Missing Value Intelligence Engine (Rule Preview)</h3>
                <p className="intel-subtitle">
                  Mandatory Rule: Any column with &gt;= {threshold}% missing values is completely dropped upon cleaning.
                  Sparse identifier columns are not exempted.
                </p>
              </div>
            </div>
          </div>

          <div className="intel-body">
            {preCleaningIntelligence.recommendedDropColumns.length > 0 ? (
              <div className="intel-recommendations-wrap">
                <div className="intel-action-bar">
                  <div className="intel-action-summary">
                    <AlertTriangle className="w-4 h-4 text-rose-400 mr-1.5" />
                    <span>
                      <strong>Mandatory Drop Target(s):</strong> {preCleaningIntelligence.recommendedDropColumns.length} column(s) have &gt;= {threshold}% missing values and will be removed upon cleaning.
                    </span>
                  </div>
                  <div className="intel-bulk-actions">
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      onClick={handleApproveAllRecommended}
                      disabled={isLoading}
                    >
                      <CheckSquare className="w-3.5 h-3.5 mr-1.5 text-rose-400" />
                      Acknowledge All ({preCleaningIntelligence.recommendedDropColumns.length})
                    </button>
                    <button
                      type="button"
                      className="btn-ghost btn-sm"
                      onClick={handleRejectAll}
                      disabled={isLoading || approvedDrops.length === 0}
                    >
                      <Square className="w-3.5 h-3.5 mr-1.5" />
                      Reset
                    </button>
                  </div>
                </div>

                <div className="intel-cards-grid">
                  {preCleaningIntelligence.recommendedDropColumns.map((colName) => {
                    const colInfo = preCleaningIntelligence.columns[colName]
                    const isApproved = approvedDrops.includes(colName)

                    return (
                      <div
                        key={colName}
                        className={`intel-column-card ${isApproved ? 'card-approved-drop' : 'card-pending'}`}
                      >
                        <div className="intel-card-header">
                          <div className="intel-col-info">
                            <span className="intel-col-name">{colName}</span>
                            <span className="intel-type-tag">{colInfo.dataType}</span>
                            {colInfo.isIdentifier && (
                              <span className="intel-rec-badge badge-amber">Sparse ID</span>
                            )}
                          </div>
                          <span className="intel-rec-badge badge-drop">Rule: Drop (&gt;= {threshold}%)</span>
                        </div>

                        <div className="intel-metric-row">
                          <div className="intel-stat">
                            <span className="stat-label">Missingness:</span>
                            <span className="stat-val text-rose-400 font-bold">
                              {colInfo.missingPercentage}%
                            </span>
                          </div>
                          <div className="intel-stat">
                            <span className="stat-label">Null Cells:</span>
                            <span className="stat-val">
                              {colInfo.missingCount.toLocaleString()} / {dataset.totalRows.toLocaleString()}
                            </span>
                          </div>
                        </div>

                        <div className="intel-progress-track">
                          <div
                            className="intel-progress-fill"
                            style={{ width: `${Math.min(100, colInfo.missingPercentage)}%` }}
                          />
                        </div>

                        <p className="intel-reason-text">{colInfo.recommendationReason}</p>

                        <div className="intel-decision-footer">
                          <button
                            type="button"
                            className={`decision-btn ${isApproved ? 'btn-approved' : 'btn-unapproved'}`}
                            onClick={() => toggleColumnApproval(colName)}
                            disabled={isLoading}
                          >
                            {isApproved ? (
                              <>
                                <CheckSquare className="w-4 h-4 mr-1.5" />
                                Acknowledged (Will Drop)
                              </>
                            ) : (
                              <>
                                <Square className="w-4 h-4 mr-1.5" />
                                Acknowledge Drop Rule
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ) : (
              <div className="intel-all-clear-card">
                <CheckCircle2 className="w-5 h-5 text-emerald-400 mr-2 flex-shrink-0" />
                <div>
                  <h5 className="all-clear-title">All Columns Below {threshold}% Missing Threshold</h5>
                  <p className="all-clear-desc">
                    All {dataset.totalColumns} columns have missing values strictly below the configured {threshold}% drop threshold.
                    No columns will be removed by the mandatory rule. Automated imputation will be safely applied.
                  </p>
                </div>
              </div>
            )}

            {preCleaningIntelligence.reviewColumns.length > 0 && (
              <div className="intel-review-strip">
                <Info className="w-4 h-4 text-blue-400 mr-2 flex-shrink-0" />
                <span>
                  <strong>Columns with Moderate Missingness (30% to {threshold}%):</strong>{' '}
                  {preCleaningIntelligence.reviewColumns.map((c) => (
                    <span key={c} className="review-col-pill">
                      {c} ({preCleaningIntelligence.columns[c].missingPercentage}%)
                    </span>
                  ))}
                  . Retained and safely imputed.
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 7. Pre-Clean Standard Module Cards */}
      {hasData && !cleaningResult && !isLoading && (
        <div className="cleaning-modules-grid">
          {cleaningModules.map((mod, i) => {
            const Icon = mod.icon
            return (
              <div key={i} className="cleaning-module-card">
                <div className="module-card-icon-wrap">
                  <Icon className="w-5 h-5 text-purple-400" />
                </div>
                <div className="module-card-body">
                  <div className="module-header-row">
                    <h4 className="module-title">{mod.title}</h4>
                    <span className="module-badge">{mod.status}</span>
                  </div>
                  <p className="module-desc">{mod.desc}</p>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 8. Post-Cleaning Audit & Complete Results Dashboard */}
      {cleaningResult && (
        <div className="cleaning-results-wrap">
          {/* Executive Summary Card */}
          <div className="cleaning-summary-banner">
            <div className="summary-banner-left">
              <div className="summary-check-icon">
                <CheckCircle2 className="w-6 h-6 text-emerald-400" />
              </div>
              <div>
                <h3 className="summary-banner-title">Cleaning Pipeline Executed Successfully</h3>
                <p className="summary-banner-desc">
                  Transformed {originalRows.toLocaleString()} rows × {originalCols} columns into{' '}
                  {cleanedRows.toLocaleString()} clean rows × {cleanedCols} columns. Original CSV preserved in memory.
                </p>
              </div>
            </div>
            <div className="summary-banner-actions">
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={handleClearReport}
              >
                Reset Studio
              </button>
            </div>
          </div>

          {/* Prominent Cleaned Dataset Download & Export Card */}
          <div className="cleaned-export-card" role="region" aria-label="Download Cleaned Dataset">
            <div className="export-card-header">
              <div className="export-card-title-wrap">
                <div className="export-icon-box">
                  <Download className="w-5 h-5 text-emerald-400" />
                </div>
                <div>
                  <h4 className="export-card-title">Download Cleaned Dataset</h4>
                  <p className="export-card-subtitle">
                    Export the production-ready CSV reflecting all imputation, deduplication, dropped columns, and outlier treatments.
                  </p>
                </div>
              </div>
              <div className="export-card-actions">
                <button
                  type="button"
                  className="btn-export-download"
                  onClick={handleDownloadCleaned}
                  disabled={!canDownload}
                  aria-label="Download Cleaned Dataset CSV"
                >
                  {isDownloading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Downloading CSV...
                    </>
                  ) : (
                    <>
                      <Download className="w-4 h-4 mr-2" />
                      Download Cleaned Dataset
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* 7 Required Metadata Display Fields */}
            <div className="export-meta-grid">
              <div className="export-meta-item">
                <span className="export-meta-label">Original Filename:</span>
                <span className="export-meta-val font-mono">{dataset?.fileName || 'dataset.csv'}</span>
              </div>
              <div className="export-meta-item">
                <span className="export-meta-label">Download Filename:</span>
                <span className="export-meta-val font-mono text-emerald-300">
                  {cleaningResult?.download_filename || `${dataset?.fileName?.replace(/\.csv$/i, '') || 'dataset'}_cleaned.csv`}
                </span>
              </div>
              <div className="export-meta-item">
                <span className="export-meta-label">Original Row Count:</span>
                <span className="export-meta-val">{originalRows.toLocaleString()}</span>
              </div>
              <div className="export-meta-item">
                <span className="export-meta-label">Cleaned Row Count:</span>
                <span className="export-meta-val text-emerald-400 font-bold">{cleanedRows.toLocaleString()}</span>
              </div>
              <div className="export-meta-item">
                <span className="export-meta-label">Original Column Count:</span>
                <span className="export-meta-val">{originalCols}</span>
              </div>
              <div className="export-meta-item">
                <span className="export-meta-label">Cleaned Column Count:</span>
                <span className="export-meta-val text-emerald-400 font-bold">{cleanedCols}</span>
              </div>
              <div className="export-meta-item">
                <span className="export-meta-label">Cleaning Status:</span>
                <span className="export-meta-val text-emerald-400 flex items-center gap-1.5 font-semibold">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Cleaned &amp; Audited
                </span>
              </div>
            </div>

            {/* Success and Error Notification Banners */}
            {downloadSuccessMessage && (
              <div className="export-status-alert alert-success" role="status">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span className="alert-text">{downloadSuccessMessage}</span>
                <button
                  type="button"
                  className="alert-dismiss-btn"
                  onClick={() => setDownloadSuccessMessage(null)}
                  aria-label="Dismiss success message"
                >
                  &times;
                </button>
              </div>
            )}
            {downloadErrorMessage && (
              <div className="export-status-alert alert-error" role="alert">
                <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <span className="alert-text">{downloadErrorMessage}</span>
                <button
                  type="button"
                  className="alert-dismiss-btn"
                  onClick={() => setDownloadErrorMessage(null)}
                  aria-label="Dismiss error message"
                >
                  &times;
                </button>
              </div>
            )}
          </div>

          {/* 6 Key Performance Indicator Cards */}
          <div className="cleaning-kpi-grid">
            {/* KPI 1: Row Dimensions */}
            <div className="cleaning-kpi-card">
              <div className="kpi-header">
                <span className="kpi-label">Dataset Rows</span>
                <Database className="w-4 h-4 text-purple-400" />
              </div>
              <div className="kpi-comparison-row">
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Original</span>
                  <span className="kpi-val">{originalRows.toLocaleString()}</span>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 kpi-arrow" />
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Cleaned</span>
                  <span className="kpi-val text-emerald-400">{cleanedRows.toLocaleString()}</span>
                </div>
              </div>
              <div className="kpi-footer">
                <span className="kpi-delta-pill">
                  {originalRows - cleanedRows > 0
                    ? `-${(originalRows - cleanedRows).toLocaleString()} rows purged`
                    : 'All rows preserved'}
                </span>
              </div>
            </div>

            {/* KPI 2: Column Dimensions */}
            <div className="cleaning-kpi-card">
              <div className="kpi-header">
                <span className="kpi-label">Columns (&gt;= {appliedThreshold}% Rule)</span>
                <SlidersHorizontal className="w-4 h-4 text-rose-400" />
              </div>
              <div className="kpi-comparison-row">
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Original</span>
                  <span className="kpi-val">{originalCols}</span>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 kpi-arrow" />
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Cleaned</span>
                  <span className="kpi-val text-rose-400">{cleanedCols}</span>
                </div>
              </div>
              <div className="kpi-footer">
                <span className="kpi-delta-pill text-rose-300">
                  {columnsActuallyRemoved.length > 0
                    ? `${columnsActuallyRemoved.length} column(s) dropped`
                    : '0 columns dropped'}
                </span>
              </div>
            </div>

            {/* KPI 3: Missing Values Imputed */}
            <div className="cleaning-kpi-card">
              <div className="kpi-header">
                <span className="kpi-label">Missing Cells Imputed</span>
                <Layers className="w-4 h-4 text-blue-400" />
              </div>
              <div className="kpi-comparison-row">
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Null Before</span>
                  <span className="kpi-val text-rose-400">{totalMissingBefore.toLocaleString()}</span>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 kpi-arrow" />
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Null After</span>
                  <span className="kpi-val text-emerald-400">{totalMissingAfter.toLocaleString()}</span>
                </div>
              </div>
              <div className="kpi-footer">
                <span className="kpi-delta-pill text-emerald-300">
                  +{missingFilledTotal.toLocaleString()} filled ({numericalStrategy}/mode)
                </span>
              </div>
            </div>

            {/* KPI 4: Deduplication */}
            <div className="cleaning-kpi-card">
              <div className="kpi-header">
                <span className="kpi-label">Row Deduplication</span>
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

            {/* KPI 5: Outliers Handled */}
            <div className="cleaning-kpi-card">
              <div className="kpi-header">
                <span className="kpi-label">Outlier Policy ({report.outlier_treatment || outlierTreatment})</span>
                <Hash className="w-4 h-4 text-blue-400" />
              </div>
              <div className="kpi-comparison-row">
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Audited Cols</span>
                  <span className="kpi-val">{outlierEntries.length}</span>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 kpi-arrow" />
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Outliers</span>
                  <span className="kpi-val text-blue-400">{totalOutliers.toLocaleString()}</span>
                </div>
              </div>
              <div className="kpi-footer">
                <span className="kpi-delta-pill text-blue-300">
                  {outlierTreatment === 'cap' ? 'Winsorized to bounds' : outlierTreatment === 'remove' ? 'Rows purged' : 'Detected (Preserved)'}
                </span>
              </div>
            </div>

            {/* KPI 6: Quality Checks */}
            <div className="cleaning-kpi-card">
              <div className="kpi-header">
                <span className="kpi-label">Data Quality Findings</span>
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="kpi-comparison-row">
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Empty Rows</span>
                  <span className="kpi-val">{emptyRowsRemoved}</span>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 kpi-arrow" />
                <div className="kpi-val-group">
                  <span className="kpi-val-sub">Constant</span>
                  <span className="kpi-val text-amber-400">{constantCols.length}</span>
                </div>
              </div>
              <div className="kpi-footer">
                <span className="kpi-delta-pill">
                  {convertedDates.length > 0 ? `${convertedDates.length} date cols standardized` : 'Standardized'}
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
              Before &amp; After Comparison
            </button>
            <button
              type="button"
              className={`cleaning-subtab-btn ${activeTab === 'intel' ? 'active' : ''}`}
              onClick={() => setActiveTab('intel')}
            >
              Missing Value Intelligence Audit ({Object.keys(mviColumns).length})
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
              Date Conversions &amp; Deduplication
            </button>
            <button
              type="button"
              className={`cleaning-subtab-btn ${activeTab === 'quality' ? 'active' : ''}`}
              onClick={() => setActiveTab('quality')}
            >
              Quality &amp; Anomaly Audit
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
                        <td className="table-cell font-semibold">Missing Value Intelligence</td>
                        <td className="table-cell">
                          {highMissingnessColumns.length} high-missingness (&gt;= {appliedThreshold}%)
                        </td>
                        <td className="table-cell font-semibold text-rose-400">
                          {columnsActuallyRemoved.length} dropped, {columnsPreserved.length} preserved
                        </td>
                        <td className="table-cell">
                          {columnsActuallyRemoved.length > 0
                            ? `Dropped: ${columnsActuallyRemoved.join(', ')}`
                            : 'No columns exceeded threshold'}
                        </td>
                        <td className="table-cell">
                          <span className="audit-status-badge badge-success">Enforced (&gt;= {appliedThreshold}%)</span>
                        </td>
                      </tr>
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
                            ? `Imputed ${totalNumericalFilled} numerical (${numericalStrategy}) & ${totalCategoricalFilled} categorical (mode)`
                            : 'No eligible missing values needed imputation'}
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
                        <td className="table-cell font-semibold">Outlier Anomaly Treatment</td>
                        <td className="table-cell">Raw numerical distribution</td>
                        <td className="table-cell text-blue-400 font-semibold">{totalOutliers.toLocaleString()} outliers flagged</td>
                        <td className="table-cell">
                          {report.outlier_treatment === 'cap'
                            ? `Capped ${report.outliers_affected || 0} values to IQR bounds`
                            : report.outlier_treatment === 'remove'
                            ? `Removed ${report.outliers_affected || 0} outlier rows`
                            : 'Audited numerical columns using IQR method; values retained'}
                        </td>
                        <td className="table-cell">
                          <span className="audit-status-badge badge-info">Policy: {report.outlier_treatment || outlierTreatment}</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: Missing Value Intelligence Detailed Audit Table */}
          {activeTab === 'intel' && (
            <div className="cleaning-tab-content">
              <div className="cleaning-table-card">
                <div className="table-card-header">
                  <div>
                    <h4 className="table-card-title">Missing Value Intelligence: Column Classifications &amp; Actions</h4>
                    <p className="table-card-desc">
                      Detailed report showing every column&apos;s missing percentage, classification, recommendation, and actual action performed based on the &gt;= {appliedThreshold}% drop rule.
                    </p>
                  </div>
                </div>

                <div className="table-scroll-wrap">
                  <table className="dataset-table" aria-label="Missing Value Intelligence Report">
                    <thead>
                      <tr>
                        <th scope="col" className="table-header-cell">Column Name</th>
                        <th scope="col" className="table-header-cell">Data Type</th>
                        <th scope="col" className="table-header-cell">Missing Count</th>
                        <th scope="col" className="table-header-cell">Missing %</th>
                        <th scope="col" className="table-header-cell">Classification</th>
                        <th scope="col" className="table-header-cell">Recommended Action</th>
                        <th scope="col" className="table-header-cell">Actual Action Performed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(mviColumns).map(([colName, colInfo]) => {
                        const isDropped = colInfo.actual_action === 'dropped' || columnsActuallyRemoved.includes(colName)

                        return (
                          <tr key={colName} className="table-row">
                            <td className="table-cell font-semibold">
                              <div className="flex items-center gap-1.5">
                                {colInfo.is_identifier && (
                                  <Shield className="w-3.5 h-3.5 text-purple-400" title="Identifier Column" />
                                )}
                                <span className={isDropped ? 'line-through text-rose-400' : ''}>
                                  {colName}
                                </span>
                              </div>
                            </td>
                            <td className="table-cell font-mono text-xs">{colInfo.data_type}</td>
                            <td className="table-cell">{colInfo.missing_count?.toLocaleString()}</td>
                            <td className="table-cell font-bold">
                              <span
                                className={
                                  colInfo.missing_percentage >= appliedThreshold
                                    ? 'text-rose-400'
                                    : colInfo.missing_percentage > 30
                                    ? 'text-amber-400'
                                    : colInfo.missing_percentage > 0
                                    ? 'text-blue-400'
                                    : 'text-slate-400'
                                }
                              >
                                {colInfo.missing_percentage}%
                              </span>
                            </td>
                            <td className="table-cell">
                              <span
                                className={`audit-pill ${
                                  colInfo.classification?.includes('high')
                                    ? 'pill-rose'
                                    : colInfo.classification === 'moderate'
                                    ? 'pill-amber'
                                    : colInfo.classification === 'low'
                                    ? 'pill-blue'
                                    : 'pill-slate'
                                }`}
                              >
                                {colInfo.classification === 'high'
                                  ? 'High (>= Threshold)'
                                  : colInfo.classification === 'moderate'
                                  ? 'Needs Review'
                                  : colInfo.classification === 'low'
                                  ? 'Low Missingness'
                                  : 'None'}
                              </span>
                            </td>
                            <td className="table-cell text-xs text-secondary">
                              {colInfo.recommended_action === 'drop'
                                ? 'Drop Entire Column'
                                : colInfo.recommended_action === 'review'
                                ? 'Review Strategy'
                                : colInfo.recommended_action === 'impute'
                                ? 'Normal Imputation'
                                : 'No Action Needed'}
                            </td>
                            <td className="table-cell">
                              {isDropped ? (
                                <span className="audit-status-badge badge-rose">
                                  <Trash2 className="w-3 h-3 mr-1 inline" /> Dropped (&gt;= {appliedThreshold}%)
                                </span>
                              ) : colInfo.actual_action?.startsWith('imputed_') ? (
                                <span className="audit-status-badge badge-success">
                                  Imputed ({colInfo.actual_action.split('_')[1]})
                                </span>
                              ) : (
                                <span className="audit-status-badge badge-slate">
                                  Preserved
                                </span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Tab 3: Missing Values Imputation */}
          {activeTab === 'missing' && (
            <div className="cleaning-tab-content">
              <div className="cleaning-table-card">
                <div className="table-card-header">
                  <div>
                    <h4 className="table-card-title">Missing Values Imputation Breakdown</h4>
                    <p className="table-card-desc">
                      Total filled: {totalNumericalFilled} numerical values ({numericalStrategy} strategy) and {totalCategoricalFilled} categorical values (mode strategy).
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
                          <th scope="col" className="table-header-cell">Strategy / Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {columnsToDisplay.map((colName) => {
                          const beforeInfo = missingBefore[colName] || { missing_count: 0, missing_percentage: 0 }
                          const afterInfo = missingAfter[colName] || { missing_count: 0, missing_percentage: 0 }
                          const numCount = numericalFilled[colName] ?? 0
                          const catCount = categoricalFilled[colName] ?? 0
                          const filledCount = numCount + catCount
                          const isDropped = columnsActuallyRemoved.includes(colName)

                          let strategy = 'None Needed'
                          if (isDropped) {
                            strategy = `Dropped (>= ${appliedThreshold}%)`
                          } else if (numCount > 0) {
                            strategy = `Numerical (${numericalStrategy})`
                          } else if (catCount > 0) {
                            strategy = 'Categorical (Mode)'
                          } else if (beforeInfo.missing_count > 0 && afterInfo.missing_count === beforeInfo.missing_count) {
                            strategy = 'Skipped (All Null)'
                          }

                          return (
                            <tr key={colName} className="table-row">
                              <td className="table-cell font-semibold">
                                <span className={isDropped ? 'line-through text-rose-400' : ''}>
                                  {colName}
                                </span>
                              </td>
                              <td className="table-cell">
                                {beforeInfo.missing_count.toLocaleString()}{' '}
                                <span className="text-muted">({beforeInfo.missing_percentage}%)</span>
                              </td>
                              <td className="table-cell">
                                {isDropped ? (
                                  <span className="text-rose-400 font-semibold">Column Dropped</span>
                                ) : (
                                  <span className={afterInfo.missing_count === 0 ? 'text-emerald-400' : 'text-amber-400'}>
                                    {afterInfo.missing_count.toLocaleString()} ({afterInfo.missing_percentage}%)
                                  </span>
                                )}
                              </td>
                              <td className="table-cell font-semibold text-emerald-400">
                                {filledCount > 0 ? `+${filledCount.toLocaleString()}` : '0'}
                              </td>
                              <td className="table-cell">
                                <span
                                  className={`audit-pill ${
                                    isDropped ? 'pill-rose' : ''
                                  }`}
                                >
                                  {strategy}
                                </span>
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

          {/* Tab 4: Outlier Detection (IQR Method) */}
          {activeTab === 'outliers' && (
            <div className="cleaning-tab-content">
              <div className="cleaning-table-card">
                <div className="table-card-header">
                  <div>
                    <h4 className="table-card-title">Interquartile Range (IQR) Outlier Audit</h4>
                    <p className="table-card-desc">
                      Bounds: [Q1 - 1.5*IQR, Q3 + 1.5*IQR]. Applied Policy: <strong>{report.outlier_treatment || outlierTreatment}</strong>.
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
                                <span className="audit-pill text-blue-300">
                                  {report.outlier_treatment === 'cap' ? 'Capped (Winsorized)' : report.outlier_treatment === 'remove' ? 'Row Removed' : 'Detected (Preserved)'}
                                </span>
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

          {/* Tab 5: Date Conversions & Deduplication */}
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
                    Columns evaluated for datetime compatibility (&gt;= 80% parseable dates) and converted into ISO 8601 standard datetime format.
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

          {/* Tab 6: Quality & Anomaly Audit */}
          {activeTab === 'quality' && (
            <div className="cleaning-tab-content">
              <div className="cleaning-dual-grid">
                {/* Quality Findings Card */}
                <div className="cleaning-sub-card">
                  <div className="sub-card-header">
                    <ShieldCheck className="w-5 h-5 text-purple-400 mr-2" />
                    <h4 className="sub-card-title">Data Quality Findings</h4>
                  </div>
                  <p className="sub-card-desc">
                    Structural issues, constant columns, and empty rows detected during pipeline execution.
                  </p>
                  <div className="dedup-stat-summary">
                    <div className="dedup-stat-item">
                      <span className="dedup-stat-label">Empty Rows Removed</span>
                      <span className="dedup-stat-val text-emerald-400">{emptyRowsRemoved}</span>
                    </div>
                    <div className="dedup-stat-item">
                      <span className="dedup-stat-label">Constant Columns</span>
                      <span className="dedup-stat-val text-amber-400">{constantCols.length}</span>
                    </div>
                    <div className="dedup-stat-item">
                      <span className="dedup-stat-label">Near-Constant Cols</span>
                      <span className="dedup-stat-val text-blue-400">{nearConstantCols.length}</span>
                    </div>
                    <div className="dedup-stat-item">
                      <span className="dedup-stat-label">Duplicate Col Pairs</span>
                      <span className="dedup-stat-val text-purple-400">{duplicateCols.length}</span>
                    </div>
                  </div>
                  {constantCols.length > 0 && (
                    <div className="mt-3 p-2 bg-amber-500/10 border border-amber-500/20 rounded text-xs text-amber-300">
                      <strong>Constant Columns (Single Value):</strong> {constantCols.join(', ')}
                    </div>
                  )}
                  {nearConstantCols.length > 0 && (
                    <div className="mt-2 p-2 bg-blue-500/10 border border-blue-500/20 rounded text-xs text-blue-300">
                      <strong>Near-Constant Columns (&gt;95% single value):</strong> {nearConstantCols.join(', ')}
                    </div>
                  )}
                </div>

                {/* Audit Actions Executed Card */}
                <div className="cleaning-sub-card">
                  <div className="sub-card-header">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 mr-2" />
                    <h4 className="sub-card-title">Pipeline Actions Executed</h4>
                  </div>
                  <p className="sub-card-desc">
                    Comprehensive log of all transformations applied by the 11-stage cleaning engine.
                  </p>
                  <div className="flex flex-col gap-2 max-h-64 overflow-y-auto pr-1">
                    {(report.actual_actions || []).length > 0 ? (
                      report.actual_actions.map((act, idx) => (
                        <div key={idx} className="p-2 bg-white/5 border border-white/10 rounded text-xs flex items-center gap-2">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                          <span>{act}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-muted text-xs">Dataset was already clean. No destructive actions needed.</p>
                    )}
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
