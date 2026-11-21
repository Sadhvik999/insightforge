import { useState } from 'react'
import {
  Cpu,
  Server,
  DollarSign,
  ShieldCheck,
  HardDrive,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  RotateCcw,
  Loader2,
  SlidersHorizontal,
  KeyRound,
  ExternalLink,
} from 'lucide-react'
import {
  testAIProviderConnection,
  saveAIProviderConfiguration,
  clearAIProviderConfiguration,
  createAISession,
} from '../api/client'

const PROVIDER_DEFAULTS = {
  ollama: {
    label: 'Local Ollama (Default, Free & Offline)',
    defaultModel: 'qwen2.5:1.5b',
    defaultBaseUrl: 'http://localhost:11434',
    requiresKey: false,
    keyPlaceholder: 'No API key required for local Ollama',
    docsUrl: 'https://ollama.com',
  },
  openai_compatible: {
    label: 'OpenAI (Official)',
    defaultModel: 'gpt-4o-mini',
    defaultBaseUrl: 'https://api.openai.com/v1',
    requiresKey: true,
    keyPlaceholder: 'sk-proj-...',
    docsUrl: 'https://platform.openai.com/api-keys',
  },
  groq: {
    label: 'Groq Cloud (Fast Inference)',
    defaultModel: 'llama-3.3-70b-versatile',
    defaultBaseUrl: 'https://api.groq.com/openai/v1',
    requiresKey: true,
    keyPlaceholder: 'gsk_...',
    docsUrl: 'https://console.groq.com/keys',
  },
  openrouter: {
    label: 'OpenRouter (Multi-Model Gateway)',
    defaultModel: 'meta-llama/llama-3.3-70b-instruct',
    defaultBaseUrl: 'https://openrouter.ai/api/v1',
    requiresKey: true,
    keyPlaceholder: 'sk-or-v1-...',
    docsUrl: 'https://openrouter.ai/keys',
  },
  custom: {
    label: 'Custom API (OpenAI Compatible Endpoint)',
    defaultModel: '',
    defaultBaseUrl: '',
    requiresKey: false,
    keyPlaceholder: 'Bearer API Key (Optional / if required by your endpoint)',
    docsUrl: null,
    isCustom: true,
  },
}

