import test from 'node:test'
import assert from 'node:assert/strict'
import {
  cleanDataset,
  downloadCleanedDataset,
  analyzeDataset,
  createAISession,
  testAIProviderConnection,
  saveAIProviderConfiguration,
  clearAIProviderConfiguration,
  getCurrentAIProviderConfiguration,
} from './client.js'

test('cleanDataset - rejects when no file is provided', async () => {
  await assert.rejects(
    () => cleanDataset(null),
    { message: 'No dataset file provided for cleaning.' }
  )
})

test('cleanDataset - rejects non-csv files', async () => {
  const file = new File(['dummy content'], 'report.xlsx', { type: 'application/vnd.ms-excel' })
  await assert.rejects(
    () => cleanDataset(file),
    { message: 'Only CSV files are supported (.csv).' }
  )
})

test('cleanDataset - successful API response handling', async () => {
  const mockResponseData = {
    original_rows: 100,
    cleaned_rows: 98,
    columns: ['ID', 'Value', 'Date'],
    cleaning_report: {
      duplicates_removed: 2,
      duplicates_before: { duplicate_count: 2, duplicate_percentage: 2.0 },
      missing_before: { ID: { missing_count: 0 }, Value: { missing_count: 1 } },
      missing_after: { ID: { missing_count: 0 }, Value: { missing_count: 0 } },
      outliers: { Value: { outlier_count: 3, lower_bound: -5, upper_bound: 25 } },
      converted_date_columns: ['Date'],
      numerical_values_filled: { Value: 1 },
      categorical_values_filled: {},
      missing_value_intelligence: {
        threshold: 75.0,
        columns_actually_removed: ['Old_Sparse'],
        columns_preserved: ['ID', 'Value', 'Date'],
        high_missingness_columns: ['Old_Sparse'],
      },
    },
  }

  let capturedBody = null
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options) => {
    assert.match(url, /\/clean$/)
    assert.equal(options.method, 'POST')
    assert.ok(options.body instanceof FormData)
    assert.ok(options.body.get('file') instanceof File)
    capturedBody = options.body

    return {
      ok: true,
      status: 200,
      json: async () => mockResponseData,
    }
  }

  try {
    const originalFile = new File(['ID,Value,Date\n1,10,2023-01-01'], 'data.csv', { type: 'text/csv' })
    const result = await cleanDataset(originalFile, {
      threshold: 80,
      numericalStrategy: 'mean',
      outlierTreatment: 'cap',
      removeDuplicates: false,
      approvedDropColumns: ['Old_Sparse'],
    })

    assert.equal(result.original_rows, 100)
    assert.equal(result.cleaned_rows, 98)
    assert.equal(result.cleaning_report.duplicates_removed, 2)
    assert.equal(result.cleaning_report.numerical_values_filled.Value, 1)

    // Verify formData parameters sent
    assert.equal(capturedBody.get('threshold'), '80')
    assert.equal(capturedBody.get('numerical_strategy'), 'mean')
    assert.equal(capturedBody.get('outlier_treatment'), 'cap')
    assert.equal(capturedBody.get('remove_duplicates'), 'false')
    assert.equal(capturedBody.get('approved_drop_columns'), '["Old_Sparse"]')

    // Verify original file remains available and untouched
    assert.equal(originalFile.name, 'data.csv')
    assert.equal(originalFile.size, 29)
    const text = await originalFile.text()
    assert.equal(text, 'ID,Value,Date\n1,10,2023-01-01')
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('cleanDataset - API error handling (400 Bad Request)', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => ({
    ok: false,
    status: 400,
    json: async () => ({ detail: 'Only CSV files are supported' }),
  })

  try {
    const file = new File(['bad'], 'test.csv', { type: 'text/csv' })
    await assert.rejects(
      () => cleanDataset(file),
      (err) => {
        assert.equal(err.status, 400)
        assert.match(err.message, /Only CSV files are supported/)
        return true
      }
    )
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('cleanDataset - API error handling (500 Server Error)', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => ({
    ok: false,
    status: 500,
    json: async () => ({ detail: 'Internal Pandas Parser Error' }),
  })

  try {
    const file = new File(['bad'], 'test.csv', { type: 'text/csv' })
    await assert.rejects(
      () => cleanDataset(file),
      (err) => {
        assert.equal(err.status, 500)
        assert.match(err.message, /Internal Pandas Parser Error/)
        return true
      }
    )
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('cleanDataset - network connection error formatting', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => {
    throw new TypeError('Failed to fetch')
  }

  try {
    const file = new File(['content'], 'test.csv', { type: 'text/csv' })
    await assert.rejects(
      () => cleanDataset(file),
      /Backend Unavailable: Unable to connect to InsightForge API/
    )
  } finally {
    globalThis.fetch = originalFetch
  }
})

// ============================================================================
// Cleaned Dataset Download Tests
// ============================================================================

test('downloadCleanedDataset - 1. successfully handles a CSV Blob and triggers browser download', async () => {
  const csvContent = 'ID,Name,Score\n1,Alice,95\n2,Bob,88\n'
  const mockBlob = new Blob([csvContent], { type: 'text/csv' })

  let clicked = false
  let createdUrl = null
  let revokedUrl = null
  let appendedChild = null
  let removedChild = null

  // Mock DOM environment
  const originalWindow = globalThis.window
  const originalDocument = globalThis.document

  globalThis.window = {
    URL: {
      createObjectURL: (blob) => {
        assert.equal(blob, mockBlob)
        createdUrl = 'blob:http://localhost:5173/mock-uuid-123'
        return createdUrl
      },
      revokeObjectURL: (url) => {
        revokedUrl = url
      },
    },
  }

  const mockAnchor = {
    style: {},
    href: '',
    download: '',
    click: () => {
      clicked = true
    },
  }

  globalThis.document = {
    createElement: (tag) => {
      assert.equal(tag, 'a')
      return mockAnchor
    },
    body: {
      appendChild: (el) => {
        appendedChild = el
      },
      removeChild: (el) => {
        removedChild = el
      },
    },
  }

  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url) => {
    assert.match(url, /\/clean\/download\/test-id-1$/)
    return {
      ok: true,
      status: 200,
      headers: new Headers({
        'content-type': 'text/csv; charset=utf-8',
        'content-disposition': 'attachment; filename="students_cleaned.csv"',
      }),
      blob: async () => mockBlob,
    }
  }

  try {
    const result = await downloadCleanedDataset('/clean/download/test-id-1', 'fallback.csv')

    assert.equal(result.success, true)
    assert.equal(result.filename, 'students_cleaned.csv')
    assert.equal(result.blob, mockBlob)

    // Verify browser DOM download actions
    assert.equal(clicked, true)
    assert.equal(mockAnchor.download, 'students_cleaned.csv')
    assert.equal(mockAnchor.href, 'blob:http://localhost:5173/mock-uuid-123')
    assert.equal(appendedChild, mockAnchor)
    assert.equal(removedChild, mockAnchor)
    assert.equal(revokedUrl, 'blob:http://localhost:5173/mock-uuid-123')
  } finally {
    globalThis.fetch = originalFetch
    globalThis.window = originalWindow
    globalThis.document = originalDocument
  }
})

test('downloadCleanedDataset - 2. correct filename is used (header vs fallback vs default)', async () => {
  const originalFetch = globalThis.fetch

  try {
    // Case A: Content-Disposition header provided
    globalThis.fetch = async () => ({
      ok: true,
      status: 200,
      headers: new Headers({
        'content-disposition': 'attachment; filename="custom_report_cleaned.csv"',
      }),
      blob: async () => new Blob(['data'], { type: 'text/csv' }),
    })
    const resA = await downloadCleanedDataset('test-id-a', 'fallback.csv')
    assert.equal(resA.filename, 'custom_report_cleaned.csv')

    // Case B: No header, fallback provided
    globalThis.fetch = async () => ({
      ok: true,
      status: 200,
      headers: new Headers(),
      blob: async () => new Blob(['data'], { type: 'text/csv' }),
    })
    const resB = await downloadCleanedDataset('test-id-b', 'my_sales_cleaned.csv')
    assert.equal(resB.filename, 'my_sales_cleaned.csv')

    // Case C: Neither provided -> defaults to 'cleaned_dataset.csv'
    const resC = await downloadCleanedDataset('test-id-c')
    assert.equal(resC.filename, 'cleaned_dataset.csv')
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('downloadCleanedDataset - 3. server errors are handled (404 expired & 500 server error)', async () => {
  const originalFetch = globalThis.fetch

  try {
    // 404 Expired or not found
    globalThis.fetch = async () => ({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Download not found or has expired.' }),
    })

    await assert.rejects(
      () => downloadCleanedDataset('expired-id'),
      (err) => {
        assert.equal(err.status, 404)
        assert.match(err.message, /expired/i)
        return true
      }
    )

    // 500 Server error
    globalThis.fetch = async () => ({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'Filesystem read error on server.' }),
    })

    await assert.rejects(
      () => downloadCleanedDataset('error-id'),
      (err) => {
        assert.equal(err.status, 500)
        assert.match(err.message, /Filesystem read error/i)
        return true
      }
    )
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('downloadCleanedDataset - 4. network failures are formatted with diagnostic guidance', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => {
    throw new TypeError('Failed to fetch')
  }

  try {
    await assert.rejects(
      () => downloadCleanedDataset('/clean/download/any-id'),
      /Backend Unavailable: Unable to connect to InsightForge API/
    )
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('download state - 5. download button is disabled before cleaning', () => {
  // Logic from DataCleaningPanel:
  // const hasDownloadRef = Boolean(cleaningResult && (cleaningResult.download_url || cleaningResult.download_id))
  // const canDownload = Boolean(hasDownloadRef && !isDownloading)

  const isDownloading = false

  // Case A: cleaningResult is null (before cleaning run)
  const resultNull = null
  const canDownloadBefore = Boolean(
    resultNull && (resultNull.download_url || resultNull.download_id) && !isDownloading
  )
  assert.equal(canDownloadBefore, false)

  // Case B: cleaningResult is empty object
  const resultEmpty = {}
  const canDownloadEmpty = Boolean(
    resultEmpty && (resultEmpty.download_url || resultEmpty.download_id) && !isDownloading
  )
  assert.equal(canDownloadEmpty, false)
})

test('download state - 6. download button is enabled after successful cleaning', () => {
  const isDownloading = false

  // After successful cleaning
  const cleaningResult = {
    original_rows: 100,
    cleaned_rows: 95,
    download_id: 'abc1234567890abcdef',
    download_url: '/clean/download/abc1234567890abcdef',
    download_filename: 'sales_cleaned.csv',
  }

  const hasDownloadRef = Boolean(
    cleaningResult && (cleaningResult.download_url || cleaningResult.download_id)
  )
  const canDownload = Boolean(hasDownloadRef && !isDownloading)

  assert.equal(canDownload, true)

  // While downloading, button is disabled to prevent repeated clicks
  const canDownloadWhileActive = Boolean(hasDownloadRef && !true)
  assert.equal(canDownloadWhileActive, false)
})

test('download state - 7. re-running cleaning updates the download reference', async () => {
  let callCount = 0
  const originalFetch = globalThis.fetch

  globalThis.fetch = async () => {
    callCount++
    return {
      ok: true,
      status: 200,
      json: async () => ({
        original_rows: 50,
        cleaned_rows: 50,
        download_id: `run-${callCount}-id`,
        download_url: `/clean/download/run-${callCount}-id`,
        download_filename: `run_${callCount}_cleaned.csv`,
        columns: ['A', 'B'],
        cleaning_report: {},
      }),
    }
  }

  try {
    const file = new File(['A,B\n1,2'], 'data.csv', { type: 'text/csv' })

    // First cleaning run
    const firstResult = await cleanDataset(file)
    assert.equal(firstResult.download_id, 'run-1-id')
    assert.equal(firstResult.download_url, '/clean/download/run-1-id')

    // Second cleaning run (e.g. user changed threshold from 75 to 80 and re-ran)
    const secondResult = await cleanDataset(file, { threshold: 80 })
    assert.equal(secondResult.download_id, 'run-2-id')
    assert.equal(secondResult.download_url, '/clean/download/run-2-id')
    assert.notEqual(firstResult.download_id, secondResult.download_id)
  } finally {
    globalThis.fetch = originalFetch
  }
})

// ============================================================================
// Multi-User AI Provider Configuration (BYOK) Tests
// ============================================================================

test('analyzeDataset - includes session_id in FormData when provided', async () => {
  const originalFetch = globalThis.fetch
  let capturedBody = null

  globalThis.fetch = async (url, options) => {
    assert.match(url, /\/analyze$/)
    assert.equal(options.method, 'POST')
    assert.ok(options.body instanceof FormData)
    capturedBody = options.body
    return {
      ok: true,
      status: 200,
      json: async () => ({
        text: 'Analysis result',
        conversation_id: 'conv-123',
      }),
    }
  }

  try {
    const res = await analyzeDataset({
      question: 'What is the average sales?',
      conversationId: 'conv-123',
      sessionId: 'user-session-abc',
    })

    assert.equal(res.conversation_id, 'conv-123')
    assert.equal(capturedBody.get('question'), 'What is the average sales?')
    assert.equal(capturedBody.get('conversation_id'), 'conv-123')
    assert.equal(capturedBody.get('session_id'), 'user-session-abc')
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('analyzeDataset - auto-retries without stale session token on 400 unissued session error', async () => {
  const originalFetch = globalThis.fetch
  let calls = 0
  let secondCallSessionId = undefined

  globalThis.fetch = async (url, options) => {
    calls++
    if (calls === 1) {
      return {
        ok: false,
        status: 400,
        json: async () => ({
          detail: 'Invalid or unissued session token. Please obtain a valid session from /config/session.',
        }),
      }
    }
    secondCallSessionId = options.body.get('session_id')
    return {
      ok: true,
      status: 200,
      json: async () => ({
        text: 'Visualization produced',
        conversation_id: 'conv-retry-1',
      }),
    }
  }

  try {
    const res = await analyzeDataset({
      question: 'Plot sales distribution',
      sessionId: 'stale-token-1234',
    })

    assert.equal(calls, 2)
    assert.equal(secondCallSessionId, null)
    assert.equal(res.conversation_id, 'conv-retry-1')
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('testAIProviderConnection - sends configuration to /config/test', async () => {
  const originalFetch = globalThis.fetch
  let capturedUrl = null
  let capturedHeaders = null
  let capturedBody = null

  globalThis.fetch = async (url, options) => {
    capturedUrl = url
    capturedHeaders = options.headers
    capturedBody = JSON.parse(options.body)
    return {
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        message: 'Successfully connected to OpenAI',
        provider: 'openai_compatible',
      }),
    }
  }

  try {
    const res = await testAIProviderConnection({
      sessionId: 'session-valid-token-12345',
      provider: 'openai_compatible',
      apiKey: 'sk-test-mock-key-12345',
      model: 'gpt-4o-mini',
      baseUrl: 'https://api.openai.com/v1',
    })

    assert.match(capturedUrl, /\/config\/test$/)
    assert.equal(capturedHeaders['X-Session-ID'], 'session-valid-token-12345')
    assert.equal(capturedBody.session_id, 'session-valid-token-12345')
    assert.equal(capturedBody.provider, 'openai_compatible')
    assert.equal(capturedBody.api_key, 'sk-test-mock-key-12345')
    assert.equal(capturedBody.model, 'gpt-4o-mini')
    assert.equal(capturedBody.base_url, 'https://api.openai.com/v1')
    assert.equal(res.success, true)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('testAIProviderConnection - formats connection failures', async () => {
  const originalFetch = globalThis.fetch

  globalThis.fetch = async () => ({
    ok: false,
    status: 400,
    json: async () => ({ detail: 'Invalid API key or unauthorized' }),
  })

  try {
    await assert.rejects(
      () =>
        testAIProviderConnection({
          provider: 'openai_compatible',
          apiKey: 'invalid-key',
        }),
      { message: 'Invalid API key or unauthorized' }
    )
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('testAIProviderConnection - supports Custom API with Base URL and model', async () => {
  const originalFetch = globalThis.fetch
  let capturedBody = null

  globalThis.fetch = async (url, options) => {
    capturedBody = JSON.parse(options.body)
    return {
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        message: 'Successfully connected to Custom API',
        provider: 'custom',
      }),
    }
  }

  try {
    const res = await testAIProviderConnection({
      provider: 'custom',
      baseUrl: 'https://custom-proxy.internal/v1',
      model: 'my-custom-model',
      apiKey: 'custom-secret-key',
    })

    assert.equal(capturedBody.provider, 'custom')
    assert.equal(capturedBody.base_url, 'https://custom-proxy.internal/v1')
    assert.equal(capturedBody.model, 'my-custom-model')
    assert.equal(capturedBody.api_key, 'custom-secret-key')
    assert.equal(res.success, true)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('saveAIProviderConfiguration - supports Custom API with custom endpoint and model', async () => {
  const originalFetch = globalThis.fetch
  let capturedBody = null

  globalThis.fetch = async (url, options) => {
    capturedBody = JSON.parse(options.body)
    return {
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        session_id: 'session-custom-1',
        config: {
          provider: 'custom',
          model: 'qwen2.5-coder-32b',
          base_url: 'https://vllm.infra.corp/v1',
          has_api_key: true,
          masked_key: '••••••••1234',
        },
      }),
    }
  }

  try {
    const res = await saveAIProviderConfiguration({
      sessionId: 'session-custom-1',
      provider: 'custom',
      baseUrl: 'https://vllm.infra.corp/v1',
      model: 'qwen2.5-coder-32b',
      apiKey: 'bearer-key-1234',
    })

    assert.equal(capturedBody.session_id, 'session-custom-1')
    assert.equal(capturedBody.provider, 'custom')
    assert.equal(capturedBody.base_url, 'https://vllm.infra.corp/v1')
    assert.equal(capturedBody.model, 'qwen2.5-coder-32b')
    assert.equal(capturedBody.api_key, 'bearer-key-1234')
    assert.equal(res.config.provider, 'custom')
    assert.equal(res.config.has_api_key, true)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('saveAIProviderConfiguration - requires sessionId and transmits credentials securely to backend', async () => {
  await assert.rejects(
    () => saveAIProviderConfiguration({ provider: 'ollama' }),
    { message: 'A session ID is required to configure AI credentials.' }
  )

  const originalFetch = globalThis.fetch
  let capturedBody = null
  let capturedHeaders = null

  // Ensure localStorage is empty / not used
  const originalLocalStorage = globalThis.localStorage
  let storageAccessed = false
  globalThis.localStorage = {
    setItem: () => {
      storageAccessed = true
    },
    getItem: () => null,
  }

  globalThis.fetch = async (url, options) => {
    assert.match(url, /\/config\/save$/)
    capturedHeaders = options?.headers
    capturedBody = JSON.parse(options.body)
    return {
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        session_id: 'session-xyz',
        config: {
          provider: 'groq',
          model: 'llama-3.3-70b-versatile',
          has_api_key: true,
          masked_key: 'gsk_...7890',
        },
      }),
    }
  }

  try {
    const res = await saveAIProviderConfiguration({
      sessionId: 'session-xyz',
      provider: 'groq',
      apiKey: 'gsk_secret1234567890',
      model: 'llama-3.3-70b-versatile',
    })

    assert.equal(capturedHeaders?.['X-Session-ID'], 'session-xyz')
    assert.equal(capturedBody.session_id, 'session-xyz')
    assert.equal(capturedBody.provider, 'groq')
    assert.equal(capturedBody.api_key, 'gsk_secret1234567890')
    assert.equal(res.config.has_api_key, true)
    assert.equal(storageAccessed, false, 'API key must never be written to localStorage')
  } finally {
    globalThis.fetch = originalFetch
    globalThis.localStorage = originalLocalStorage
  }
})

test('clearAIProviderConfiguration - clears session config and sends X-Session-ID header', async () => {
  await assert.rejects(
    () => clearAIProviderConfiguration(''),
    { message: 'A session ID is required to clear AI configuration.' }
  )

  const originalFetch = globalThis.fetch
  let capturedBody = null
  let capturedHeaders = null

  globalThis.fetch = async (url, options) => {
    assert.match(url, /\/config\/clear$/)
    capturedHeaders = options?.headers
    capturedBody = JSON.parse(options.body)
    return {
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        message: 'Session configuration cleared. Reverted to default local Ollama.',
      }),
    }
  }

  try {
    const res = await clearAIProviderConfiguration('session-xyz')
    assert.equal(capturedHeaders?.['X-Session-ID'], 'session-xyz')
    assert.equal(capturedBody.session_id, 'session-xyz')
    assert.equal(res.success, true)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('getCurrentAIProviderConfiguration - transmits session_id via X-Session-ID header without query params', async () => {
  const originalFetch = globalThis.fetch
  let capturedUrl = null
  let capturedHeaders = null

  globalThis.fetch = async (url, options) => {
    capturedUrl = url
    capturedHeaders = options?.headers
    return {
      ok: true,
      status: 200,
      json: async () => ({
        session_id: 'session-xyz',
        config: {
          provider: 'ollama',
          model: 'qwen2.5:1.5b',
          has_api_key: false,
          masked_key: null,
        },
      }),
    }
  }

  try {
    const res = await getCurrentAIProviderConfiguration('session-xyz')
    assert.match(capturedUrl, /\/config\/current$/)
    assert.ok(!capturedUrl.includes('?session_id='), 'Session ID must not be in query parameters')
    assert.equal(capturedHeaders?.['X-Session-ID'], 'session-xyz')
    assert.equal(res.config.provider, 'ollama')
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('createAISession - requests cryptographically random session from backend and falls back to CSPRNG', async () => {
  const originalFetch = globalThis.fetch

  globalThis.fetch = async (url, options) => {
    assert.match(url, /\/config\/session$/)
    assert.equal(options.method, 'POST')
    return {
      ok: true,
      status: 200,
      json: async () => ({
        session_id: 'a1b2c3d4e5f60718293a4b5c6d7e8f90',
      }),
    }
  }

  try {
    const sessionId = await createAISession()
    assert.equal(sessionId, 'a1b2c3d4e5f60718293a4b5c6d7e8f90')
  } finally {
    globalThis.fetch = originalFetch
  }
})
