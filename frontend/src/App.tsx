import { useEffect, useState, type FormEvent } from 'react'
import './App.css'

type Signal = { term: string; contribution: number }
type FactCheck = {
  claim: string
  publisher: string
  title: string
  rating: string
  url: string
  review_date: string
}
type ModelPrediction = {
  status: 'available' | 'not_trained' | 'unavailable'
  benchmark_label: string | null
  label_description: string | null
  explanation: string | null
  message: string | null
}
type ModelComparison = {
  traditional: ModelPrediction
  transformer: ModelPrediction
}
type AnalysisResult = {
  submission_id: string | null
  benchmark_label: string
  label_description: string
  model_score: number
  top_signals: Signal[]
  counter_signals: Signal[]
  explanation: string
  model_comparison?: ModelComparison | null
  fact_checks: {
    status: 'not_configured' | 'unavailable' | 'no_matches' | 'matches'
    message: string
    items: FactCheck[]
  }
  notice: string
}
type SavedSubmission = {
  id: string
  headline: string
  article_text: string
  source_name: string | null
  source_url: string | null
  status: string
  created_at: string
  analysis_result: Omit<AnalysisResult, 'submission_id'> | null
}
type ThemeMode = 'light' | 'dark' | 'device'
type SubmissionStatus = 'received' | 'processing' | 'analyzed' | 'failed'
type HistorySort = 'newest' | 'oldest'

const HISTORY_PAGE_SIZE = 8
const baselineMetrics = [
  { label: 'Accuracy', value: 24.8 },
  { label: 'Macro-F1', value: 24.6 },
  { label: 'Macro-precision', value: 24.6 },
  { label: 'Macro-recall', value: 25.7 },
]
const classMetrics = [
  { label: 'Pants-fire', precision: 17.2, recall: 32.6 },
  { label: 'False', precision: 32.3, recall: 28.1 },
  { label: 'Barely-true', precision: 24.5, recall: 22.2 },
  { label: 'Half-true', precision: 25.7, recall: 20.4 },
  { label: 'Mostly-true', precision: 22.7, recall: 22.8 },
  { label: 'True', precision: 25.0, recall: 27.9 },
]
const SAMPLE_ARTICLE = {
  headline: 'Illustrative sample: City library expands weekend hours',
  articleText:
    'The city library announced that it will extend weekend opening hours beginning next month, according to a notice published on its website. This fictional sample is provided only to demonstrate the analysis workflow.',
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const THEME_STORAGE_KEY = 'truthlens-theme'

function getInitialTheme(): ThemeMode {
  const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)
  return savedTheme === 'light' || savedTheme === 'dark' || savedTheme === 'device'
    ? savedTheme
    : 'device'
}

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 32 32" fill="none">
        <path
          d="M16 3.5 26 7v7.4c0 6.4-4.1 11.4-10 14.1-5.9-2.7-10-7.7-10-14.1V7l10-3.5Z"
          stroke="currentColor"
          strokeWidth="1.8"
        />
        <path
          d="M11.5 15.5c1.2-1.6 2.7-2.4 4.5-2.4s3.3.8 4.5 2.4c-1.2 1.6-2.7 2.4-4.5 2.4s-3.3-.8-4.5-2.4Z"
          stroke="currentColor"
          strokeWidth="1.6"
        />
        <circle cx="16" cy="15.5" r="1.2" fill="currentColor" />
      </svg>
    </span>
  )
}

function formatStatus(status: string): string {
  switch (status) {
    case 'received':
      return 'Received'
    case 'processing':
      return 'Processing'
    case 'analyzed':
      return 'Analyzed'
    case 'failed':
      return 'Failed'
    default:
      return status ? `${status[0].toUpperCase()}${status.slice(1)}` : 'Unknown'
  }
}

function ArrowIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none">
      <path d="M4.2 10h11.6m-4.8-4.8 4.8 4.8-4.8 4.8" />
    </svg>
  )
}

