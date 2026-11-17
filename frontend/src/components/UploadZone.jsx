import { useState, useRef } from 'react'
import {
  Upload,
  FileSpreadsheet,
  CheckCircle2,
  X,
  AlertTriangle,
  RefreshCw,
  Sparkles,
  Loader2,
  Server,
} from 'lucide-react'
import { parseCSV, formatBytes } from '../utils/csvParser'
import { inspectDataset } from '../api/client'

export default function UploadZone({ dataset, onDatasetLoaded, onDatasetCleared }) {
  const [isDragging, setIsDragging] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [loadingStep, setLoadingStep] = useState('')
  const [errorMessage, setErrorMessage] = useState(null)
  const fileInputRef = useRef(null)

  const handleProcessFile = async (file) => {
    setErrorMessage(null)

    if (!file) return

    if (!file.name.toLowerCase().endsWith('.csv')) {
      setErrorMessage('Please select a valid CSV file (.csv).')
      return
    }

    setIsLoading(true)
    setLoadingStep('Reading local CSV preview...')

    try {
      // 1. Read local sample preview (first 10 rows) using FileReader
      const text = await new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = (e) => resolve(e.target.result)
        reader.onerror = () => reject(new Error('Failed to read file locally.'))
        reader.readAsText(file)
      })

      const parsed = parseCSV(text, 10)

      // 2. Call backend POST /inspect endpoint with the actual file
      setLoadingStep('Uploading to FastAPI backend & analyzing full dataset...')
      const report = await inspectDataset(file)

      // 3. Calculate full dataset missing values from the backend report
      const totalMissing = Object.values(report.missing_values || {}).reduce(
        (acc, count) => acc + (Number(count) || 0),
        0
      )

      // 4. Update dataset state with verified backend statistics
      onDatasetLoaded({
        file,
        fileName: file.name,
        fileSize: formatBytes(file.size),
        totalRows: report.rows,
        totalColumns: report.columns,
        missingValues: totalMissing,
        duplicateRows: report.duplicate_rows ?? 0,
        dataTypes: report.data_types || {},
        columnNames: report.column_names || [],
        backendReport: report,
        backendVerified: true,
        headers:
          parsed.headers && parsed.headers.length
            ? parsed.headers
            : report.column_names || [],
        rows: parsed.rows || [],
        loadedAt: new Date().toLocaleTimeString(),
      })
    } catch (err) {
      setErrorMessage(err.message || 'An error occurred while processing the dataset.')
      onDatasetCleared()
    } finally {
      setIsLoading(false)
      setLoadingStep('')
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (!isLoading) {
      setIsDragging(true)
    }
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    if (isLoading) return

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleProcessFile(e.dataTransfer.files[0])
    }
  }

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleProcessFile(e.target.files[0])
    }
  }

  const handleBrowseClick = () => {
    if (isLoading) return
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
      fileInputRef.current.click()
    }
  }

  return (
    <div className="upload-container">
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        className="hidden-file-input"
        onChange={handleFileChange}
        disabled={isLoading}
        aria-label="Upload CSV dataset file"
      />

      {dataset && dataset.fileName ? (
        /* Loaded Dataset Active Card */
        <div className="upload-active-card">
          <div className="upload-active-header">
            <div className="upload-active-icon-box">
              <FileSpreadsheet className="w-6 h-6 text-emerald-400" />
            </div>
            <div className="upload-active-info">
              <div className="upload-filename-row">
                <span className="upload-active-filename">{dataset.fileName}</span>
                <span className="upload-badge-ready">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  {dataset.backendVerified ? 'Backend Verified (FastAPI)' : 'Local File Ready'}
                </span>
              </div>
              <p className="upload-active-meta">
                {dataset.fileSize} • {dataset.totalRows.toLocaleString()} rows •{' '}
                {dataset.totalColumns} columns detected & verified by backend
              </p>
            </div>

            <div className="upload-active-actions">
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={handleBrowseClick}
                disabled={isLoading}
                title="Select another CSV to replace this one"
              >
                <RefreshCw className="w-3.5 h-3.5 mr-1" />
                Replace
              </button>
              <button
                type="button"
                className="btn-danger-ghost btn-sm"
                onClick={onDatasetCleared}
                disabled={isLoading}
                title="Remove current dataset"
                aria-label="Remove uploaded dataset"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="upload-ready-banner">
            <Sparkles className="w-4 h-4 text-purple-400 flex-shrink-0" />
            <span>
              <strong>Backend Inspection Complete:</strong> Full dataset verified across{' '}
              {dataset.totalRows.toLocaleString()} rows. Descriptive statistics, column types, and data quality metrics are active.
            </span>
          </div>
        </div>
      ) : (
        /* Dropzone Card */
        <div
          className={`upload-dropzone ${isDragging ? 'upload-dropzone-active' : ''} ${
            isLoading ? 'upload-dropzone-loading' : ''
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={handleBrowseClick}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              handleBrowseClick()
            }
          }}
          aria-label="Drag and drop your CSV dataset or click to browse files"
          aria-busy={isLoading}
        >
          <div className="dropzone-glow" />
          <div className="dropzone-content">
            {isLoading ? (
              <div className="dropzone-loading-state">
                <div className="dropzone-icon-ring loading-pulse">
                  <Loader2 className="w-7 h-7 text-purple-400 animate-spin" />
                </div>
                <h3 className="dropzone-title">Analyzing Dataset with FastAPI...</h3>
                <p className="dropzone-subtitle">{loadingStep}</p>
                <div className="dropzone-badges">
                  <span className="dropzone-pill">
                    <Server className="w-3 h-3 mr-1 inline text-purple-400" />
                    POST /inspect
                  </span>
                  <span className="dropzone-pill">Full Dataset Inspection</span>
                </div>
              </div>
            ) : (
              <>
                <div className="dropzone-icon-ring">
                  <Upload className="w-6 h-6 text-purple-400 dropzone-icon" />
                </div>

                <h3 className="dropzone-title">
                  {isDragging ? 'Drop CSV File Here' : 'Upload CSV Dataset'}
                </h3>

                <p className="dropzone-subtitle">
                  Drag and drop your dataset file here, or{' '}
                  <span className="dropzone-browse-link">browse files</span>
                </p>

                <div className="dropzone-badges">
                  <span className="dropzone-pill">Format: .CSV</span>
                  <span className="dropzone-pill">Backend Verified (FastAPI)</span>
                  <span className="dropzone-pill">Tested on Sample - Superstore.csv</span>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {errorMessage && (
        <div className="upload-error-alert" role="alert">
          <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0" />
          <div className="error-text-content">
            <span className="error-title">Upload & Inspection Error</span>
            <p className="error-detail">{errorMessage}</p>
          </div>
          <button
            type="button"
            className="error-dismiss-btn"
            onClick={() => setErrorMessage(null)}
            aria-label="Dismiss error"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  )
}
