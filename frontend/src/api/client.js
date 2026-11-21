/**
 * InsightForge Reusable API Client
 * Connects the React frontend to the local FastAPI backend (http://127.0.0.1:8000).
 * Handles multipart/form-data upload without manual Content-Type override.
 */

export const API_BASE_URL =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) ||
  'http://127.0.0.1:8000'

/**
 * Format network and connection errors with actionable diagnostics.
 */
function formatNetworkError(err) {
  if (
    err instanceof TypeError &&
    (err.message.includes('fetch') ||
      err.message.includes('NetworkError') ||
      err.message.includes('Failed to fetch'))
  ) {
    return new Error(
      `Backend Unavailable: Unable to connect to InsightForge API at ${API_BASE_URL}. Please ensure the FastAPI server is running (e.g. uvicorn app.main:app).`
    )
  }
  return err
}

/**
 * Check whether the FastAPI backend is running and healthy.
 * GET /health
 */
export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
    })

    if (!res.ok) {
      throw new Error(`Health check returned HTTP ${res.status}`)
    }

    return await res.json()
  } catch (err) {
    throw formatNetworkError(err)
  }
}

/**
 * Inspect a dataset by uploading a CSV file to the backend.
 * POST /inspect (multipart/form-data with field 'file')
 */
export async function inspectDataset(file) {
  if (!file) {
    throw new Error('No dataset file provided for inspection.')
  }

  if (!file.name.toLowerCase().endsWith('.csv')) {
    throw new Error('Only CSV files are supported (.csv).')
  }

  const formData = new FormData()
  formData.append('file', file)

  try {
    const res = await fetch(`${API_BASE_URL}/inspect`, {
      method: 'POST',
      body: formData,
      // Note: Do not manually set Content-Type header; the browser automatically adds multipart boundary.
    })

    if (!res.ok) {
      let detail = `Inspection failed with status ${res.status}`
      try {
        const errorData = await res.json()
        if (errorData?.detail) {
          detail = errorData.detail
        }
      } catch {
        // Fallback to default message
      }
      const err = new Error(detail)
      err.status = res.status
      throw err
    }

    return await res.json()
  } catch (err) {
    throw formatNetworkError(err)
  }
}

/**
 * Clean a dataset using the backend's data-cleaning engine.
 * POST /clean (multipart/form-data with field 'file')
 */
export async function cleanDataset(
  file,
  {
    threshold = 75,
    numericalStrategy = 'median',
    outlierTreatment = 'detect',
    removeDuplicates = true,
    approvedDropColumns = [],
  } = {}
) {
  if (!file) {
    throw new Error('No dataset file provided for cleaning.')
  }

  if (!file.name.toLowerCase().endsWith('.csv')) {
    throw new Error('Only CSV files are supported (.csv).')
  }

  const formData = new FormData()
  formData.append('file', file)
  formData.append('threshold', String(threshold))
  formData.append('numerical_strategy', String(numericalStrategy))
  formData.append('outlier_treatment', String(outlierTreatment))
  formData.append('remove_duplicates', String(removeDuplicates))

  if (approvedDropColumns && approvedDropColumns.length > 0) {
    formData.append(
      'approved_drop_columns',
      JSON.stringify(approvedDropColumns)
    )
  }

  try {
    const res = await fetch(`${API_BASE_URL}/clean`, {
      method: 'POST',
      body: formData,
    })

    if (!res.ok) {
      let detail = `Cleaning failed with status ${res.status}`
      try {
        const errorData = await res.json()
        if (errorData?.detail) {
          detail = errorData.detail
        }
      } catch {
        // Fallback
      }
      const err = new Error(detail)
      err.status = res.status
      throw err
    }

    return await res.json()
  } catch (err) {
    throw formatNetworkError(err)
  }
}

/**
 * Run context-aware natural language analysis or visualization.
 * POST /analyze (FormData: question, file [optional], conversation_id [optional], session_id [optional])
 */