function App() {
  const currentPage =
    window.location.pathname === '/history'
      ? 'history'
      : window.location.pathname === '/about'
        ? 'about'
        : 'analyze'
  const [navigationOpen, setNavigationOpen] = useState(false)
  const [themeMode, setThemeMode] = useState<ThemeMode>(getInitialTheme)
  const [headline, setHeadline] = useState('')
  const [articleText, setArticleText] = useState('')
  const [sourceName, setSourceName] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [modelReady, setModelReady] = useState<boolean | null>(null)
  const [apiConnected, setApiConnected] = useState(false)
  const [apiStatusLoading, setApiStatusLoading] = useState(true)
  const [savedSubmissions, setSavedSubmissions] = useState<SavedSubmission[]>([])
  const [selectedSubmission, setSelectedSubmission] = useState<SavedSubmission | null>(null)
  const [historyError, setHistoryError] = useState('')
  const [historyActionError, setHistoryActionError] = useState('')
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historySearch, setHistorySearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | SubmissionStatus>('all')
  const [historySort, setHistorySort] = useState<HistorySort>('newest')
  const [historyPage, setHistoryPage] = useState(1)
  const [reanalyzingId, setReanalyzingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    if (!navigationOpen) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setNavigationOpen(false)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [navigationOpen])

  useEffect(() => {
    const colorScheme = window.matchMedia('(prefers-color-scheme: dark)')
    const applyTheme = () => {
      const activeTheme =
        themeMode === 'device' ? (colorScheme.matches ? 'dark' : 'light') : themeMode
      document.documentElement.dataset.theme = activeTheme
    }

    applyTheme()
    window.localStorage.setItem(THEME_STORAGE_KEY, themeMode)

    if (themeMode === 'device') {
      colorScheme.addEventListener('change', applyTheme)
      return () => colorScheme.removeEventListener('change', applyTheme)
    }
  }, [themeMode])

  async function loadSubmissions() {
    setHistoryLoading(true)
    setHistoryError('')
    try {
      const response = await fetch(`${API_BASE_URL}/api/submissions?limit=20`)
      if (!response.ok) throw new Error(await getErrorDetail(response))
      setSavedSubmissions((await response.json()) as SavedSubmission[])
      setHistoryPage(1)
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : 'Could not load saved submissions.')
    } finally {
      setHistoryLoading(false)
    }
  }

  useEffect(() => {
    document.title =
      currentPage === 'history'
        ? 'Saved articles — TruthLens AI'
        : currentPage === 'about'
          ? 'About — TruthLens AI'
          : 'TruthLens AI — Read between the headlines'
  }, [currentPage])

  useEffect(() => {
    let active = true
    fetch(`${API_BASE_URL}/api/analysis/status`)
      .then(async (response) => {
        if (!response.ok) throw new Error('Analysis service is unavailable.')
        return (await response.json()) as { available: boolean }
      })
      .then((status) => {
        if (active) {
          setModelReady(status.available)
          setApiConnected(true)
          setApiStatusLoading(false)
        }
      })
      .catch(() => {
        if (active) {
          setModelReady(false)
          setApiConnected(false)
          setApiStatusLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    fetch(`${API_BASE_URL}/api/submissions?limit=20`)
      .then(async (response) => {
        if (!response.ok) throw new Error(await getErrorDetail(response))
        return (await response.json()) as SavedSubmission[]
      })
      .then((records) => {
        if (active) {
          setSavedSubmissions(records)
          setHistoryLoading(false)
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setHistoryError(
            error instanceof Error ? error.message : 'Could not load saved submissions.',
          )
          setHistoryLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [])

  const canAnalyze =
    headline.trim().length >= 5 &&
    headline.trim().length <= 300 &&
    articleText.trim().length >= 40 &&
    articleText.trim().length <= 20_000 &&
    apiConnected &&
    modelReady === true &&
    !submitting &&
    !result
  const headlineError =
    headline.trim().length > 0 && headline.trim().length < 5
      ? 'Enter at least 5 characters for the headline.'
      : ''
  const articleTextError =
    articleText.trim().length > 0 && articleText.trim().length < 40
      ? 'Enter at least 40 characters of article text.'
      : ''
  const filteredSubmissions = savedSubmissions
    .filter((submission) => {
      const matchesSearch = `${submission.headline} ${submission.source_name || ''}`
        .toLowerCase()
        .includes(historySearch.trim().toLowerCase())
      const matchesStatus = statusFilter === 'all' || submission.status === statusFilter
      return matchesSearch && matchesStatus
    })
    .sort((left, right) => {
      const dateDifference =
        new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
      return historySort === 'newest' ? -dateDifference : dateDifference
    })
  const historyPageCount = Math.max(1, Math.ceil(filteredSubmissions.length / HISTORY_PAGE_SIZE))
  const paginatedSubmissions = filteredSubmissions.slice(
    (historyPage - 1) * HISTORY_PAGE_SIZE,
    historyPage * HISTORY_PAGE_SIZE,
  )

  function loadSampleArticle() {
    setHeadline(SAMPLE_ARTICLE.headline)
    setArticleText(SAMPLE_ARTICLE.articleText)
    setSourceName('')
    setSourceUrl('')
    clearAnalysis()
  }

  async function reanalyzeSubmission(submission: SavedSubmission) {
    if (reanalyzingId !== null || deletingId !== null) return
    setReanalyzingId(submission.id)
    setHistoryActionError('')
    try {
      const response = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          headline: submission.headline,
          article_text: submission.article_text,
          source_name: submission.source_name,
          source_url: submission.source_url,
          submission_id: submission.id,
        }),
      })
      if (!response.ok) throw new Error(await getErrorDetail(response))

      const analysis = (await response.json()) as AnalysisResult
      const updatedSubmission: SavedSubmission = {
        ...submission,
        status: 'analyzed',
        analysis_result: analysis,
      }
      setSavedSubmissions((current) =>
        current.map((record) => (record.id === submission.id ? updatedSubmission : record)),
      )
      setSelectedSubmission(updatedSubmission)
    } catch (error) {
      setHistoryActionError(
        error instanceof Error ? error.message : 'Could not reanalyze this saved article.',
      )
    } finally {
      setReanalyzingId(null)
    }
  }

  async function deleteSubmission(submission: SavedSubmission) {
    if (deletingId !== null || reanalyzingId !== null) return
    const confirmed = window.confirm(
      `Permanently delete "${submission.headline}" and its saved analysis? This cannot be undone.`,
    )
    if (!confirmed) return

    setDeletingId(submission.id)
    setHistoryActionError('')
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/submissions/${encodeURIComponent(submission.id)}`,
        { method: 'DELETE' },
      )
      if (!response.ok) throw new Error(await getErrorDetail(response))

      setSavedSubmissions((current) =>
        current.filter((record) => record.id !== submission.id),
      )
      setSelectedSubmission((current) => (current?.id === submission.id ? null : current))
    } catch (error) {
      setHistoryActionError(
        error instanceof Error ? error.message : 'Could not delete this saved article.',
      )
    } finally {
      setDeletingId(null)
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setErrorMessage('')
    setResult(null)
    try {
      const submissionResponse = await fetch(`${API_BASE_URL}/api/submissions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          headline: headline.trim(),
          article_text: articleText.trim(),
          source_name: sourceName.trim() || null,
          source_url: sourceUrl.trim() || null,
        }),
      })
      if (!submissionResponse.ok) {
        const detail = await getErrorDetail(submissionResponse)
        throw new Error(detail)
      }

      const submission = (await submissionResponse.json()) as { id: string }
      await loadSubmissions()
      const analysisResponse = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          headline: headline.trim(),
          article_text: articleText.trim(),
          source_name: sourceName.trim() || null,
          source_url: sourceUrl.trim() || null,
          submission_id: submission.id,
        }),
      })
      if (!analysisResponse.ok) {
        const detail = await getErrorDetail(analysisResponse)
        throw new Error(`Submission saved (${submission.id}), but analysis failed: ${detail}`)
      }

      const analysis = (await analysisResponse.json()) as AnalysisResult
      setResult({ ...analysis, submission_id: submission.id })
      await loadSubmissions()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'The request failed unexpectedly.')
    } finally {
      setSubmitting(false)
    }
  }

  async function getErrorDetail(response: Response): Promise<string> {
    try {
      const body = (await response.json()) as { detail?: string }
      return body.detail || `The server returned HTTP ${response.status}.`
    } catch {
      return `The server returned HTTP ${response.status}.`
    }
  }

  function clearAnalysis() {
    setResult(null)
    setErrorMessage('')
  }

  function resetForm() {
    setHeadline('')
    setArticleText('')
    setSourceName('')
    setSourceUrl('')
    clearAnalysis()
  }

  function startAnotherAnalysis() {
    resetForm()
    document.getElementById('analyzer')?.scrollIntoView({ behavior: 'smooth' })
  }

  function renderSignalList(title: string, signals: Signal[]) {
    return (
      <div className="signal-group">
        <p className="roadmap-title">{title}</p>
        {signals.length ? (
          <div className="signal-list">
            {signals.map((signal, index) => (
              <span className="signal-chip" key={`${signal.term}-${index}`}>
                {signal.term}
              </span>
            ))}
          </div>
        ) : (
          <p className="small-muted">No strong token signals were available.</p>
        )}
      </div>
    )
  }

  function renderModelComparison(comparison: ModelComparison | null | undefined) {
    if (!comparison) {
      return (
        <p className="unavailable-note">
          This saved result predates model comparison and contains only one model prediction.
        </p>
      )
    }

    return (
      <div className="model-comparison-grid">
        {[
          { title: 'Traditional ML · TF-IDF + Logistic Regression', prediction: comparison.traditional },
          { title: 'Transformer · DistilBERT', prediction: comparison.transformer },
        ].map(({ title, prediction }) => (
          <article className="model-comparison-card" key={title}>
            <p className="section-kicker">{title}</p>
            {prediction.status === 'available' ? (
              <>
                <strong className="result-label">
                  {prediction.benchmark_label?.replaceAll('-', ' ') || 'Prediction unavailable'}
                </strong>
                {prediction.label_description && (
                  <p className="result-body-copy">{prediction.label_description}</p>
                )}
                {prediction.explanation && (
                  <p className="small-muted">{prediction.explanation}</p>
                )}
              </>
            ) : (
              <p className="unavailable-note">
                {prediction.message ||
                  (prediction.status === 'not_trained'
                    ? 'This model has not been trained yet.'
                    : 'This model is not currently available.')}
              </p>
            )}
          </article>
        ))}
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-left">
          <button
            className="page-menu-toggle"
            type="button"
            aria-label={navigationOpen ? 'Close page navigation' : 'Open page navigation'}
            aria-expanded={navigationOpen}
            aria-controls={navigationOpen ? 'page-navigation' : undefined}
            onClick={() => setNavigationOpen((open) => !open)}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <a className="brand" href="/" aria-label="TruthLens AI home">
            <BrandMark />
            <span>
              <strong>TruthLens</strong>
              <small>AI</small>
            </span>
          </a>
        </div>
        <div className="topbar-tools">
          <span className="prototype-badge">
            <span className="status-dot" />
            Research prototype
          </span>
          <label className="theme-control">
            <span className="visually-hidden">Color theme</span>
            <select
              aria-label="Color theme"
              value={themeMode}
              onChange={(event) => {
                const selectedTheme = event.currentTarget.value
                if (
                  selectedTheme === 'light' ||
                  selectedTheme === 'dark' ||
                  selectedTheme === 'device'
                ) {
                  setThemeMode(selectedTheme)
                }
              }}
            >
              <option value="light">Light</option>
              <option value="dark">Dark</option>
              <option value="device">Device</option>
            </select>
          </label>
        </div>
      </header>

      {navigationOpen && (
        <>
          <button
            className="page-menu-backdrop"
            type="button"
            aria-label="Close page navigation"
            onClick={() => setNavigationOpen(false)}
          />
          <aside className="page-sidebar" id="page-navigation" aria-label="Page navigation">
            <div className="page-sidebar-heading">
              <div>
                <p className="section-kicker">TRUTHLENS AI</p>
                <h2>Pages</h2>
              </div>
              <button
                className="page-sidebar-close"
                type="button"
                aria-label="Close page navigation"
                onClick={() => setNavigationOpen(false)}
              >
                <span aria-hidden="true">×</span>
              </button>
            </div>
            <nav className="page-sidebar-nav" aria-label="Pages">
              <a
                className={`page-nav-link ${currentPage === 'analyze' ? 'is-active' : ''}`}
                href="/"
                aria-current={currentPage === 'analyze' ? 'page' : undefined}
                onClick={() => setNavigationOpen(false)}
              >
                <span className="page-nav-number">01</span>
                <span><strong>Analyze</strong><small>Review a news article</small></span>
                <ArrowIcon />
              </a>
              <a
                className={`page-nav-link ${currentPage === 'history' ? 'is-active' : ''}`}
                href="/history"
                aria-current={currentPage === 'history' ? 'page' : undefined}
                onClick={() => setNavigationOpen(false)}
              >
                <span className="page-nav-number">02</span>
                <span><strong>Saved articles</strong><small>Browse previous reviews</small></span>
                <ArrowIcon />
              </a>
              <a
                className={`page-nav-link ${currentPage === 'about' ? 'is-active' : ''}`}
                href="/about"
                aria-current={currentPage === 'about' ? 'page' : undefined}
                onClick={() => setNavigationOpen(false)}
              >
                <span className="page-nav-number">03</span>
                <span><strong>About</strong><small>Methods and limitations</small></span>
                <ArrowIcon />
              </a>
            </nav>
            <p className="page-sidebar-note">
              Model predictions are research signals, not proof of truth or falsity.
            </p>
          </aside>
        </>
      )}

      <main>
        {currentPage === 'analyze' && (
          <>
        <section className="hero" id="about">
          <div className="hero-copy">
            <p className="eyebrow">
              <span className="eyebrow-line" />
              A clearer view of online claims
            </p>
            <h1>
              Read between the <span>headlines.</span>
            </h1>
            <p className="hero-description">
              Review language-model patterns alongside independently published
              fact-checks when available. TruthLens supports careful reading;
              it never decides whether a story is true.
            </p>
            <div className="hero-actions">
              <a className="primary-link" href="#analyzer">
                Analyze an article <ArrowIcon />
              </a>
              <a className="secondary-link" href="#how-it-works">
                Explore how it works
              </a>
            </div>
          </div>
          <aside className="hero-note" aria-label="Project principle">
            <div className="hero-principle">
              <div className="note-icon" aria-hidden="true">
                <BrandMark />
              </div>
              <p className="note-label">Prediction ≠ evidence</p>
              <p className="note-text">
                A model highlights learned language patterns. Fact-check reviews
                are separate sources to read and assess.
              </p>
            </div>
            <div className="workflow-preview" id="how-it-works">
              <div className="workflow-preview-heading">
                <p className="note-label">How a review works</p>
                <span>Illustrative</span>
              </div>
              <ol>
                <li><span>01</span>Submit an article</li>
                <li><span>02</span>Inspect language signals</li>
                <li><span>03</span>Open independent reviews</li>
              </ol>
              <p className="preview-disclaimer">
                Workflow preview only. No sample verdict or evidence is shown.
              </p>
            </div>
          </aside>
          <div className="hero-decoration" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
          </div>
        </section>

        <section className="research-snapshot" aria-labelledby="research-snapshot-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">A TRANSPARENT BASELINE</p>
              <h2 id="research-snapshot-title">What the model measured</h2>
            </div>
            <p className="section-aside">
              LIAR six-class benchmark · Traditional model · Held-out test split
            </p>
          </div>
          <div className="research-chart-grid">
            <figure className="research-chart-card">
              <figcaption className="research-chart-heading">
                <div>
                  <h3>Overall test metrics</h3>
                  <p>1,267 short political statements</p>
                </div>
                <span className="chart-tag">TEST SET</span>
              </figcaption>
              <div className="overall-metric-chart">
                {baselineMetrics.map((metric, index) => (
                  <div className="overall-metric-row" key={metric.label}>
                    <span>{metric.label}</span>
                    <div className="metric-track" aria-hidden="true">
                      <span
                        className="metric-fill"
                        style={{ width: `${metric.value}%`, animationDelay: `${index * 90}ms` }}
                      />
                    </div>
                    <strong>{metric.value.toFixed(1)}%</strong>
                  </div>
                ))}
              </div>
              <p className="chart-axis-note">Scale: 0–100%. Higher is not proof of factual accuracy.</p>
            </figure>

            <figure className="research-chart-card">
              <figcaption className="research-chart-heading">
                <div>
                  <h3>Per-label performance</h3>
                  <p>Macro-class precision and recall</p>
                </div>
                <div className="chart-legend" aria-label="Chart legend">
                  <span><i className="legend-swatch precision-swatch" />Precision</span>
                  <span><i className="legend-swatch recall-swatch" />Recall</span>
                </div>
              </figcaption>
              <div className="label-metric-chart">
                {classMetrics.map((metric, index) => (
                  <div className="label-metric-row" key={metric.label}>
                    <span className="label-metric-name">{metric.label}</span>
                    <div className="label-metric-bars" aria-hidden="true">
                      <div className="metric-track">
                        <span
                          className="metric-fill precision-fill"
                          style={{
                            width: `${(metric.precision / 40) * 100}%`,
                            animationDelay: `${index * 70}ms`,
                          }}
                        />
                      </div>
                      <div className="metric-track">
                        <span
                          className="metric-fill recall-fill"
                          style={{
                            width: `${(metric.recall / 40) * 100}%`,
                            animationDelay: `${index * 70 + 45}ms`,
                          }}
                        />
                      </div>
                    </div>
                    <strong>{metric.precision.toFixed(1)} / {metric.recall.toFixed(1)}%</strong>
                  </div>
                ))}
              </div>
              <p className="chart-axis-note">Bar scale: 0–40%. Values are shown as precision / recall.</p>
            </figure>
          </div>
          <p className="research-caveat">
            These scores describe predictions against LIAR dataset labels—not
            verification of real-world news articles. DistilBERT remains marked
            as not trained until a local fine-tuning run completes.
          </p>
        </section>

        <section className="workspace-section" id="analyzer">
          <div className="section-heading">
            <div>
              <p className="section-kicker">THE ANALYSIS WORKSPACE</p>
              <h2>Start with the story</h2>
            </div>
            <p className="section-aside">
              No verdicts without context. Share the article details below.
            </p>
          </div>

          <div className="workspace-grid">
            <form className="article-form" onSubmit={handleSubmit} aria-busy={submitting}>
              <div className="form-topline">
                <div className="step-number">01</div>
                <div>
                  <h3>Article details</h3>
                  <p>Paste a headline and the article text to get started.</p>
                </div>
                <button
                  className="sample-button"
                  type="button"
                  onClick={loadSampleArticle}
                  disabled={submitting}
                >
                  Use illustrative sample
                </button>
              </div>

              <label htmlFor="headline">Headline</label>
              <input
                id="headline"
                name="headline"
                type="text"
                placeholder="Paste or type the article headline"
                value={headline}
                aria-invalid={Boolean(headlineError)}
                aria-describedby={headlineError ? 'headline-hint headline-error' : 'headline-hint'}
                onChange={(event) => {
                  setHeadline(event.target.value)
                  clearAnalysis()
                }}
                onBlur={() => setHeadline((value) => value.trim())}
                minLength={5}
                maxLength={300}
                disabled={submitting}
                required
              />
              <div className="field-hint" id="headline-hint">
                <span>Use the headline as it appears in the source.</span>
                <span>{headline.length}/300</span>
              </div>
              {headlineError && (
                <p className="field-error" id="headline-error" role="alert">{headlineError}</p>
              )}

              <label htmlFor="article-text">Article text</label>
              <textarea
                id="article-text"
                name="article_text"
                placeholder="Paste the article or claim you want to examine…"
                value={articleText}
                aria-invalid={Boolean(articleTextError)}
                aria-describedby={articleTextError ? 'article-hint article-error' : 'article-hint'}
                onChange={(event) => {
                  setArticleText(event.target.value)
                  clearAnalysis()
                }}
                onBlur={() => setArticleText((value) => value.trim())}
                minLength={40}
                maxLength={20_000}
                rows={7}
                disabled={submitting}
                required
              />
              <div className="field-hint" id="article-hint">
                <span>At least 40 characters. Maximum 20,000.</span>
                <span>{articleText.length.toLocaleString()}/20,000</span>
              </div>
              {articleTextError && (
                <p className="field-error" id="article-error" role="alert">{articleTextError}</p>
              )}

              <div className="source-fields">
                <div>
                  <label htmlFor="source-name">Publisher <span>(optional)</span></label>
                  <input
                    id="source-name"
                    name="source_name"
                    type="text"
                    placeholder="e.g. Example News"
                    value={sourceName}
                    onChange={(event) => {
                      setSourceName(event.target.value)
                      clearAnalysis()
                    }}
                    maxLength={200}
                    disabled={submitting}
                  />
                </div>
                <div>
                  <label htmlFor="source-url">Article URL <span>(optional)</span></label>
                  <input
                    id="source-url"
                    name="source_url"
                    type="url"
                    placeholder="https://"
                    value={sourceUrl}
                    onChange={(event) => {
                      setSourceUrl(event.target.value)
                      clearAnalysis()
                    }}
                    disabled={submitting}
                  />
                </div>
              </div>

              <div className="form-actions">
                <button
                  className={`submit-button ${submitting ? 'is-loading' : ''} ${result ? 'is-complete' : ''}`}
                  type="submit"
                  disabled={!canAnalyze}
                >
                  {submitting ? 'Analyzing…' : result ? 'Analysis complete' : 'Analyze article'}
                  {submitting ? (
                    <span className="button-spinner" aria-hidden="true" />
                  ) : result ? (
                    <span aria-hidden="true">✓</span>
                  ) : (
                    <ArrowIcon />
                  )}
                </button>
                <button
                  className="reset-button"
                  type="button"
                  onClick={resetForm}
                  disabled={submitting}
                >
                  Clear
                </button>
              </div>
              <p className="privacy-note">
                Submitting saves this article locally and sends its headline to the optional fact-check search.
              </p>
            </form>

            <aside className="analysis-card" aria-label="Analysis review">
              <div className="analysis-card-header">
                <div>
                  <p className="section-kicker">YOUR REVIEW</p>
                  <h3>Analysis overview</h3>
                </div>
                <span className="not-connected">
                  <span className={`status-dot ${apiConnected ? 'connected' : ''}`} />
                  {!apiConnected ? 'API unavailable' : modelReady ? 'Model ready' : 'Model not ready'}
                </span>
              </div>

              {errorMessage ? (
                <div className="error-message" role="alert">
                  <strong>Analysis could not be completed</strong>
                  <p>{errorMessage}</p>
                  <a href="/history">Check saved articles</a>
                </div>
              ) : submitting ? (
                <div className="analysis-loading" role="status" aria-live="polite">
                  <span className="loading-spinner" aria-hidden="true" />
                  <h4>Review in progress</h4>
                  <p>
                    Saving your article and requesting the configured classifier
                    and available fact-check reviews.
                  </p>
                  <p className="small-muted">A model label is not a truth verdict.</p>
                </div>
              ) : result ? (
                <div className="analysis-result" aria-label="Analysis result">
                  <div className="result-summary">
                    <span className="review-status">Needs further verification</span>
                    <p className="section-kicker">ANALYSIS SUMMARY</p>
                    <h4>{result.label_description}</h4>
                    <p>
                      The configured classifier matched this statement to a
                      LIAR benchmark category. This is a learned language
                      association, not an assessment of truth.
                    </p>
                  </div>
                  <div className="result-details-grid">
                    <section className="result-section">
                      <p className="section-kicker">CONFIGURED MODEL PREDICTION</p>
                      <div className="result-label">
                        {result.benchmark_label.replaceAll('-', ' ')}
                      </div>
                      <p className="result-body-copy">{result.explanation}</p>
                      <dl className="model-metadata">
                        <div><dt>Architecture</dt><dd>Not provided by the API</dd></div>
                        <div><dt>Model version</dt><dd>Not provided by the API</dd></div>
                      </dl>
                    </section>
                    <section className="result-section">
                      <p className="section-kicker">MODEL COMPARISON</p>
                      {renderModelComparison(result.model_comparison)}
                    </section>
                  </div>

                  <section className="result-section result-evidence">
                    <p className="section-kicker">LANGUAGE SIGNALS</p>
                    <p className="result-body-copy">
                      Terms associated with the selected benchmark class—not
                      supporting evidence about the article.
                    </p>
                    {renderSignalList('ASSOCIATED TERMS', result.top_signals)}
                    {renderSignalList('COUNTER-SIGNALS', result.counter_signals)}
                  </section>

                  <section className="result-section result-evidence">
                    <p className="section-kicker">CLAIM-BY-CLAIM EVIDENCE</p>
                    <p className="unavailable-note">
                      Claim extraction and claim-level evidence are not provided
                      by the current API. External fact-check reviews below are
                      shown separately.
                    </p>
                  </section>

                  <section className="result-section result-evidence fact-check-results">
                    <p className="section-kicker">EXTERNAL FACT-CHECK REVIEWS</p>
                    <p className="result-body-copy">{result.fact_checks.message}</p>
                    <p className="result-body-copy">
                      Ratings and conclusions are attributed to each publisher;
                      the API does not map reviews as support or contradiction
                      for the full article.
                    </p>
                    {result.fact_checks.items.length > 0 ? (
                      result.fact_checks.items.map((item) => (
                        <article className="fact-check-item" key={item.url}>
                          <p>
                            {item.publisher}
                            {item.review_date ? ` · ${item.review_date}` : ''}
                          </p>
                          <a href={item.url} target="_blank" rel="noreferrer">
                            {item.title}
                          </a>
                          <strong>{item.rating}</strong>
                          <p>Review of: {item.claim}</p>
                        </article>
                      ))
                    ) : (
                      <p className="unavailable-note">
                        No linked review is available for this submission. This
                        is not evidence that the claim is true or false.
                      </p>
                    )}
                  </section>

                  {sourceUrl && (
                    <section className="result-section result-source">
                      <p className="section-kicker">SUBMITTED ARTICLE SOURCE</p>
                      <a href={sourceUrl} target="_blank" rel="noreferrer">
                        {sourceName || sourceUrl}
                      </a>
                      <p>This is the article source provided by you, not independent corroboration.</p>
                    </section>
                  )}

                  <section className="result-section result-limitations">
                    <p className="section-kicker">LIMITATIONS</p>
                    <p className="result-body-copy">{result.notice}</p>
                    <p className="result-body-copy">
                      The LIAR benchmark contains short political statements.
                      Performance on that dataset may not generalize to full
                      news articles or other topics.
                    </p>
                  </section>

                  <div className="result-actions">
                    <span className="saved-confirmation">
                      {result.submission_id ? 'Analysis saved with this article' : 'Analysis complete'}
                    </span>
                    {result.submission_id && (
                      <a className="secondary-action" href="/history">View saved articles</a>
                    )}
                    <button className="reset-button" type="button" onClick={startAnotherAnalysis}>
                      Analyze another article
                    </button>
                  </div>
                </div>
              ) : apiStatusLoading ? (
                <div className="analysis-loading" role="status" aria-live="polite">
                  <span className="loading-spinner" aria-hidden="true" />
                  <h4>Connecting to the analysis service</h4>
                  <p>Checking model availability before you submit an article.</p>
                </div>
              ) : !apiConnected ? (
                <div className="error-message" role="status">
                  <strong>Analysis service unavailable</strong>
                  <p>
                    The frontend cannot reach the API at {API_BASE_URL}. Start
                    the FastAPI server and refresh this page to analyze articles.
                  </p>
                </div>
              ) : modelReady === false && apiConnected ? (
                <div className="empty-analysis service-not-ready" role="status">
                  <h4>Analysis model is not ready</h4>
                  <p>
                    The API is reachable, but its configured classifier is not
                    available. Your article will not be labeled until the model
                    is ready.
                  </p>
                </div>
              ) : (
                <div className="empty-analysis">
                  <div className="empty-art" aria-hidden="true">
                    <div className="empty-art-ring ring-one" />
                    <div className="empty-art-ring ring-two" />
                    <div className="empty-art-center">
                      <BrandMark />
                    </div>
                    <span className="orbit-dot dot-one" />
                    <span className="orbit-dot dot-two" />
                    <span className="orbit-dot dot-three" />
                  </div>
                  <h4>Waiting for an article</h4>
                  <p>
                    Submit a headline and article text to request a benchmark
                    label and any configured, independent fact-check reviews.
                  </p>
                </div>
              )}

            </aside>
          </div>
        </section>
          </>
        )}

        {currentPage === 'history' && (
        <section className="saved-section" id="saved-submissions">
          <div className="section-heading">
            <div>
              <p className="section-kicker">DATABASE HISTORY</p>
              <h2>Saved articles</h2>
            </div>
            <button
              className="secondary-action refresh-button"
              type="button"
              onClick={() => void loadSubmissions()}
              disabled={historyLoading}
            >
              {historyLoading ? 'Loading articles…' : 'Refresh articles'}
            </button>
          </div>
          <p className="history-intro">
            Search and review recent submissions. The current API returns up to
            20 records per request.
          </p>
          <div className="history-controls">
            <label>
              <span>Search articles</span>
              <input
                type="search"
                placeholder="Search headline or publisher"
                value={historySearch}
                onChange={(event) => {
                  setHistorySearch(event.target.value)
                  setHistoryPage(1)
                }}
              />
            </label>
            <label>
              <span>Status</span>
              <select
                value={statusFilter}
                onChange={(event) => {
                  const value = event.currentTarget.value
                  if (
                    value === 'all' ||
                    value === 'received' ||
                    value === 'processing' ||
                    value === 'analyzed' ||
                    value === 'failed'
                  ) {
                    setStatusFilter(value)
                    setHistoryPage(1)
                  }
                }}
              >
                <option value="all">All statuses</option>
                <option value="received">Received</option>
                <option value="processing">Processing</option>
                <option value="analyzed">Analyzed</option>
                <option value="failed">Failed</option>
              </select>
            </label>
            <label>
              <span>Date</span>
              <select
                value={historySort}
                onChange={(event) => {
                  const value = event.currentTarget.value
                  if (value === 'newest' || value === 'oldest') setHistorySort(value)
                  setHistoryPage(1)
                }}
              >
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
              </select>
            </label>
          </div>

          {historyError ? (
            <p className="history-error" role="alert">{historyError}</p>
          ) : historyLoading && savedSubmissions.length === 0 ? (
            <div className="empty-history" role="status">Loading your saved articles…</div>
          ) : savedSubmissions.length === 0 ? (
            <div className="empty-history">
              <strong>No articles saved yet</strong>
              <p>Analyze an article to save its submission and review its result here.</p>
              <a className="secondary-action" href="/#analyzer">Analyze an article</a>
            </div>
          ) : paginatedSubmissions.length === 0 ? (
            <div className="empty-history">
              <strong>No matching articles</strong>
              <p>Try changing the search phrase or status filter.</p>
            </div>
          ) : (
            <div className="saved-list">
              {paginatedSubmissions.map((submission) => {
                const isReanalyzing = reanalyzingId === submission.id
                const isDeleting = deletingId === submission.id
                const isProcessing = isReanalyzing || isDeleting
                const displayStatus = isProcessing ? 'Processing' : formatStatus(submission.status)
                return (
                  <article className="saved-item" key={submission.id}>
                    <div className="saved-item-content">
                      <div className="saved-item-heading">
                        <button
                          className="saved-headline"
                          type="button"
                          onClick={() => setSelectedSubmission(submission)}
                        >
                          {submission.headline}
                        </button>
                        <span className="saved-status" data-status={isProcessing ? 'processing' : submission.status}>
                          {displayStatus}
                        </span>
                      </div>
                      <p className="saved-meta">
                        {submission.source_name || 'Publisher not provided'}
                        <span aria-hidden="true"> · </span>
                        <time dateTime={submission.created_at}>
                          {new Date(submission.created_at).toLocaleString()}
                        </time>
                      </p>
                      <p className="saved-model-version">
                        {submission.analysis_result
                          ? 'Model version not provided by API'
                          : 'No prediction saved for this submission'}
                      </p>
                    </div>
                    <div className="saved-item-actions">
                      <button
                        className="text-action"
                        type="button"
                        onClick={() => setSelectedSubmission(submission)}
                        disabled={!submission.analysis_result}
                      >
                        View analysis
                      </button>
                      <button
                        className="text-action"
                        type="button"
                        onClick={() => void reanalyzeSubmission(submission)}
                        disabled={
                          reanalyzingId !== null ||
                          deletingId !== null ||
                          !apiConnected ||
                          !modelReady
                        }
                      >
                        {isReanalyzing ? 'Reanalyzing…' : 'Reanalyze'}
                      </button>
                      <button
                        className="text-action destructive-action"
                        type="button"
                        onClick={() => void deleteSubmission(submission)}
                        disabled={deletingId !== null || reanalyzingId !== null || !apiConnected}
                      >
                        {isDeleting ? 'Deleting…' : 'Delete'}
                      </button>
                    </div>
                  </article>
                )
              })}
            </div>
          )}

          {historyActionError && (
            <p className="history-error" role="alert">{historyActionError}</p>
          )}
          {filteredSubmissions.length > HISTORY_PAGE_SIZE && (
            <nav className="pagination" aria-label="Saved article pages">
              <button
                className="secondary-action"
                type="button"
                onClick={() => setHistoryPage((page) => Math.max(1, page - 1))}
                disabled={historyPage === 1}
              >
                Previous
              </button>
              <span>Page {historyPage} of {historyPageCount}</span>
              <button
                className="secondary-action"
                type="button"
                onClick={() => setHistoryPage((page) => Math.min(historyPageCount, page + 1))}
                disabled={historyPage === historyPageCount}
              >
                Next
              </button>
            </nav>
          )}
          {selectedSubmission && (
            <article className="saved-detail">
              <div className="saved-detail-heading">
                <div>
                  <p className="section-kicker">DATABASE RECORD</p>
                  <h3>{selectedSubmission.headline}</h3>
                </div>
                <button
                  className="reset-button"
                  type="button"
                  onClick={() => setSelectedSubmission(null)}
                >
                  Close
                </button>
              </div>
              <p className="saved-detail-meta">
                ID: {selectedSubmission.id} · Saved {new Date(selectedSubmission.created_at).toLocaleString()}
              </p>
              <p className="saved-article-text">{selectedSubmission.article_text}</p>
              {selectedSubmission.analysis_result ? (
                <div className="saved-analysis">
                  <p className="section-kicker">SAVED BENCHMARK-MODEL ANALYSIS</p>
                  <span className="review-status">Needs further verification</span>
                  <h3>{selectedSubmission.analysis_result.label_description}</h3>
                  <p>{selectedSubmission.analysis_result.explanation}</p>
                  <p className="saved-model-version">Model version not provided by API.</p>
                  <div className="saved-citations">
                    <p className="section-kicker">TRADITIONAL ML AND TRANSFORMER</p>
                    {renderModelComparison(
                      selectedSubmission.analysis_result.model_comparison,
                    )}
                  </div>
                  <div className="saved-citations">
                    <p className="section-kicker">LANGUAGE SIGNALS</p>
                    {renderSignalList(
                      'ASSOCIATED TERMS',
                      selectedSubmission.analysis_result.top_signals,
                    )}
                    {renderSignalList(
                      'COUNTER-SIGNALS',
                      selectedSubmission.analysis_result.counter_signals,
                    )}
                  </div>
                  <div className="saved-citations">
                    <p className="section-kicker">EXTERNAL FACT-CHECK REVIEWS</p>
                    <p className="saved-review-message">
                      {selectedSubmission.analysis_result.fact_checks.message}
                    </p>
                    {selectedSubmission.analysis_result.fact_checks.items.map((item) => (
                      <article className="fact-check-item" key={item.url}>
                        <p>
                          {item.publisher}
                          {item.review_date ? ` · ${item.review_date}` : ''}
                        </p>
                        <a href={item.url} target="_blank" rel="noreferrer">{item.title}</a>
                        <strong>{item.rating}</strong>
                        <p>Review of: {item.claim}</p>
                      </article>
                    ))}
                  </div>
                  <p className="result-notice">{selectedSubmission.analysis_result.notice}</p>
                  {selectedSubmission.analysis_result.fact_checks.items.length > 0 && (
                    <p className="saved-model-version">
                      External review links open their original publisher pages.
                    </p>
                  )}
                </div>
              ) : (
                <div className="saved-analysis unavailable-note">
                  <strong>Not analyzed</strong>
                  <p>No model prediction is available for this article yet.</p>
                </div>
              )}
              {selectedSubmission.source_url && (
                <a href={selectedSubmission.source_url} target="_blank" rel="noreferrer">
                  Open submitted article source
                </a>
              )}
              <div className="saved-detail-actions">
                <button
                  className="text-action"
                  type="button"
                  onClick={() => void reanalyzeSubmission(selectedSubmission)}
                  disabled={
                    reanalyzingId !== null ||
                    deletingId !== null ||
                    !apiConnected ||
                    !modelReady
                  }
                >
                  {reanalyzingId === selectedSubmission.id ? 'Reanalyzing…' : 'Reanalyze'}
                </button>
                <button
                  className="text-action destructive-action"
                  type="button"
                  onClick={() => void deleteSubmission(selectedSubmission)}
                  disabled={deletingId !== null || reanalyzingId !== null || !apiConnected}
                >
                  {deletingId === selectedSubmission.id ? 'Deleting…' : 'Delete article'}
                </button>
                <p className="small-muted">
                  Deleting permanently removes this article and its saved analysis.
                </p>
              </div>
            </article>
          )}
        </section>
        )}

        {currentPage === 'about' && (
          <section className="about-page">
            <div className="about-hero">
              <p className="eyebrow"><span className="eyebrow-line" />ABOUT TRUTHLENS AI</p>
              <h1>Context over <span>certainty.</span></h1>
              <p>
                TruthLens is a research prototype that helps readers examine a
                news statement using language-model signals and separately
                identified external fact-check reviews.
              </p>
            </div>
            <div className="about-grid">
              <article className="about-card">
                <span className="about-number">01</span>
                <h2>What happens to an article?</h2>
                <p>
                  The article text is saved in the selected database. The
                  classifier compares it with patterns from the LIAR benchmark
                  and stores its label, score, and token signals alongside the
                  saved submission.
                </p>
              </article>
              <article className="about-card">
                <span className="about-number">02</span>
                <h2>What does a label mean?</h2>
                <p>
                  It describes the benchmark class that the model most
                  associated with the text. It is not a probability that the
                  story is true, nor independent fact verification.
                </p>
              </article>
              <article className="about-card">
                <span className="about-number">03</span>
                <h2>Where does the evidence come from?</h2>
                <p>
                  External reviews, when configured and found, are shown with
                  their publisher, rating, and source link. No match means the
                  search found no review; it does not mean a claim is true.
                </p>
              </article>
            </div>
            <section className="methodology-panel" aria-labelledby="model-evaluation-title">
              <p className="section-kicker">MODEL & EVALUATION</p>
              <h2 id="model-evaluation-title">Experimental models, measured transparently</h2>
              <dl className="metrics-grid">
                <div><dt>Dataset</dt><dd>LIAR six-class benchmark</dd></div>
                <div><dt>Traditional architecture</dt><dd>TF-IDF uni/bigrams + Logistic Regression</dd></div>
                <div><dt>Traditional test accuracy</dt><dd>24.8%</dd></div>
                <div><dt>Traditional macro-F1</dt><dd>24.6%</dd></div>
                <div><dt>Traditional macro-precision</dt><dd>24.6%</dd></div>
                <div><dt>Traditional macro-recall</dt><dd>25.7%</dd></div>
                <div><dt>Evaluation method</dt><dd>Provided train/validation/test partitions; metrics reported on the held-out test split</dd></div>
              </dl>
              <p className="methodology-limitations">
                LIAR contains short political statements, not full news articles.
                Results are weak and may not generalize. DistilBERT is reported
                separately when its local fine-tuning and held-out evaluation
                are complete. Neither model verifies an article's claims.
              </p>
              <a className="text-link" href="/#analyzer">
                Try the analyzer <ArrowIcon />
              </a>
            </section>
          </section>
        )}

        <section className="trust-strip" aria-label="Project commitments">
          <div>
            <span className="trust-icon" aria-hidden="true">01</span>
            <p><strong>Evidence first</strong><br />Sources should be visible.</p>
          </div>
          <div>
            <span className="trust-icon" aria-hidden="true">02</span>
            <p><strong>Uncertainty matters</strong><br />Not every claim is classifiable.</p>
          </div>
          <div>
            <span className="trust-icon" aria-hidden="true">03</span>
            <p><strong>People decide</strong><br />AI supports, never replaces, judgment.</p>
          </div>
        </section>
      </main>

      <footer className="footer">
        <a className="brand footer-brand" href="/" aria-label="TruthLens AI home">
          <BrandMark />
          <span>
            <strong>TruthLens</strong>
            <small>AI</small>
          </span>
        </a>
        <p>Built for thoughtful reading. Not a substitute for independent verification.</p>
        <span className="footer-version">TRUTHLENS AI · RESEARCH PROTOTYPE</span>
      </footer>
    </div>
  )
}

export default App
