import test from 'node:test'
import assert from 'node:assert/strict'
import { cleanDataset } from './client.js'

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
    },
  }

  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options) => {
    assert.match(url, /\/clean$/)
    assert.equal(options.method, 'POST')
    assert.ok(options.body instanceof FormData)
    assert.ok(options.body.get('file') instanceof File)

    return {
      ok: true,
      status: 200,
      json: async () => mockResponseData,
    }
  }

  try {
    const originalFile = new File(['ID,Value,Date\n1,10,2023-01-01'], 'data.csv', { type: 'text/csv' })
    const result = await cleanDataset(originalFile)

    assert.equal(result.original_rows, 100)
    assert.equal(result.cleaned_rows, 98)
    assert.equal(result.cleaning_report.duplicates_removed, 2)
    assert.equal(result.cleaning_report.numerical_values_filled.Value, 1)

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