export async function analyzeDataset({ question, file, conversationId, sessionId, isRetry = false } = {}) {
  if (!question || !question.trim()) {
    throw new Error('Question cannot be empty.')
  }

  const headers = {}
  const formData = new FormData()
  formData.append('question', question.trim())

  if (conversationId) {
    formData.append('conversation_id', conversationId)
  }

  if (sessionId) {
    const cleanSessionId = String(sessionId).trim()
    formData.append('session_id', cleanSessionId)
    headers['X-Session-ID'] = cleanSessionId
  }

  if (file) {
    formData.append('file', file)
  }

  try {
    const res = await fetch(`${API_BASE_URL}/analyze`, {
      method: 'POST',
      headers,
      body: formData,
    })

    if (!res.ok) {
      let detail = `Analysis failed with status ${res.status}`
      try {
        const errorData = await res.json()
        if (errorData?.detail) {
          detail = errorData.detail
        }
      } catch {
        // Fallback
      }

      // Auto-heal: If an unissued or expired session token was rejected,
      // retry once without the stale session ID so visualization/analysis succeeds.
      if (
        res.status === 400 &&
        (detail.includes('Invalid or unissued session token') || detail.includes('expired')) &&
        !isRetry
      ) {
        return analyzeDataset({
          question,
          file,
          conversationId,
          sessionId: null,
          isRetry: true,
        })
      }

      const err = new Error(detail)
      err.status = res.status
      throw err
    }

    return await res.json()
  } catch (err) {
    throw formatNetworkError(err)
  }
}

/**
 * Download the cleaned dataset CSV file from the backend.
 * GET /clean/download/{download_id} (or via downloadUrl)
 * Handles Blob response, triggers browser download, and revokes temporary object URL.
 *
 * @param {string} downloadUrlOrId - Backend download endpoint URL or download ID
 * @param {string} [fallbackFilename='cleaned_dataset.csv'] - Fallback filename
 * @returns {Promise<{ success: boolean, filename: string, blob: Blob }>}
 */
export async function downloadCleanedDataset(downloadUrlOrId, fallbackFilename) {
  if (!downloadUrlOrId || typeof downloadUrlOrId !== 'string' || !downloadUrlOrId.trim()) {
    throw new Error('No download URL or download ID provided.')
  }

  const cleanTarget = downloadUrlOrId.trim()
  let requestUrl
  if (cleanTarget.startsWith('http://') || cleanTarget.startsWith('https://')) {
    requestUrl = cleanTarget
  } else if (cleanTarget.startsWith('/')) {
    requestUrl = `${API_BASE_URL}${cleanTarget}`
  } else {
    requestUrl = `${API_BASE_URL}/clean/download/${encodeURIComponent(cleanTarget)}`
  }

  try {
    const res = await fetch(requestUrl, {
      method: 'GET',
    })

    if (!res.ok) {
      let detail = `Download failed with status ${res.status}`
      if (res.status === 404) {
        detail = 'Cleaned dataset download has expired or was not found. Please re-run the cleaning pipeline.'
      }
      try {
        const errorData = await res.json()
        if (errorData?.detail) {
          detail = errorData.detail
        }
      } catch {
        // Fallback
      }
      const err = new Error(detail)
      err.status = res.status
      throw err
    }

    // Determine filename from Content-Disposition header if available
    let filename = fallbackFilename
    const disposition = res.headers.get('content-disposition')
    if (disposition) {
      const match = disposition.match(/filename\*?=['"]?(?:UTF-8'')?([^;"'\n]*)['"]?/i)
      if (match && match[1]) {
        filename = decodeURIComponent(match[1].trim())
      }
    }
    if (!filename) {
      filename = 'cleaned_dataset.csv'
    }

    const blob = await res.blob()

    // Trigger browser file download if in a browser DOM environment
    if (typeof window !== 'undefined' && typeof document !== 'undefined' && document.createElement) {
      const objectUrl = window.URL.createObjectURL(blob)
      try {
        const a = document.createElement('a')
        a.style.display = 'none'
        a.href = objectUrl
        a.download = filename
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
      } finally {
        window.URL.revokeObjectURL(objectUrl)
      }
    }

    return {
      success: true,
      filename,
      blob,
    }
  } catch (err) {
    throw formatNetworkError(err)
  }
}

/**
 * Issue a new cryptographically random session identifier from the backend (or local CSPRNG).
 * POST /config/session
 */
export async function createAISession() {
  try {
    const res = await fetch(`${API_BASE_URL}/config/session`, {
      method: 'POST',
    })
    if (res.ok) {
      const data = await res.json()
      if (data?.session_id) return data.session_id
    }
  } catch {
    // Fallback to local browser CSPRNG if backend is unreachable
  }

  if (typeof crypto !== 'undefined') {
    if (crypto.randomUUID) {
      return crypto.randomUUID().replace(/-/g, '')
    }
    if (crypto.getRandomValues) {
      const bytes = new Uint8Array(16)
      crypto.getRandomValues(bytes)
      return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
    }
  }
  return null
}

/**
 * Test connectivity and authentication for an AI provider.
 * Requires a valid server-issued session ID.
 * POST /config/test
 */
export async function testAIProviderConnection({
  sessionId,
  provider,
  apiKey,
  model,
  baseUrl,
} = {}) {
  const cleanSessionId = sessionId ? String(sessionId).trim() : null
  const payload = {
    session_id: cleanSessionId,
    provider: provider || 'ollama',
    api_key: apiKey ? String(apiKey).trim() : null,
    model: model ? String(model).trim() : null,
    base_url: baseUrl ? String(baseUrl).trim() : null,
  }

  const headers = {
    'Content-Type': 'application/json',
  }
  if (cleanSessionId) {
    headers['X-Session-ID'] = cleanSessionId
  }

  try {
    const res = await fetch(`${API_BASE_URL}/config/test`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    })

    if (!res.ok) {
      let detail = `Connection test failed with status ${res.status}`
      try {
        const errorData = await res.json()
        if (errorData?.detail) {
          detail = errorData.detail
        }
      } catch {
        // Fallback
      }
      const err = new Error(detail)
      err.status = res.status
      throw err
    }

    return await res.json()
  } catch (err) {
    throw formatNetworkError(err)
  }
}