export default function SettingsPanel({
  sessionId,
  activeConfig = {},
  onConfigSaved,
}) {
  const currentProvider = activeConfig.provider || 'ollama'

  const [provider, setProvider] = useState(currentProvider)
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [model, setModel] = useState(
    activeConfig.model || PROVIDER_DEFAULTS[currentProvider]?.defaultModel || ''
  )
  const [baseUrl, setBaseUrl] = useState(
    activeConfig.baseUrl || PROVIDER_DEFAULTS[currentProvider]?.defaultBaseUrl || ''
  )

  const [isTesting, setIsTesting] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isClearing, setIsClearing] = useState(false)
  const [testResult, setTestResult] = useState(null) // { success: boolean, message: string }
  const [saveResult, setSaveResult] = useState(null) // { success: boolean, message: string }

  const providerMeta = PROVIDER_DEFAULTS[provider] || PROVIDER_DEFAULTS.ollama

  const handleProviderChange = (e) => {
    const next = e.target.value
    setProvider(next)
    const defaults = PROVIDER_DEFAULTS[next] || PROVIDER_DEFAULTS.ollama
    setModel(defaults.defaultModel)
    setBaseUrl(defaults.defaultBaseUrl)
    setApiKey('')
    setTestResult(null)
    setSaveResult(null)
  }

  const handleTestConnection = async () => {
    if (isTesting || isSaving || isClearing) return
    setTestResult(null)
    setSaveResult(null)

    if (provider === 'custom') {
      if (!baseUrl.trim() || !(baseUrl.trim().startsWith('http://') || baseUrl.trim().startsWith('https://'))) {
        setTestResult({
          success: false,
          message: 'Please enter a valid Base URL starting with http:// or https:// for Custom API.',
        })
        return
      }
      if (!model.trim()) {
        setTestResult({
          success: false,
          message: 'Please enter a model name for Custom API.',
        })
        return
      }
    } else if (providerMeta.requiresKey && !apiKey.trim() && !activeConfig.hasApiKey) {
      setTestResult({
        success: false,
        message: `Please enter an API key to test connection to ${providerMeta.label}.`,
      })
      return
    }

    setIsTesting(true)

    try {
      let activeSessionId = sessionId
      if (!activeSessionId) {
        activeSessionId = await createAISession().catch(() => null)
      }

      if (!activeSessionId) {
        setTestResult({
          success: false,
          message: 'Unable to establish an authoritative server session. Please ensure the backend is running.',
        })
        return
      }

      const res = await testAIProviderConnection({
        sessionId: activeSessionId,
        provider,
        apiKey: apiKey.trim() || undefined,
        model: model.trim() || undefined,
        baseUrl: baseUrl.trim() || undefined,
      })

      setTestResult({
        success: true,
        message: res.message || `Successfully connected to ${provider === 'custom' ? 'Custom API' : provider}.`,
      })
    } catch (err) {
      setTestResult({
        success: false,
        message: err.message || 'Connection failed. Please verify endpoint and credentials.',
      })
    } finally {
      setIsTesting(false)
    }
  }

  const handleSaveConfiguration = async (e) => {
    if (e && e.preventDefault) e.preventDefault()
    if (isSaving || isTesting || isClearing) return

    if (provider === 'custom') {
      if (!baseUrl.trim() || !(baseUrl.trim().startsWith('http://') || baseUrl.trim().startsWith('https://'))) {
        setSaveResult({
          success: false,
          message: 'Please enter a valid Base URL starting with http:// or https:// for Custom API.',
        })
        return
      }
      if (!model.trim()) {
        setSaveResult({
          success: false,
          message: 'Please enter a model name for Custom API.',
        })
        return
      }
    } else if (providerMeta.requiresKey && !apiKey.trim() && !activeConfig.hasApiKey) {
      setSaveResult({
        success: false,
        message: `Please enter an API key for ${providerMeta.label}.`,
      })
      return
    }

    let activeSessionId = sessionId
    if (!activeSessionId) {
      activeSessionId = await createAISession().catch(() => null)
    }

    if (!activeSessionId) {
      setSaveResult({
        success: false,
        message: 'No active session token could be issued. Please ensure the backend is running.',
      })
      return
    }

    setIsSaving(true)
    setSaveResult(null)

    try {
      const res = await saveAIProviderConfiguration({
        sessionId: activeSessionId,
        provider,
        apiKey: apiKey.trim() || undefined,
        model: model.trim() || undefined,
        baseUrl: baseUrl.trim() || undefined,
      })

      const updated = res.config || {}
      if (typeof onConfigSaved === 'function') {
        onConfigSaved({
          provider: updated.provider || provider,
          model: updated.model || model,
          baseUrl: updated.base_url || baseUrl,
          hasApiKey: updated.has_api_key,
          maskedKey: updated.masked_key,
        })
      }

      setApiKey('') // Clear raw key from form input for security
      setSaveResult({
        success: true,
        message: `Configuration saved for session. Provider: ${provider === 'custom' ? 'Custom API' : provider}, Model: ${updated.model || model}.`,
      })
      setTestResult(null)
    } catch (err) {
      setSaveResult({
        success: false,
        message: err.message || 'Failed to save configuration.',
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleClearConfiguration = async () => {
    if (isClearing || isSaving || isTesting) return
    if (!sessionId) return

    setIsClearing(true)
    setSaveResult(null)
    setTestResult(null)

    try {
      await clearAIProviderConfiguration(sessionId)
      setProvider('ollama')
      setModel(PROVIDER_DEFAULTS.ollama.defaultModel)
      setBaseUrl(PROVIDER_DEFAULTS.ollama.defaultBaseUrl)
      setApiKey('')

      if (typeof onConfigSaved === 'function') {
        onConfigSaved({
          provider: 'ollama',
          model: PROVIDER_DEFAULTS.ollama.defaultModel,
          baseUrl: PROVIDER_DEFAULTS.ollama.defaultBaseUrl,
          hasApiKey: false,
          maskedKey: null,
        })
      }

      setSaveResult({
        success: true,
        message: 'Configuration reset to default local Ollama.',
      })
    } catch (err) {
      setSaveResult({
        success: false,
        message: err.message || 'Failed to clear configuration.',
      })
    } finally {
      setIsClearing(false)
    }
  }

  const configs = [
    {
      label: 'Local LLM Inference',
      value: 'Ollama (qwen2.5:1.5b)',
      icon: Cpu,
      status: 'Active',
      detail: 'Local Metal GPU-accelerated weights',
    },
    {
      label: 'Inference Endpoint',
      value: 'http://localhost:11434',
      icon: Server,
      status: 'Configured',
      detail: 'Zero latency over loopback network',
    },
    {
      label: 'Target Hardware',
      value: 'MacBook Pro M3 (8GB Unified Memory)',
      icon: HardDrive,
      status: 'Optimized',
      detail: 'Memory constrained footprint (<1.5GB)',
    },
    {
      label: 'API Budget & Billing',
      value: provider === 'ollama' ? '$0.00 (Local Free)' : 'BYOK Cloud Account',
      icon: DollarSign,
      status: 'Enforced',
      detail: provider === 'ollama' ? 'No external paid cloud APIs used' : 'Direct usage on your cloud account',
    },
  ]

  return (
    <div className="settings-panel-wrap">
      {/* Intro Header Card */}
      <div className="section-intro-card">
        <div className="intro-card-header">
          <div className="intro-icon-box">
            <SlidersHorizontal className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h2 className="intro-title">Platform & AI Provider Settings</h2>
            <p className="intro-subtitle">
              Configure your AI reasoning model, Bring Your Own Key (BYOK), or use local offline inference.
            </p>
          </div>
        </div>
      </div>

      {/* Dedicated AI Provider Configuration Card */}
      <div className="settings-byok-card" aria-label="AI Provider Configuration">
        <div className="byok-card-header">
          <div className="byok-title-group">
            <div className="byok-icon-box">
              <KeyRound className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h3 className="byok-title">AI Provider & Model Configuration</h3>
              <p className="byok-subtitle">
                Select your inference backend. Keys are held in volatile session memory and never saved to disk.
              </p>
            </div>
          </div>

          <div className="byok-status-pill">
            <span
              className={`status-dot ${
                activeConfig.provider && activeConfig.provider !== 'ollama'
                  ? 'bg-blue-400'
                  : 'bg-emerald-400'
              }`}
            />
            <span className="byok-status-label">
              Active: {
                activeConfig.provider === 'custom'
                  ? 'Custom API'
                  : activeConfig.provider === 'ollama'
                  ? 'Ollama (Local)'
                  : activeConfig.provider === 'openai_compatible'
                  ? 'OpenAI'
                  : activeConfig.provider || 'Ollama'
              }
            </span>
          </div>
        </div>

        <form className="byok-form" onSubmit={handleSaveConfiguration}>
          {/* Provider Selection */}
          <div className="form-group">
            <label htmlFor="ai-provider-select" className="form-label">
              AI Provider
            </label>
            <select
              id="ai-provider-select"
              value={provider}
              onChange={handleProviderChange}
              className="form-select"
              disabled={isTesting || isSaving || isClearing}
            >
              {Object.entries(PROVIDER_DEFAULTS).map(([key, item]) => (
                <option key={key} value={key}>
                  {item.label}
                </option>
              ))}
            </select>
            <span className="form-hint">
              InsightForge supports offline local inference (Ollama), OpenAI, Groq, OpenRouter, and custom OpenAI-compatible endpoints.
            </span>
          </div>

          {/* API Key (Conditional / Masked) */}
          <div className="form-group">
            <div className="form-label-row">
              <label htmlFor="ai-api-key-input" className="form-label">
                API Key {
                  provider === 'custom'
                    ? '(Optional / endpoint dependent)'
                    : providerMeta.requiresKey
                    ? '(Required)'
                    : '(Not required for Ollama)'
                }
              </label>
              {providerMeta.docsUrl && (
                <a
                  href={providerMeta.docsUrl}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="docs-link"
                >
                  Get Key <ExternalLink className="w-3 h-3 ml-0.5" />
                </a>
              )}
            </div>
            <div className="password-input-wrap">
              <input
                id="ai-api-key-input"
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={
                  activeConfig.hasApiKey && activeConfig.provider === provider
                    ? `Configured (${activeConfig.maskedKey || '••••••••'}) — enter new key to replace`
                    : provider === 'custom'
                    ? 'Bearer API Key (Optional / if required by your endpoint)'
                    : providerMeta.keyPlaceholder
                }
                disabled={(!providerMeta.requiresKey && provider !== 'custom') || isTesting || isSaving || isClearing}
                className="form-input password-input"
                autoComplete="off"
                spellCheck="false"
              />
              {(providerMeta.requiresKey || provider === 'custom') && (
                <button
                  type="button"
                  onClick={() => setShowKey((prev) => !prev)}
                  className="password-toggle-btn"
                  title={showKey ? 'Hide API Key' : 'Show API Key'}
                  tabIndex={-1}
                >
                  {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              )}
            </div>
            {activeConfig.hasApiKey && activeConfig.provider === provider && (
              <span className="form-hint text-emerald-400">
                Key configured for current session: {activeConfig.maskedKey}
              </span>
            )}
          </div>

          {/* Model Name & Base URL Grid */}
          <div className="form-grid-2">
            <div className="form-group">
              <label htmlFor="ai-model-input" className="form-label">
                Model Name {provider === 'custom' && <span className="text-blue-400">*</span>}
              </label>
              <input
                id="ai-model-input"
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={providerMeta.defaultModel || 'e.g. meta-llama/llama-3-8b'}
                disabled={isTesting || isSaving || isClearing}
                className="form-input"
              />
              <span className="form-hint">
                {provider === 'custom'
                  ? 'Required: model identifier recognized by your API'
                  : `Default: ${providerMeta.defaultModel}`}
              </span>
            </div>

            <div className="form-group">
              <label htmlFor="ai-baseurl-input" className="form-label">
                API Base URL {provider === 'custom' && <span className="text-blue-400">*</span>}
              </label>
              <input
                id="ai-baseurl-input"
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={providerMeta.defaultBaseUrl || 'https://api.your-provider.com/v1'}
                disabled={isTesting || isSaving || isClearing}
                className="form-input"
              />
              <span className="form-hint">
                {provider === 'custom'
                  ? 'Required: e.g. https://api.together.xyz/v1 or http://localhost:8000/v1'
                  : `Default: ${providerMeta.defaultBaseUrl}`}
              </span>
            </div>
          </div>

          {/* Action Feedback Alerts */}
          {testResult && (
            <div
              className={`settings-feedback-alert ${
                testResult.success ? 'feedback-success' : 'feedback-error'
              }`}
            >
              {testResult.success ? (
                <CheckCircle2 className="w-4 h-4 mr-2 flex-shrink-0 text-emerald-400" />
              ) : (
                <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0 text-rose-400" />
              )}
              <span>{testResult.message}</span>
            </div>
          )}

          {saveResult && (
            <div
              className={`settings-feedback-alert ${
                saveResult.success ? 'feedback-success' : 'feedback-error'
              }`}
            >
              {saveResult.success ? (
                <CheckCircle2 className="w-4 h-4 mr-2 flex-shrink-0 text-emerald-400" />
              ) : (
                <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0 text-rose-400" />
              )}
              <span>{saveResult.message}</span>
            </div>
          )}

          {/* Action Buttons */}
          <div className="byok-actions-row">
            <div className="actions-left">
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={isTesting || isSaving || isClearing}
                className="btn-secondary"
              >
                {isTesting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Testing...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4 mr-2 text-blue-400" />
                    Test Connection
                  </>
                )}
              </button>

              <button
                type="submit"
                disabled={isTesting || isSaving || isClearing}
                className="btn-primary"
              >
                {isSaving ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    Save Configuration
                  </>
                )}
              </button>
            </div>

            <button
              type="button"
              onClick={handleClearConfiguration}
              disabled={isTesting || isSaving || isClearing || provider === 'ollama'}
              className="btn-ghost text-slate-400"
              title="Reset configuration to local Ollama defaults"
            >
              {isClearing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                  Resetting...
                </>
              ) : (
                <>
                  <RotateCcw className="w-4 h-4 mr-1.5" />
                  Reset to Ollama
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Local System Specs & Architecture Grid */}
      <div className="settings-grid">
        {configs.map((cfg, i) => {
          const Icon = cfg.icon
          return (
            <div key={i} className="setting-card">
              <div className="setting-header">
                <div className="setting-icon-box">
                  <Icon className="w-4 h-4 text-blue-400" />
                </div>
                <span className="setting-status-badge">
                  <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-400" />
                  {cfg.status}
                </span>
              </div>
              <h3 className="setting-label">{cfg.label}</h3>
              <p className="setting-value">{cfg.value}</p>
              <p className="setting-detail">{cfg.detail}</p>
            </div>
          )
        })}
      </div>

      {/* Data Sovereignty & BYOK Security Banner */}
      <div className="settings-privacy-banner">
        <ShieldCheck className="w-5 h-5 text-emerald-400 mr-2.5 flex-shrink-0" />
        <div>
          <h4 className="privacy-title">Data Privacy & Credential Security Assured</h4>
          <p className="privacy-desc">
            InsightForge never ships hardcoded developer API credentials. User-provided keys are held strictly in temporary server memory for the duration of the current session and never written to disk, database, or browser localStorage.
          </p>
        </div>
      </div>
    </div>
  )
}
