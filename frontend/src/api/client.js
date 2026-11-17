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
export async function cleanDataset(file) {
  if (!file) {
    throw new Error('No dataset file provided for cleaning.')
  }

  if (!file.name.toLowerCase().endsWith('.csv')) {
    throw new Error('Only CSV files are supported (.csv).')
  }

  const formData = new FormData()
  formData.append('file', file)

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
 * POST /analyze (FormData: question, file [optional], conversation_id [optional])
 */
export async function analyzeDataset({ question, file, conversationId } = {}) {
  if (!question || !question.trim()) {
    throw new Error('Question cannot be empty.')
  }

  const formData = new FormData()
  formData.append('question', question.trim())

  if (conversationId) {
    formData.append('conversation_id', conversationId)
  }

  if (file) {
    formData.append('file', file)
  }

  try {
    const res = await fetch(`${API_BASE_URL}/analyze`, {
      method: 'POST',
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
      const err = new Error(detail)
      err.status = res.status
      throw err
    }

    return await res.json()
  } catch (err) {
    throw formatNetworkError(err)
  }
}
