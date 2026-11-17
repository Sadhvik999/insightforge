/**
 * Lightweight client-side CSV parser for local preview and metrics calculation.
 * Zero external dependencies; safely handles quoted fields, newlines, and commas.
 */
export function parseCSV(csvText, maxPreviewRows = 10) {
  if (!csvText || typeof csvText !== 'string' || !csvText.trim()) {
    return {
      headers: [],
      rows: [],
      totalRows: 0,
      totalColumns: 0,
      missingCount: 0,
    }
  }

  // Split into lines while handling CRLF, LF, CR
  const lines = csvText.split(/\r\n|\n|\r/)
  const nonEmptyLines = lines.filter((l) => l.trim().length > 0)

  if (nonEmptyLines.length === 0) {
    return {
      headers: [],
      rows: [],
      totalRows: 0,
      totalColumns: 0,
      missingCount: 0,
    }
  }

  // Parse a single CSV row respecting quoted values and escaped quotes
  function parseRow(line) {
    const values = []
    let current = ''
    let inQuotes = false

    for (let i = 0; i < line.length; i++) {
      const char = line[i]
      if (char === '"') {
        if (inQuotes && line[i + 1] === '"') {
          current += '"'
          i++
        } else {
          inQuotes = !inQuotes
        }
      } else if (char === ',' && !inQuotes) {
        values.push(current.trim())
        current = ''
      } else {
        current += char
      }
    }
    values.push(current.trim())
    return values
  }

  // First line is headers
  const rawHeaders = parseRow(nonEmptyLines[0])
  const headers = rawHeaders.map(
    (h, idx) => h.replace(/^["']|["']$/g, '').trim() || `Column_${idx + 1}`
  )

  const totalRows = Math.max(0, nonEmptyLines.length - 1)
  const previewSlice = nonEmptyLines.slice(1, maxPreviewRows + 1)

  let sampleMissingCount = 0

  const rows = previewSlice.map((line) => {
    const vals = parseRow(line)
    const rowObj = {}
    headers.forEach((h, i) => {
      const val = vals[i] !== undefined ? vals[i].replace(/^["']|["']$/g, '').trim() : ''
      rowObj[h] = val
      if (val === '' || val.toLowerCase() === 'null' || val.toLowerCase() === 'nan') {
        sampleMissingCount++
      }
    })
    return rowObj
  })

  return {
    headers,
    rows,
    totalRows,
    totalColumns: headers.length,
    missingCount: sampleMissingCount,
  }
}

/**
 * Format bytes to human readable string (KB, MB).
 */
export function formatBytes(bytes, decimals = 1) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}
