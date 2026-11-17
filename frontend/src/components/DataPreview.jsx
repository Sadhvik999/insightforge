import { useState } from 'react'
import {
  TableProperties,
  Search,
  Hash,
  Type,
  Calendar,
  FileSpreadsheet,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react'

export default function DataPreview({ dataset, onTriggerUpload }) {
  const [searchTerm, setSearchTerm] = useState('')

  const headers = dataset?.headers || []
  const rows = dataset?.rows || []
  const dataTypes = dataset?.dataTypes || {}
  const hasData = dataset && headers.length > 0

  // Filter preview rows based on search term
  const filteredRows = hasData
    ? rows.filter((row) => {
        if (!searchTerm) return true
        const term = searchTerm.toLowerCase()
        return Object.values(row).some((val) =>
          String(val).toLowerCase().includes(term)
        )
      })
    : []

  // Determine column data type from backend report or fallback
  const getColTypeInfo = (colName) => {
    const rawType = (dataTypes[colName] || '').toLowerCase()
    if (rawType.includes('int') || rawType.includes('float') || rawType.includes('numeric')) {
      return { kind: 'numeric', label: rawType || 'numeric' }
    }
    if (rawType.includes('date') || rawType.includes('time')) {
      return { kind: 'date', label: rawType || 'datetime' }
    }
    if (rawType) {
      return { kind: 'text', label: rawType }
    }

    // Fallback if no backend type available
    if (!rows.length) return { kind: 'text', label: 'text' }
    const sample = rows[0][colName]
    if (sample === undefined || sample === '') return { kind: 'text', label: 'text' }
    return !isNaN(Number(sample))
      ? { kind: 'numeric', label: 'numeric' }
      : { kind: 'text', label: 'text' }
  }

  return (
    <section className="preview-card" aria-labelledby="preview-heading">
      <div className="preview-header">
        <div className="preview-header-left">
          <div className="preview-icon-wrap">
            <TableProperties className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <div className="preview-title-row">
              <h2 id="preview-heading" className="preview-title">Dataset Preview</h2>
              {dataset?.backendVerified && (
                <span className="preview-verified-badge" title="Schema and row counts verified by FastAPI">
                  <ShieldCheck className="w-3.5 h-3.5 mr-1 text-emerald-400" />
                  Backend Verified
                </span>
              )}
            </div>
            <p className="preview-subtitle">
              {hasData
                ? `Local preview of top ${rows.length} sample rows • Full dataset has ${dataset.totalRows.toLocaleString()} rows & ${dataset.totalColumns} columns`
                : 'Upload a CSV dataset above to view schema and preview data'}
            </p>
          </div>
        </div>

        {hasData && (
          <div className="preview-search-wrap">
            <Search className="w-4 h-4 preview-search-icon" />
            <input
              type="text"
              placeholder="Filter sample rows..."
              className="preview-search-input"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              aria-label="Filter sample preview rows"
            />
            {searchTerm && (
              <span className="search-count-badge">
                {filteredRows.length} matches
              </span>
            )}
          </div>
        )}
      </div>

      {!hasData ? (
        /* Empty State */
        <div className="preview-empty-state">
          <div className="empty-state-icon-box">
            <FileSpreadsheet className="w-10 h-10 text-purple-400" />
          </div>
          <h3 className="empty-state-title">No dataset loaded</h3>
          <p className="empty-state-description">
            Your tabular data preview will appear here once you select or drag-and-drop a CSV dataset in the upload section above.
          </p>
          <button
            type="button"
            className="btn-primary btn-sm"
            onClick={onTriggerUpload}
          >
            Upload CSV to Preview
            <ArrowRight className="w-4 h-4 ml-1.5" />
          </button>
        </div>
      ) : (
        /* Data Table */
        <div className="table-responsive-container">
          <div className="table-scroll-wrap">
            <table className="dataset-table" aria-label="Dataset Preview Rows">
              <thead>
                <tr>
                  <th scope="col" className="table-col-index">#</th>
                  {headers.map((colName) => {
                    const typeInfo = getColTypeInfo(colName)
                    return (
                      <th key={colName} scope="col" className="table-header-cell">
                        <div className="col-header-inner">
                          <span className="col-type-icon">
                            {typeInfo.kind === 'numeric' && (
                              <Hash className="w-3 h-3 text-blue-400" title={`Numeric: ${typeInfo.label}`} />
                            )}
                            {typeInfo.kind === 'date' && (
                              <Calendar className="w-3 h-3 text-amber-400" title={`DateTime: ${typeInfo.label}`} />
                            )}
                            {typeInfo.kind === 'text' && (
                              <Type className="w-3 h-3 text-purple-400" title={`Text: ${typeInfo.label}`} />
                            )}
                          </span>
                          <span className="col-header-title">{colName}</span>
                          <span className="col-header-dtype" title={`Pandas dtype: ${typeInfo.label}`}>
                            {typeInfo.label}
                          </span>
                        </div>
                      </th>
                    )
                  })}
                </tr>
              </thead>
              <tbody>
                {filteredRows.length > 0 ? (
                  filteredRows.map((row, idx) => (
                    <tr key={idx} className="table-row">
                      <td className="table-cell-index">{idx + 1}</td>
                      {headers.map((colName) => {
                        const val = row[colName]
                        const isNull = val === '' || val === null || val === undefined
                        return (
                          <td
                            key={colName}
                            className={`table-cell ${isNull ? 'table-cell-null' : ''}`}
                          >
                            {isNull ? <span className="null-tag">null</span> : val}
                          </td>
                        )
                      })}
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={headers.length + 1} className="table-no-results">
                      No sample rows matched your search term "{searchTerm}".
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="table-footer-meta">
            <span>
              Showing first {Math.min(rows.length, filteredRows.length)} sample rows for client performance. Full dataset ({dataset.totalRows.toLocaleString()} rows) verified by FastAPI.
            </span>
            <span className="dataset-source-tag">Source: Local Preview • Backend Verified</span>
          </div>
        </div>
      )}
    </section>
  )
}
