import { useState, useMemo } from 'react'
import {
  BarChart3,
  LineChart,
  PieChart,
  ScatterChart,
  Maximize2,
  Minimize2,
  Download,
  Info,
  Activity,
  Loader2,
} from 'lucide-react'
import Plotly from 'plotly.js-dist-min'
import PlotlyChart from './PlotlyChart'

export default function VisualizationPanel({ dataset, figureData = null }) {
  const [manualTab, setManualTab] = useState(null)
  const [isExpanded, setIsExpanded] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)

  const chartTypes = [
    { id: 'bar', label: 'Bar Chart', icon: BarChart3, desc: 'Categorical comparisons' },
    { id: 'line', label: 'Line Trend', icon: LineChart, desc: 'Temporal & sequential trends' },
    { id: 'histogram', label: 'Histogram', icon: PieChart, desc: 'Value distributions' },
    { id: 'scatter', label: 'Scatter Plot', icon: ScatterChart, desc: 'Numerical correlation' },
  ]

  // Pure derived active chart type (derived from live figureData or manual tab selection)
  const activeChartType = useMemo(() => {
    if (manualTab) return manualTab

    if (figureData && figureData.data && figureData.data[0]) {
      const trace = figureData.data[0]
      const t = trace.type
      if (t === 'bar') return 'bar'
      if (t === 'histogram') return 'histogram'
      if (t === 'scatter' || t === 'scattergl') {
        return trace.mode && trace.mode.includes('line') ? 'line' : 'scatter'
      }
    }

    return 'bar'
  }, [figureData, manualTab])

  const handleDownloadImage = async () => {
    if (!figureData || isDownloading) return
    setIsDownloading(true)
    try {
      // Find the active Plotly DOM plot element
      const plotElement = document.querySelector('.studio-plotly-chart .js-plotly-plot')
      if (plotElement && Plotly?.downloadImage) {
        await Plotly.downloadImage(plotElement, {
          format: 'png',
          width: 1200,
          height: 700,
          filename: `insightforge_${activeChartType}_chart`,
        })
      } else {
        // Fallback: create temporary off-screen div to export figureData
        const tempDiv = document.createElement('div')
        tempDiv.style.position = 'fixed'
        tempDiv.style.left = '-9999px'
        tempDiv.style.width = '1000px'
        tempDiv.style.height = '600px'
        document.body.appendChild(tempDiv)
        await Plotly.newPlot(tempDiv, figureData.data, figureData.layout || {})
        await Plotly.downloadImage(tempDiv, {
          format: 'png',
          width: 1200,
          height: 700,
          filename: `insightforge_${activeChartType}_chart`,
        })
        Plotly.purge(tempDiv)
        document.body.removeChild(tempDiv)
      }
    } catch (err) {
      console.error('Failed to download chart image:', err)
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <>
      <section className="visualization-card" aria-labelledby="viz-heading">
        {/* Panel Header */}
        <div className="viz-header">
          <div className="viz-header-left">
            <div className="viz-icon-box">
              <BarChart3 className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h2 id="viz-heading" className="viz-title">Visualization Studio</h2>
              <p className="viz-subtitle">
                Plotly dynamic charts generated from analytical tool executions
              </p>
            </div>
          </div>

          <div className="viz-header-actions">
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={() => setIsExpanded(true)}
              disabled={!figureData}
              title={figureData ? 'Expand chart to full screen' : 'Generate a chart first to expand'}
              aria-label="Expand chart"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={handleDownloadImage}
              disabled={!figureData || isDownloading}
              title={figureData ? 'Download chart as high-res PNG' : 'Generate a chart first to download'}
              aria-label="Download chart image"
            >
              {isDownloading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Download className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
        </div>

        {/* Chart Selector Tabs */}
        <div className="viz-tabs-row" role="tablist" aria-label="Chart types">
          {chartTypes.map((tab) => {
            const Icon = tab.icon
            const isActive = activeChartType === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                className={`viz-tab-btn ${isActive ? 'viz-tab-active' : ''}`}
                onClick={() => setManualTab(tab.id)}
              >
                <Icon className="w-4 h-4 mr-1.5" />
                <span>{tab.label}</span>
              </button>
            )}
          )}
        </div>

        {/* Chart Canvas Area */}
        <div className="viz-canvas-area">
          {figureData ? (
            /* Real Plotly interactive visualization */
            <div className="plotly-rendered-container">
              <PlotlyChart figure={figureData} className="studio-plotly-chart" />
            </div>
          ) : (
            /* High-Fidelity Chart Placeholder & Visual Blueprint */
            <div className="viz-empty-canvas">
              <div className="viz-mockup-graphic" aria-hidden="true">
                {/* SVG Blueprint Mockup */}
                <svg
                  viewBox="0 0 500 220"
                  className="mockup-chart-svg"
                  preserveAspectRatio="none"
                >
                  <defs>
                    <linearGradient id="chartBlueGrad1" x1="0%" y1="0%" x2="0%" y2="100%">
                      <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.8" />
                      <stop offset="100%" stopColor="#1e3a8a" stopOpacity="0.2" />
                    </linearGradient>
                    <linearGradient id="chartBlueGrad2" x1="0%" y1="0%" x2="0%" y2="100%">
                      <stop offset="0%" stopColor="#60a5fa" stopOpacity="0.7" />
                      <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.1" />
                    </linearGradient>
                  </defs>

                  {/* Grid Lines */}
                  <line x1="40" y1="30" x2="480" y2="30" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
                  <line x1="40" y1="75" x2="480" y2="75" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
                  <line x1="40" y1="120" x2="480" y2="120" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
                  <line x1="40" y1="165" x2="480" y2="165" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
                  <line x1="40" y1="190" x2="480" y2="190" stroke="rgba(255,255,255,0.2)" />

                  {activeChartType === 'bar' && (
                    <>
                      <rect x="70" y="80" width="36" height="110" rx="4" fill="url(#chartBlueGrad1)" />
                      <rect x="130" y="45" width="36" height="145" rx="4" fill="url(#chartBlueGrad1)" />
                      <rect x="190" y="105" width="36" height="85" rx="4" fill="url(#chartBlueGrad1)" />
                      <rect x="250" y="60" width="36" height="130" rx="4" fill="url(#chartBlueGrad1)" />
                      <rect x="310" y="125" width="36" height="65" rx="4" fill="url(#chartBlueGrad1)" />
                      <rect x="370" y="90" width="36" height="100" rx="4" fill="url(#chartBlueGrad1)" />
                      <rect x="430" y="40" width="36" height="150" rx="4" fill="url(#chartBlueGrad1)" />
                    </>
                  )}

                  {activeChartType === 'line' && (
                    <>
                      <path
                        d="M 60,150 Q 120,60 180,90 T 300,50 T 420,110 T 470,40"
                        fill="none"
                        stroke="#3b82f6"
                        strokeWidth="3.5"
                      />
                      <path
                        d="M 60,170 Q 120,120 180,140 T 300,100 T 420,130 T 470,80"
                        fill="none"
                        stroke="#60a5fa"
                        strokeWidth="2.5"
                        strokeDasharray="6 3"
                      />
                      <circle cx="180" cy="90" r="5" fill="#3b82f6" stroke="#0f172a" strokeWidth="2" />
                      <circle cx="300" cy="50" r="5" fill="#3b82f6" stroke="#0f172a" strokeWidth="2" />
                      <circle cx="470" cy="40" r="5" fill="#3b82f6" stroke="#0f172a" strokeWidth="2" />
                    </>
                  )}

                  {activeChartType === 'histogram' && (
                    <>
                      <rect x="80" y="140" width="45" height="50" rx="2" fill="url(#chartBlueGrad2)" />
                      <rect x="130" y="90" width="45" height="100" rx="2" fill="url(#chartBlueGrad2)" />
                      <rect x="180" y="50" width="45" height="140" rx="2" fill="url(#chartBlueGrad1)" />
                      <rect x="230" y="35" width="45" height="155" rx="2" fill="url(#chartBlueGrad1)" />
                      <rect x="280" y="70" width="45" height="120" rx="2" fill="url(#chartBlueGrad1)" />
                      <rect x="330" y="110" width="45" height="80" rx="2" fill="url(#chartBlueGrad2)" />
                      <rect x="380" y="150" width="45" height="40" rx="2" fill="url(#chartBlueGrad2)" />
                    </>
                  )}

                  {activeChartType === 'scatter' && (
                    <>
                      <circle cx="80" cy="150" r="4.5" fill="#3b82f6" />
                      <circle cx="120" cy="130" r="4.5" fill="#60a5fa" />
                      <circle cx="150" cy="100" r="5" fill="#3b82f6" />
                      <circle cx="190" cy="95" r="4" fill="#60a5fa" />
                      <circle cx="210" cy="115" r="4.5" fill="#3b82f6" />
                      <circle cx="260" cy="80" r="5" fill="#2563eb" />
                      <circle cx="290" cy="65" r="4" fill="#60a5fa" />
                      <circle cx="340" cy="70" r="5.5" fill="#3b82f6" />
                      <circle cx="380" cy="45" r="5" fill="#2563eb" />
                      <circle cx="420" cy="55" r="4.5" fill="#60a5fa" />
                      <circle cx="450" cy="35" r="5" fill="#3b82f6" />
                      <line x1="60" y1="165" x2="460" y2="40" stroke="#3b82f6" strokeWidth="1.5" strokeDasharray="4 4" opacity="0.6" />
                    </>
                  )}
                </svg>
              </div>

              <div className="viz-overlay-message">
                <div className="viz-status-tag">
                  <Activity className="w-3.5 h-3.5 text-blue-400 mr-1" />
                  Plotly Engine Ready
                </div>
                <h4 className="viz-overlay-title">Interactive Chart Canvas</h4>
                <p className="viz-overlay-desc">
                  {dataset?.fileName
                    ? `Ask the AI Analyst (e.g. "Plot a bar chart of Sales by Region") to generate live interactive charts.`
                    : 'Upload a CSV dataset and ask the AI analyst to plot distributions, comparisons, or relationships.'}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Footer Info */}
        <div className="viz-footer">
          <Info className="w-3.5 h-3.5 text-muted mr-1.5 flex-shrink-0" />
          <span className="text-xs text-muted">
            Supports interactive zooming, pan, hover tooltips, and PNG downloads via Plotly.js.
          </span>
        </div>
      </section>

      {/* Expanded Chart Modal */}
      {isExpanded && figureData && (
        <div className="chart-modal-backdrop" onClick={() => setIsExpanded(false)}>
          <div
            className="chart-modal-dialog"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Expanded Chart View"
          >
            <div className="chart-modal-header">
              <div className="chart-modal-title-group">
                <BarChart3 className="w-5 h-5 text-blue-400 mr-2" />
                <h3 className="chart-modal-title">Interactive Chart View</h3>
              </div>
              <div className="chart-modal-actions">
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={handleDownloadImage}
                  disabled={isDownloading}
                >
                  {isDownloading ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                  ) : (
                    <Download className="w-3.5 h-3.5 mr-1" />
                  )}
                  Export PNG
                </button>
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => setIsExpanded(false)}
                  aria-label="Close expanded view"
                >
                  <Minimize2 className="w-4 h-4 mr-1" />
                  Close
                </button>
              </div>
            </div>
            <div className="chart-modal-body">
              <PlotlyChart figure={figureData} className="modal-plotly-chart" />
            </div>
          </div>
        </div>
      )}
    </>
  )
}
