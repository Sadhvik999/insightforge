import { useState } from 'react'
import {
  Database,
  Columns3,
  AlertTriangle,
  CopyCheck,
  Sparkles,
} from 'lucide-react'

import Sidebar from './components/Sidebar'
import Header from './components/Header'
import StatCard from './components/StatCard'
import UploadZone from './components/UploadZone'
import DataPreview from './components/DataPreview'
import AnalystPanel from './components/AnalystPanel'
import VisualizationPanel from './components/VisualizationPanel'
import DataCleaningPanel from './components/DataCleaningPanel'
import SettingsPanel from './components/SettingsPanel'

import './App.css'

export default function App() {
  const [activeTab, setActiveTab] = useState('overview')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Dataset state (loaded from backend POST /inspect)
  const [dataset, setDataset] = useState(null)
  const [cleaningResult, setCleaningResult] = useState(null)

  // AI Analyst conversation state (conversation_id returned by backend POST /analyze)
  const [conversationId, setConversationId] = useState(null)
  const [latestFigure, setLatestFigure] = useState(null)
  const [chatMessages, setChatMessages] = useState([
    {
      id: 'welcome-1',
      sender: 'ai',
      timestamp: 'Ready',
      text: 'Hello! I am your InsightForge local AI data analyst. Upload a CSV file and ask me about distributions, top categories, correlations, outlier detection, or interactive charts.',
      tags: ['Local Qwen 2.5:1.5b', 'Privacy Safe', 'Zero Cost'],
    },
  ])

  const handleDatasetLoaded = (newDataset) => {
    setDataset(newDataset)
    setConversationId(null) // Fresh dataset starts a fresh conversation session
    setLatestFigure(null)
    setCleaningResult(null)
  }

  const handleDatasetCleared = () => {
    setDataset(null)
    setConversationId(null)
    setLatestFigure(null)
    setCleaningResult(null)
  }

  const handleTriggerUpload = () => {
    setActiveTab('overview')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const hasData = Boolean(dataset && dataset.fileName)

  return (
    <div className="app-layout">
      {/* Sidebar Navigation */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main Content Area */}
      <div className="app-main-wrapper">
        <Header
          activeTab={activeTab}
          dataset={dataset}
          onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
        />

        <main className="app-content-body">
          {activeTab === 'overview' && (
            <div className="overview-flow">
              {/* Hero Banner */}
              <div className="welcome-banner">
                <div className="welcome-content">
                  <div className="welcome-tag">
                    <Sparkles className="w-3.5 h-3.5 text-purple-400 mr-1.5" />
                    Portfolio Project Showcase
                  </div>
                  <h2 className="welcome-title">
                    Welcome to <span className="welcome-gradient-text">InsightForge</span>
                  </h2>
                  <p className="welcome-desc">
                    Your autonomous local data analyst. Upload datasets in CSV format, query with conversational prompts, inspect distributions, and produce publication-ready charts.
                  </p>
                </div>
              </div>

              {/* Upload Dropzone */}
              <UploadZone
                dataset={dataset}
                onDatasetLoaded={handleDatasetLoaded}
                onDatasetCleared={handleDatasetCleared}
              />

              {/* Analytics Stat Cards */}
              <section className="stats-grid" aria-label="Dataset Statistics">
                <StatCard
                  title="Total Rows"
                  value={hasData ? dataset.totalRows : null}
                  subtitle={
                    hasData
                      ? `${dataset.totalRows.toLocaleString()} rows verified by backend`
                      : null
                  }
                  icon={Database}
                  accent="purple"
                  hasData={hasData}
                  trendText={hasData ? 'Backend Verified' : null}
                />
                <StatCard
                  title="Total Columns"
                  value={hasData ? dataset.totalColumns : null}
                  subtitle={
                    hasData
                      ? `${dataset.totalColumns} columns inspected`
                      : null
                  }
                  icon={Columns3}
                  accent="blue"
                  hasData={hasData}
                  trendText={hasData ? 'Backend Verified' : null}
                />
                <StatCard
                  title="Missing Values"
                  value={hasData ? dataset.missingValues : null}
                  subtitle={
                    hasData
                      ? `${dataset.missingValues} null cells across full dataset`
                      : null
                  }
                  icon={AlertTriangle}
                  accent="amber"
                  hasData={hasData}
                  trendText={hasData ? 'Full Audit' : null}
                />
                <StatCard
                  title="Duplicate Rows"
                  value={hasData ? dataset.duplicateRows : null}
                  subtitle={
                    hasData
                      ? `${dataset.duplicateRows} exact duplicates detected`
                      : null
                  }
                  icon={CopyCheck}
                  accent="emerald"
                  hasData={hasData}
                  trendText={hasData ? 'Full Audit' : null}
                />
              </section>

              {/* Dataset Preview */}
              <DataPreview
                dataset={dataset}
                onTriggerUpload={handleTriggerUpload}
              />

              {/* Dual Column: AI Analyst Chat & Visualization Studio */}
              <div className="analyst-viz-grid">
                <AnalystPanel
                  dataset={dataset}
                  conversationId={conversationId}
                  onConversationIdChange={setConversationId}
                  messages={chatMessages}
                  onMessagesChange={setChatMessages}
                  onFigureGenerated={setLatestFigure}
                />
                <VisualizationPanel dataset={dataset} figureData={latestFigure} />
              </div>
            </div>
          )}

          {activeTab === 'explorer' && (
            <div className="tab-view-flow">
              <UploadZone
                dataset={dataset}
                onDatasetLoaded={handleDatasetLoaded}
                onDatasetCleared={handleDatasetCleared}
              />
              <DataPreview
                dataset={dataset}
                onTriggerUpload={handleTriggerUpload}
              />
            </div>
          )}

          {activeTab === 'analyst' && (
            <div className="tab-view-flow">
              <div className="analyst-viz-grid">
                <AnalystPanel
                  dataset={dataset}
                  conversationId={conversationId}
                  onConversationIdChange={setConversationId}
                  messages={chatMessages}
                  onMessagesChange={setChatMessages}
                  onFigureGenerated={setLatestFigure}
                />
                <VisualizationPanel dataset={dataset} figureData={latestFigure} />
              </div>
            </div>
          )}

          {activeTab === 'cleaning' && (
            <div className="tab-view-flow">
              <DataCleaningPanel
                dataset={dataset}
                cleaningResult={cleaningResult}
                onCleaningResultChange={setCleaningResult}
                onNavigateToOverview={() => setActiveTab('overview')}
              />
            </div>
          )}

          {activeTab === 'settings' && (
            <div className="tab-view-flow">
              <SettingsPanel />
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
