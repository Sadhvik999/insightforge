import { useMemo } from 'react'
import Plotly from 'plotly.js-dist-min'
import createPlotlyComponent from 'react-plotly.js/factory'
import { AlertCircle } from 'lucide-react'

const Plot = createPlotlyComponent(Plotly)

/**
 * Reusable Responsive Plotly Chart Component
 * Supports bar, line, histogram, and scatter charts with dark theme styling.
 */
export default function PlotlyChart({ figure, className = '' }) {
  const chartConfig = useMemo(() => {
    if (!figure || !figure.data) {
      return null
    }

    // Deep copy layout and adapt to InsightForge dark theme while preserving titles and axes
    const incomingLayout = figure.layout || {}

    const layout = {
      ...incomingLayout,
      autosize: true,
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'rgba(11, 17, 32, 0.6)',
      font: {
        family: 'system-ui, -apple-system, sans-serif',
        color: '#cbd5e1',
        size: 11,
        ...(incomingLayout.font || {}),
      },
      title: {
        font: {
          color: '#f8fafc',
          size: 13,
          weight: 600,
        },
        x: 0.05,
        ...(typeof incomingLayout.title === 'string'
          ? { text: incomingLayout.title }
          : incomingLayout.title || {}),
      },
      margin: {
        l: 50,
        r: 30,
        t: 40,
        b: 50,
        pad: 4,
        ...(incomingLayout.margin || {}),
      },
      xaxis: {
        gridcolor: 'rgba(255, 255, 255, 0.06)',
        zerolinecolor: 'rgba(255, 255, 255, 0.1)',
        tickfont: { color: '#94a3b8', size: 10 },
        titlefont: { color: '#c4b5fd', size: 11 },
        ...(incomingLayout.xaxis || {}),
      },
      yaxis: {
        gridcolor: 'rgba(255, 255, 255, 0.06)',
        zerolinecolor: 'rgba(255, 255, 255, 0.1)',
        tickfont: { color: '#94a3b8', size: 10 },
        titlefont: { color: '#c4b5fd', size: 11 },
        ...(incomingLayout.yaxis || {}),
      },
      legend: {
        font: { color: '#cbd5e1', size: 10 },
        bgcolor: 'rgba(14, 20, 36, 0.7)',
        bordercolor: 'rgba(255, 255, 255, 0.1)',
        ...(incomingLayout.legend || {}),
      },
    }

    const config = {
      responsive: true,
      displayModeBar: true,
      displaylogo: false,
      modeBarButtonsToRemove: ['lasso2d', 'select2d'],
      toImageButtonOptions: {
        format: 'png',
        filename: 'insightforge_chart',
        height: 500,
        width: 700,
        scale: 2,
      },
    }

    return {
      data: figure.data,
      layout,
      config,
    }
  }, [figure])

  if (!chartConfig) {
    return (
      <div className="plotly-error-fallback">
        <AlertCircle className="w-4 h-4 text-amber-400 mr-2" />
        <span>Chart configuration or data is unavailable.</span>
      </div>
    )
  }

  return (
    <div className={`plotly-wrapper ${className}`}>
      <Plot
        data={chartConfig.data}
        layout={chartConfig.layout}
        config={chartConfig.config}
        useResizeHandler
        style={{ width: '100%', height: '100%', minHeight: '320px' }}
      />
    </div>
  )
}