/**
 * Save user AI provider configuration into volatile server session memory.
 * POST /config/save
 */
export async function saveAIProviderConfiguration({
  sessionId,
  provider,
  apiKey,
  model,
  baseUrl,
} = {}) {
  if (!sessionId) {
    throw new Error('A session ID is required to configure AI credentials.')
  }

  const cleanSessionId = String(sessionId).trim()
  const payload = {
    session_id: cleanSessionId,
    provider: provider || 'ollama',
    api_key: apiKey ? String(apiKey).trim() : null,
    model: model ? String(model).trim() : null,
    base_url: baseUrl ? String(baseUrl).trim() : null,
  }

  try {
    const res = await fetch(`${API_BASE_URL}/config/save`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': cleanSessionId,
      },
      body: JSON.stringify(payload),
    })

    if (!res.ok) {
      let detail = `Failed to save configuration with status ${res.status}`
      try {
        const errorData = await res.json()
        if (errorData?.detail) {
          detail = errorData.detail
        }
      } catch {
        // Fallback
      }
      const err = new Error(detail)
      err.status = res.status
      throw err
    }

    return await res.json()
  } catch (err) {
    throw formatNetworkError(err)
  }
}

/**
 * Clear custom AI provider configuration for a session (resets to local Ollama).
 * POST /config/clear
 */
export async function clearAIProviderConfiguration(sessionId) {
  if (!sessionId) {
    throw new Error('A session ID is required to clear AI configuration.')
  }

  const cleanSessionId = String(sessionId).trim()
  const payload = {
    session_id: cleanSessionId,
  }

  try {
    const res = await fetch(`${API_BASE_URL}/config/clear`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': cleanSessionId,
      },
      body: JSON.stringify(payload),
    })

    if (!res.ok) {
      let detail = `Failed to clear configuration with status ${res.status}`
      try {
        const errorData = await res.json()
        if (errorData?.detail) {
          detail = errorData.detail
        }
      } catch {
        // Fallback
      }
      const err = new Error(detail)
      err.status = res.status
      throw err
    }

    return await res.json()
  } catch (err) {
    throw formatNetworkError(err)
  }
}

/**
 * Retrieve the current masked AI provider configuration for a session.
 * Transports session ID via X-Session-ID header to avoid query parameter exposure.
 * GET /config/current
 */
export async function getCurrentAIProviderConfiguration(sessionId) {
  const headers = {}
  if (sessionId) {
    headers['X-Session-ID'] = String(sessionId).trim()
  }

  try {
    const res = await fetch(`${API_BASE_URL}/config/current`, {
      method: 'GET',
      headers,
    })

    if (!res.ok) {
      let detail = `Failed to retrieve configuration with status ${res.status}`
      try {
        const errorData = await res.json()
        if (errorData?.detail) {
          detail = errorData.detail
        }
      } catch {
        // Fallback
      }
      const err = new Error(detail)
      err.status = res.status
      throw err
    }

    return await res.json()
  } catch (err) {
    throw formatNetworkError(err)
  }
}
