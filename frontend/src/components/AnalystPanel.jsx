import { useState, useRef, useEffect } from 'react'
import {
  Bot,
  Send,
  Activity,
  User,
  Info,
  CornerDownLeft,
  RotateCcw,
  Loader2,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Wrench,
  X,
  BarChart3,
} from 'lucide-react'
import { analyzeDataset } from '../api/client'
import PlotlyChart from './PlotlyChart'

const initialWelcomeMessage = {
  id: 'welcome-1',
  sender: 'ai',
  timestamp: 'Ready',
  text: 'Hello! I am your InsightForge local AI data analyst. Upload a CSV file and ask me about distributions, top categories, correlations, outlier detection, or interactive charts.',
  tags: ['AI Engine Ready', 'Plotly Engine', 'Privacy Safe', 'Session Isolated'],
}

export default function AnalystPanel({
  dataset,
  conversationId: externalConversationId,
  onConversationIdChange,
  sessionId,
  messages: externalMessages,
  onMessagesChange,
  onFigureGenerated,
}) {
  // Support both external state (lifted to App.jsx) and fallback internal state
  const [internalConversationId, setInternalConversationId] = useState(null)
  const [internalMessages, setInternalMessages] = useState([initialWelcomeMessage])

  const [inputPrompt, setInputPrompt] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [errorMessage, setErrorMessage] = useState(null)

  const chatScrollRef = useRef(null)
  const messageIdRef = useRef(1)

  const currentConversationId =
    externalConversationId !== undefined
      ? externalConversationId
      : internalConversationId

  const setConvId = (newId) => {
    if (typeof onConversationIdChange === 'function') {
      onConversationIdChange(newId)
    }
    setInternalConversationId(newId)
  }

  const messages =
    externalMessages !== undefined ? externalMessages : internalMessages

  const setMsgs = (updater) => {
    if (typeof onMessagesChange === 'function') {
      onMessagesChange(updater)
    }
    setInternalMessages(updater)
  }

  const suggestedQuestions = dataset?.fileName
    ? [
        'Plot a bar chart of Sales by Region',
        'Plot a scatter chart of Sales vs Profit',
        'Plot a histogram of Profit',
        'Which region has the highest total sales?',
      ]
    : [
        'Which region has the highest average sales?',
        'What is the distribution of Profit across categories?',
        'Identify potential outliers using IQR method',
        'Plot a scatter visualization of Sales vs Profit',
      ]

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight
    }
  }, [messages, isAnalyzing])

  const handleSendMessage = async (textToSend) => {
    if (isAnalyzing) return

    const query = (textToSend || inputPrompt || '').trim()
    if (!query) return

    // Requirement 10: Handle missing datasets gracefully
    if (!dataset || !dataset.file) {
      setErrorMessage(
        'Please upload a CSV dataset first before querying the AI Analyst.'
      )
      return
    }

    setErrorMessage(null)

    messageIdRef.current += 1
    const userMsg = {
      id: `user-${messageIdRef.current}`,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      }),
      text: query,
    }

    setMsgs((prev) => [...prev, userMsg])
    setInputPrompt('')
    setIsAnalyzing(true)

    try {
      // First turn sends the CSV file; follow-ups send only question & conversation_id
      const isFirstTurn = !currentConversationId
      const response = await analyzeDataset({
        question: query,
        file: isFirstTurn ? dataset.file : null,
        conversationId: isFirstTurn ? null : currentConversationId,
        sessionId,
      })

      if (response?.conversation_id) {
        setConvId(response.conversation_id)
      }

      // Extract figureData if visualizer was called
      let figureData = null
      let chartType = null
      if (response?.results?.figure) {
        figureData = response.results.figure
        chartType = response.results.chart_type
      } else if (Array.isArray(response?.tool_results)) {
        const viz = response.tool_results.find(
          (t) => t.tool === 'visualize_data' && t.results?.figure
        )
        if (viz) {
          figureData = viz.results.figure
          chartType = viz.results.chart_type
        }
      }

      if (figureData && typeof onFigureGenerated === 'function') {
        onFigureGenerated(figureData)
      }

      messageIdRef.current += 1
      const aiMsg = {
        id: `ai-${messageIdRef.current}`,
        sender: 'ai',
        timestamp: new Date().toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit',
        }),
        summary: response.summary,
        keyFindings: Array.isArray(response.key_findings)
          ? response.key_findings
          : [],
        toolInfo: {
          tool: response.selected_tool,
          count: response.tool_calls_count,
          arguments: response.arguments,
          stopReason: response.stop_reason,
        },
        figureData,
        chartType,
        conversationId: response.conversation_id,
      }

      setMsgs((prev) => [...prev, aiMsg])
    } catch (err) {
      // Check for 404 / expired conversation
      const isExpired =
        err.status === 404 ||
        err.message?.toLowerCase().includes('conversation not found')

      if (isExpired) {
        // Reset conversation ID so the next question starts a fresh session
        setConvId(null)
        if (typeof onFigureGenerated === 'function') {
          onFigureGenerated(null)
        }
        messageIdRef.current += 1
        const expiredMsg = {
          id: `ai-expired-${messageIdRef.current}`,
          sender: 'ai',
          timestamp: new Date().toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          }),
          isError: true,
          text: 'Your previous conversation session expired or was not found. Active session has been reset. Please submit your question again to start a new analysis session with your uploaded dataset.',
        }
        setMsgs((prev) => [...prev, expiredMsg])
        setErrorMessage(
          'Conversation session expired. Session has been reset — submit your question again.'
        )
      } else {
        messageIdRef.current += 1
        const errorMsg = {
          id: `ai-err-${messageIdRef.current}`,
          sender: 'ai',
          timestamp: new Date().toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          }),
          isError: true,
          text: err.message || 'An error occurred while analyzing the dataset.',
        }
        setMsgs((prev) => [...prev, errorMsg])
        setErrorMessage(err.message || 'Analysis request failed.')
      }
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!isAnalyzing && inputPrompt.trim()) {
        handleSendMessage()
      }
    }
  }

  const handleClearChat = () => {
    if (isAnalyzing) return
    setConvId(null)
    setErrorMessage(null)
    if (typeof onFigureGenerated === 'function') {
      onFigureGenerated(null)
    }
    messageIdRef.current += 1
    setMsgs([
      {
        id: `welcome-${messageIdRef.current}`,
        sender: 'ai',
        timestamp: 'Ready',
        text: 'Chat history cleared. Active conversation session has been reset. Ask a question below to start a new analysis session.',
        tags: ['Local Qwen 2.5:1.5b', 'Plotly Engine', 'Privacy Safe', 'Zero Cost'],
      },
    ])
  }

  return (
    <section className="analyst-card" aria-labelledby="analyst-heading">
      {/* Panel Header */}
      <div className="analyst-header">
        <div className="analyst-header-left">
          <div className="analyst-avatar-box">
            <Bot className="w-5 h-5 text-purple-300" />
            <span className="analyst-online-pulse" />
          </div>
          <div>
            <h2 id="analyst-heading" className="analyst-title">AI Analyst Studio</h2>
            <p className="analyst-subtitle">
              Interactive natural language querying • Local inference
            </p>
          </div>
        </div>

        <div className="analyst-header-right">
          <div className="model-chip" title="Local model identifier">
            <span className="model-chip-dot" />
            <span>qwen2.5:1.5b</span>
          </div>

          <button
            type="button"
            className="btn-ghost btn-sm"
            onClick={handleClearChat}
            disabled={isAnalyzing}
            title="Reset conversation thread and conversation ID"
            aria-label="Reset chat history"
          >
            <RotateCcw className="w-3.5 h-3.5 mr-1" />
            Clear
          </button>
        </div>
      </div>

      {/* Dynamic Status / Session Banner */}
      <div className="analyst-status-banner">
        {errorMessage ? (
          <div className="analyst-banner-error" role="alert">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
            <span className="flex-1">{errorMessage}</span>
            <button
              type="button"
              className="analyst-banner-dismiss"
              onClick={() => setErrorMessage(null)}
              title="Dismiss error message"
              aria-label="Dismiss error message"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        ) : currentConversationId ? (
          <div className="analyst-banner-session">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
            <span>
              Active Session: <strong>{currentConversationId.slice(0, 8)}...</strong>
              {dataset?.fileName && (
                <> • Context: <strong>{dataset.fileName}</strong></>
              )}
            </span>
          </div>
        ) : dataset?.fileName ? (
          <div className="analyst-banner-ready">
            <Activity className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
            <span>
              Ready: <strong>{dataset.fileName}</strong> loaded ({dataset.totalRows?.toLocaleString()} rows). Ask a question below to begin.
            </span>
          </div>
        ) : (
          <div className="analyst-banner-empty">
            <Info className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            <span>
              No dataset uploaded yet. Upload a CSV file in Overview or Explorer to begin querying.
            </span>
          </div>
        )}
      </div>

      {/* Chat Thread */}
      <div className="chat-thread" ref={chatScrollRef} role="log" aria-live="polite">
        {messages.map((msg) => {
          const isAI = msg.sender === 'ai'
          return (
            <div
              key={msg.id}
              className={`chat-message ${isAI ? 'chat-message-ai' : 'chat-message-user'}`}
            >
              <div className="message-avatar">
                {isAI ? (
                  <Bot
                    className={`w-4 h-4 ${msg.isError ? 'text-amber-400' : 'text-purple-400'}`}
                  />
                ) : (
                  <User className="w-4 h-4 text-blue-400" />
                )}
              </div>

              <div className="message-bubble-group">
                <div className="message-header-meta">
                  <span className="message-sender-label">
                    {isAI ? 'InsightForge Analyst' : 'You'}
                  </span>
                  <span className="message-timestamp">{msg.timestamp}</span>
                  {msg.conversationId && (
                    <span
                      className="message-session-tag"
                      title={`Conversation ID: ${msg.conversationId}`}
                    >
                      Session #{msg.conversationId.slice(0, 6)}
                    </span>
                  )}
                </div>

                <div
                  className={`message-bubble ${
                    msg.isError
                      ? 'message-bubble-error'
                      : msg.isNotice
                      ? 'message-bubble-notice'
                      : ''
                  }`}
                >
                  {/* Error display */}
                  {msg.isError && (
                    <div className="message-error-content">
                      <AlertCircle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                      <p className="message-text">{msg.text}</p>
                    </div>
                  )}

                  {/* Standard text (e.g. welcome message) */}
                  {!msg.isError && msg.text && !msg.summary && (
                    <p className="message-text">{msg.text}</p>
                  )}

                  {/* Backend Analysis Summary */}
                  {!msg.isError && msg.summary && (
                    <div className="analyst-summary-section">
                      <p className="analyst-summary-text">{msg.summary}</p>
                    </div>
                  )}

                  {/* Backend Key Findings List */}
                  {!msg.isError && msg.keyFindings && msg.keyFindings.length > 0 && (
                    <div className="analyst-findings-block">
                      <div className="findings-header">
                        <Activity className="w-3.5 h-3.5 text-blue-400" />
                        <span>Key Findings</span>
                      </div>
                      <ul className="findings-list">
                        {msg.keyFindings.map((finding, idx) => (
                          <li key={idx} className="finding-item">
                            <span className="finding-bullet">•</span>
                            <span>{finding}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Interactive Plotly Visualization */}
                  {!msg.isError && msg.figureData && (
                    <div className="analyst-chart-container">
                      <div className="analyst-chart-header">
                        <span className="analyst-chart-badge">
                          <BarChart3 className="w-3.5 h-3.5 text-purple-400 mr-1.5" />
                          Interactive Visualization
                        </span>
                        {msg.chartType && (
                          <span className="analyst-chart-type">
                            {msg.chartType.toUpperCase()}
                          </span>
                        )}
                      </div>
                      <PlotlyChart figure={msg.figureData} className="chat-plotly-chart" />
                    </div>
                  )}

                  {/* Tool Execution Pills */}
                  {!msg.isError && msg.toolInfo?.tool && (
                    <div className="message-tags-list">
                      <span className="message-tag-pill">
                        <Wrench className="w-3 h-3 text-purple-400 mr-1" />
                        Tool: {msg.toolInfo.tool}
                      </span>
                      {msg.toolInfo.count > 0 && (
                        <span className="message-tag-pill">
                          Calls: {msg.toolInfo.count}
                        </span>
                      )}
                      {msg.toolInfo.stopReason && (
                        <span className="message-tag-pill">
                          Status: {msg.toolInfo.stopReason}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Metadata tags */}
                  {msg.tags && msg.tags.length > 0 && (
                    <div className="message-tags-list">
                      {msg.tags.map((tag) => (
                        <span key={tag} className="message-tag-pill">
                          <Activity className="w-3 h-3 text-blue-400 mr-1" />
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        })}

        {/* Loading state indicator */}
        {isAnalyzing && (
          <div className="chat-message chat-message-ai">
            <div className="message-avatar">
              <Bot className="w-4 h-4 text-purple-400" />
            </div>
            <div className="message-bubble-group">
              <div className="message-header-meta">
                <span className="message-sender-label">InsightForge Analyst</span>
                <span className="message-timestamp">Analyzing...</span>
              </div>
              <div className="message-bubble message-bubble-loading">
                <div className="chat-loading-content">
                  <Loader2 className="w-4 h-4 animate-spin text-purple-400 mr-2" />
                  <span>Executing local agent & running analysis tools with Qwen 2.5...</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Suggested Questions */}
      <div className="suggested-questions-wrap">
        <span className="suggested-label">SUGGESTIONS:</span>
        <div className="suggested-chips-list">
          {suggestedQuestions.map((q, idx) => (
            <button
              key={idx}
              type="button"
              className="suggested-chip"
              disabled={isAnalyzing}
              onClick={() => handleSendMessage(q)}
              title={
                !dataset?.file
                  ? 'Upload a CSV dataset first to ask questions'
                  : `Ask: "${q}"`
              }
            >
              <Activity className="w-3 h-3 text-blue-400 mr-1" />
              <span>{q}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Chat Input Bar */}
      <div className="chat-input-bar">
        <input
          type="text"
          className="chat-text-input"
          disabled={isAnalyzing}
          placeholder={
            dataset?.fileName
              ? `Ask a question about ${dataset.fileName} (e.g. 'Plot a bar chart of Sales by Region')...`
              : 'Upload a CSV dataset first to start asking questions...'
          }
          value={inputPrompt}
          onChange={(e) => setInputPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          aria-label="Enter question for the AI data analyst"
        />

        <button
          type="button"
          className="chat-send-btn"
          disabled={isAnalyzing || !inputPrompt.trim()}
          onClick={() => handleSendMessage()}
          aria-label="Send query to AI analyst"
        >
          {isAnalyzing ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <>
              <Send className="w-4 h-4" />
              <CornerDownLeft className="w-3 h-3 text-purple-200 hidden md:inline ml-0.5" />
            </>
          )}
        </button>
      </div>
    </section>
  )
}
