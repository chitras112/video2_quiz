import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

const API = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
const ACCEPTED_EXTENSIONS = ['.mp4', '.mov', '.mkv', '.webm', '.avi']

function Icon({ name, size = 20 }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.6a8 8 0 0 1-1.6.9l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.6-.9l-1.7.6-1.4-2.4 1.4-1.1a7 7 0 0 1 0-1.9l-1.4-1.1 1.4-2.4 1.7.6a8 8 0 0 1 1.6-.9l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.6.9l1.7-.6 1.4 2.4-1.4 1.1a7 7 0 0 1-.1 1.8Z"/></>,
    play: <><path d="m8 5 11 7-11 7V5Z"/></>,
    upload: <><path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5"/><path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/></>,
    link: <><path d="M10 13a5 5 0 0 0 7.1 0l2-2A5 5 0 0 0 12 3.9l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.1 0l-2 2A5 5 0 0 0 12 20.1l1.1-1.1"/></>,
    arrow: <><path d="M7 17 17 7M7 7h10v10"/></>,
    check: <><path d="m5 12 4 4L19 6"/></>,
    refresh: <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.6 9a7 7 0 0 1 11.6-2L20 12M4 12l2.8 5a7 7 0 0 0 11.6-2"/></>,
    spark: <><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z"/><path d="m19 16 .9 2.1L22 19l-2.1.9L19 22l-.9-2.1L16 19l2.1-.9L19 16Z"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    alert: <><path d="M10.3 4.3 2.8 17.2A2 2 0 0 0 4.5 20h15a2 2 0 0 0 1.7-2.8L13.7 4.3a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4m0 3h.01"/></>,
  }
  return <svg {...common}>{paths[name] || paths.spark}</svg>
}

function formatDate(value) {
  if (!value) return 'Time unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Time unavailable' : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

function statusLabel(status = 'unknown') {
  return status.replaceAll('_', ' ')
}

function processingStages(status) {
  const states = {
    uploaded: [2, 0, 0, 0],
    extracting_audio: [2, 1, 0, 0],
    transcribing: [2, 2, 1, 0],
    generating_quiz: [2, 2, 2, 1],
    completed: [2, 2, 2, 2],
    completed_no_speech: [2, 2, 2, 3],
  }
  if (status === 'downloading') return [1, 0, 0, 0]
  return states[status] || [0, 0, 0, 0]
}

function App() {
  const [file, setFile] = useState(null)
  const [url, setUrl] = useState('')
  const [videos, setVideos] = useState([])
  const [showAllVideos, setShowAllVideos] = useState(false)
  const [videosLoading, setVideosLoading] = useState(true)
  const [videoError, setVideoError] = useState('')
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [grading, setGrading] = useState(false)
  const [starting, setStarting] = useState(false)
  const [message, setMessage] = useState('')
  const [selected, setSelected] = useState(null)
  const [quiz, setQuiz] = useState(null)
  const [quizLoading, setQuizLoading] = useState(false)
  const [quizError, setQuizError] = useState('')
  const [examStarted, setExamStarted] = useState(false)
  const [persistentExam, setPersistentExam] = useState(true)
  const [answers, setAnswers] = useState({})
  const [evaluation, setEvaluation] = useState(null)
  const [transcript, setTranscript] = useState('')
  const [attempt, setAttempt] = useState(null)
  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [historyResult, setHistoryResult] = useState(null)
  const [historyResultLoading, setHistoryResultLoading] = useState(false)
  const [historyResultError, setHistoryResultError] = useState('')
  const [submissionRetryLocked, setSubmissionRetryLocked] = useState(false)
  const startKeyRef = useRef(null)
  const startingRef = useRef(false)
  const submittingRef = useRef(false)
  const submissionPayloadRef = useRef(null)
  const fileInputRef = useRef(null)
  const autoLoadedRef = useRef(null)

  async function refresh({ silent = false } = {}) {
    if (!silent) setVideosLoading(true)
    try {
      const response = await fetch(`${API}/videos`)
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw Error(result.detail || 'Could not load your videos.')
      const allVideos = Array.isArray(result) ? result : []
      setVideos(allVideos)
      setVideoError('')
      setSelected(current => current ? (allVideos.find(video => video.id === current.id) || current) : current)
    } catch (error) {
      setVideoError(error.message || `Cannot reach the API at ${API}.`)
    } finally {
      if (!silent) setVideosLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    const timer = setInterval(() => refresh({ silent: true }), 5000)
    return () => clearInterval(timer)
  }, [])

  const stats = useMemo(() => ({
    total: videos.length,
    ready: videos.filter(video => video.status === 'completed').length,
    processing: videos.filter(video => ['downloading', 'uploaded', 'extracting_audio', 'transcribing', 'generating_quiz'].includes(video.status)).length,
    failed: videos.filter(video => video.status === 'failed').length,
  }), [videos])

  const sortedVideos = useMemo(() => videos
    .map((video, index) => ({ video, index, timestamp: Date.parse(video.created_at || '') }))
    .sort((a, b) => {
      const aValid = Number.isFinite(a.timestamp)
      const bValid = Number.isFinite(b.timestamp)
      if (aValid && bValid) return b.timestamp - a.timestamp || a.index - b.index
      if (aValid) return -1
      if (bValid) return 1
      return a.index - b.index
    })
    .map(({ video }) => video), [videos])
  const displayedVideos = showAllVideos ? sortedVideos : sortedVideos.slice(0, 3)

  async function loadAttemptHistory(videoId) {
    if (!Number.isInteger(Number(videoId)) || Number(videoId) <= 0) {
      setHistoryError('This video has an invalid ID.')
      return
    }
    setHistoryLoading(true)
    setHistoryError('')
    try {
      const response = await fetch(`${API}/videos/${videoId}/attempts`)
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw Error(result.detail || 'Could not load exam history.')
      setHistory(Array.isArray(result) ? result : [])
    } catch (error) {
      setHistoryError(error.message || 'Could not load exam history.')
    } finally {
      setHistoryLoading(false)
    }
  }

  async function loadDetails(videoId) {
    setQuizLoading(true)
    setQuizError('')
    try {
      const [quizResponse, transcriptResponse] = await Promise.all([
        fetch(`${API}/videos/${videoId}/quiz`),
        fetch(`${API}/videos/${videoId}/transcript`),
      ])
      if (quizResponse.ok) {
        setQuiz(await quizResponse.json())
      } else if (quizResponse.status !== 409) {
        const error = await quizResponse.json().catch(() => ({}))
        setQuizError(error.detail || 'Could not load quiz questions. Try again.')
      }
      if (transcriptResponse.ok) setTranscript((await transcriptResponse.json()).text || '')
    } catch {
      setQuizError('Could not connect to the API while loading this video.')
    } finally {
      setQuizLoading(false)
    }
  }

  async function openVideo(video) {
    if (!Number.isInteger(Number(video?.id)) || Number(video.id) <= 0) {
      setMessage('This video has an invalid ID. Refresh the video list and try again.')
      return
    }
    setSelected(video)
    setQuiz(null)
    setExamStarted(false)
    setPersistentExam(true)
    setAnswers({})
    setEvaluation(null)
    setAttempt(null)
    setTranscript('')
    setHistory([])
    setHistoryResult(null)
    setHistoryResultError('')
    setHistoryError('')
    setQuizError('')
    startKeyRef.current = null
    submissionPayloadRef.current = null
    setSubmissionRetryLocked(false)
    loadAttemptHistory(video.id)
    await loadDetails(video.id)
  }

  useEffect(() => {
    const loadKey = selected ? `${selected.id}:${selected.status}` : null
    if (selected && ['completed', 'completed_no_speech'].includes(selected.status) && !quiz && !quizLoading && autoLoadedRef.current !== loadKey) {
      autoLoadedRef.current = loadKey
      loadDetails(selected.id)
    }
  }, [selected?.id, selected?.status, quiz, quizLoading])

  function chooseFile(nextFile) {
    if (!nextFile) return
    const extension = `.${nextFile.name.split('.').pop()?.toLowerCase()}`
    if (!ACCEPTED_EXTENSIONS.includes(extension)) {
      setFile(null)
      setMessage(`Unsupported format. Choose ${ACCEPTED_EXTENSIONS.join(', ')}.`)
      return
    }
    setMessage('')
    setFile(nextFile)
  }

  async function upload() {
    if (!file) return setMessage('Choose a video file first.')
    const data = new FormData()
    data.append('file', file)
    setBusy(true)
    setMessage('Uploading video…')
    try {
      const response = await fetch(`${API}/videos/upload`, { method: 'POST', body: data })
      const result = await response.json()
      if (!response.ok) throw Error(result.detail || 'Upload failed.')
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      setMessage(`Video #${result.id} was accepted. Processing status will update here.`)
      await refresh({ silent: true })
      await openVideo(result)
    } catch (error) {
      setMessage(error.message || 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }

  async function youtube() {
    if (!url.trim()) return setMessage('Paste a YouTube URL first.')
    setBusy(true)
    setMessage('Submitting YouTube URL…')
    try {
      const response = await fetch(`${API}/videos/youtube`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim() }),
      })
      const result = await response.json()
      if (!response.ok) throw Error(result.detail || 'Could not submit this URL.')
      setUrl('')
      setMessage(`YouTube video #${result.id} was accepted. Download and processing status will update here.`)
      await refresh({ silent: true })
      await openVideo(result)
    } catch (error) {
      setMessage(error.message || 'Could not submit this URL.')
    } finally {
      setBusy(false)
    }
  }

  async function openAttemptResult(attemptId) {
    if (!Number.isInteger(Number(attemptId)) || Number(attemptId) <= 0) {
      setHistoryResultError('This exam attempt has an invalid ID.')
      return
    }
    setHistoryResultLoading(true)
    setHistoryResultError('')
    try {
      const response = await fetch(`${API}/videos/attempts/${attemptId}`)
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw Error(result.detail || 'Could not load the saved exam result.')
      setHistoryResult(result)
    } catch (error) {
      setHistoryResultError(error.message || 'Could not load the saved exam result.')
    } finally {
      setHistoryResultLoading(false)
    }
  }

  function newIdempotencyKey() {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
    return `exam-${Date.now()}-${Math.random().toString(36).slice(2)}`
  }

  async function startExam() {
    if (!selected?.id || startingRef.current) return
    startingRef.current = true
    setStarting(true)
    setMessage('')
    if (!startKeyRef.current) startKeyRef.current = newIdempotencyKey()
    setAnswers({})
    setEvaluation(null)
    setHistoryResult(null)
    setHistoryResultError('')
    submissionPayloadRef.current = null
    setSubmissionRetryLocked(false)
    try {
      const response = await fetch(`${API}/videos/${selected.id}/attempts`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idempotency_key: startKeyRef.current }),
      })
      const result = await response.json().catch(() => ({}))
      if (response.status === 503 && String(result.detail || '').includes('Persistent exam attempts are temporarily unavailable')) {
        setAttempt(null)
        setPersistentExam(false)
        setExamStarted(true)
        setMessage('Persistent exam history is unavailable. You can take and grade this quiz, but the result will not be saved.')
        startKeyRef.current = null
        return
      }
      if (!response.ok) throw Error(result.detail || 'Could not start this exam.')
      setAttempt(result)
      setPersistentExam(true)
      setQuiz(current => ({ ...current, ...result }))
      setExamStarted(true)
      startKeyRef.current = null
    } catch (error) {
      setMessage(error.message || 'Could not start this exam. Retry to continue.')
    } finally {
      startingRef.current = false
      setStarting(false)
    }
  }

  async function submitExam() {
    if ((persistentExam && !attempt?.attempt_id) || !quiz?.questions?.length || submittingRef.current) return
    submittingRef.current = true
    setGrading(true)
    setMessage('')
    if (!submissionPayloadRef.current) submissionPayloadRef.current = { answers: { ...answers } }
    try {
      const submitUrl = persistentExam
        ? `${API}/videos/attempts/${attempt.attempt_id}/submit`
        : `${API}/videos/${selected.id}/evaluate`
      const response = await fetch(submitUrl, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(submissionPayloadRef.current),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) {
        if (!persistentExam || response.status < 500) {
          submissionPayloadRef.current = null
          setSubmissionRetryLocked(false)
        } else setSubmissionRetryLocked(true)
        throw Error(result.detail || 'Could not save this submission. Retry to check its status.')
      }
      setEvaluation(result)
      submissionPayloadRef.current = null
      setSubmissionRetryLocked(false)
      if (persistentExam) await loadAttemptHistory(selected.id)
    } catch (error) {
      setSubmissionRetryLocked(Boolean(submissionPayloadRef.current))
      setMessage(submissionPayloadRef.current
        ? `${error.message || 'Could not save this submission.'} Retry to check the saved result; the same answers will be sent.`
        : (error.message || 'Could not save this submission.'))
    } finally {
      submittingRef.current = false
      setGrading(false)
    }
  }

  function retakeExam() {
    setAnswers({})
    setEvaluation(null)
    setExamStarted(false)
    setPersistentExam(true)
    setAttempt(null)
    setHistoryResult(null)
    setHistoryResultError('')
    startKeyRef.current = null
    submissionPayloadRef.current = null
    setSubmissionRetryLocked(false)
  }

  function questionTimestamp(question) {
    if (question.timestamp_seconds == null) return null
    const seconds = Math.max(0, Math.floor(Number(question.timestamp_seconds) || 0))
    const time = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
    if (selected?.source_type === 'youtube' && selected.source_url) {
      try {
        const target = new URL(selected.source_url)
        target.searchParams.set('t', `${seconds}s`)
        return <a className="timestamp-link" href={target.toString()} target="_blank" rel="noreferrer">Jump to {time} in YouTube <Icon name="arrow" size={13}/></a>
      } catch { /* Show the timestamp as text when the source URL is malformed. */ }
    }
    return <span className="timestamp-link">Video timestamp {time}</span>
  }

  function processingView(video) {
    const values = processingStages(video.status)
    const labels = [
      ['Video ingestion', 'Upload or source download'],
      ['Audio extraction', 'FFmpeg · mono 16 kHz audio'],
      ['Speech transcription', 'Whisper · transcript and segments'],
      ['Quiz generation', 'Transcript-derived questions'],
    ]
    return <div className="pipeline" aria-label={`Processing status: ${statusLabel(video.status)}`}>
      {labels.map(([title, detail], index) => {
        const value = values[index]
        const state = value === 3 ? 'unavailable' : value === 2 ? 'complete' : value === 1 ? 'active' : video.status === 'failed' ? 'unknown' : 'pending'
        return <div className={`pipeline-step ${state}`} key={title}>
          <span className="pipeline-node">{state === 'complete' ? <Icon name="check" size={14}/> : index + 1}</span>
          <span className="pipeline-copy"><strong>{title}</strong><small>{state === 'active' ? statusLabel(video.status) : detail}</small></span>
          <span className="pipeline-state">{state === 'complete' ? 'Complete' : state === 'active' ? 'In progress' : state === 'unknown' ? 'Not reported' : state === 'unavailable' ? 'Not generated' : 'Queued'}</span>
        </div>
      })}
      {video.status === 'failed' && <div className="inline-alert error-alert"><Icon name="alert"/><span>{video.error_message || 'Processing failed. The backend did not provide an error message.'}</span></div>}
      {video.status === 'completed_no_speech' && <div className="inline-alert info-alert">Processing finished, but the transcript contained no speech for quiz generation.</div>}
    </div>
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Main navigation">
        <a className="brand" href="#dashboard" aria-label="Video2Quiz dashboard">
          <span className="brand-mark"><Icon name="play" size={20}/></span>
          <span className="brand-name">video<span>2</span>quiz<small>AI LEARNING STUDIO</small></span>
        </a>
        <div className="nav-caption">WORKSPACE</div>
        <nav className="side-nav">
          <a className="nav-link active" href="#dashboard" aria-label="Dashboard" aria-current="page" title="Dashboard"><Icon name="grid"/><span>Dashboard</span></a>
          <a className="nav-link" href="#create-quiz" aria-label="Create quiz" title="Create quiz"><Icon name="plus"/><span>Create quiz</span></a>
          <a className="nav-link" href={selected ? '#quiz-history' : '#library'} aria-label="Quiz history" title="Quiz history"><Icon name="history"/><span>Quiz history</span></a>
        </nav>
        <div className="sidebar-spacer"/>
        <div className="sidebar-note"><span className="online-dot"/><span><strong>Studio ready</strong><small>Connected to your Video2Quiz API</small></span></div>
        <div className="sidebar-footer">LOCAL WORKSPACE <span>v0.5</span></div>
      </aside>

      <main className="main-content" id="dashboard">
        <div className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> Dashboard</div>
          <button className="icon-button" type="button" onClick={() => refresh()} aria-label="Refresh videos" title="Refresh videos"><Icon name="refresh"/></button>
        </div>

        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow"><span className="eyebrow-line"/> VIDEO2QUIZ STUDIO</div>
            <h1>Turn what you watch<br/><span>into what you know.</span></h1>
            <p>Transform lectures and learning videos into clear transcripts and interactive quizzes, ready for your next study session.</p>
            <a className="button button-primary hero-action" href="#create-quiz">Create a quiz <Icon name="arrow" size={16}/></a>
          </div>
          <div className="hero-art" aria-hidden="true">
            <div className="orbit orbit-one"/><div className="orbit orbit-two"/>
            <div className="hero-orb"><Icon name="spark" size={37}/></div>
            <div className="float-chip chip-video"><Icon name="play" size={15}/> Video</div>
            <div className="float-chip chip-transcript"><span className="mini-wave"><i/><i/><i/><i/><i/></span> Transcript</div>
            <div className="float-chip chip-quiz"><Icon name="check" size={15}/> Quiz ready</div>
          </div>
          <div className="hero-glow"/>
        </section>

        <section className="stats-grid" aria-label="Video library statistics">
          <article className="stat-card"><div className="stat-icon purple"><Icon name="play"/></div><div><span>Recent videos</span><strong>{videosLoading && !videos.length ? '—' : stats.total}</strong></div><small>Returned by the API</small></article>
          <article className="stat-card"><div className="stat-icon green"><Icon name="check"/></div><div><span>Ready to study</span><strong>{videosLoading && !videos.length ? '—' : stats.ready}</strong></div><small>Processing completed</small></article>
          <article className="stat-card"><div className="stat-icon blue"><Icon name="clock"/></div><div><span>In progress</span><strong>{videosLoading && !videos.length ? '—' : stats.processing}</strong></div><small>Live backend statuses</small></article>
        </section>

        <div className="content-grid" id="create-quiz">
          <section className="panel create-panel">
            <div className="section-heading">
              <div><span className="section-kicker">START WITH A VIDEO</span><h2>Create your next quiz</h2><p>Bring a lecture or explainer into your learning workspace.</p></div>
              <span className="heading-spark"><Icon name="spark"/></span>
            </div>
            <div className={`dropzone ${dragging ? 'dragging' : ''}`} onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files?.[0]) }}>
              <input ref={fileInputRef} className="file-input" type="file" accept={ACCEPTED_EXTENSIONS.join(',')} aria-label="Choose video file" onChange={event => chooseFile(event.target.files?.[0])}/>
              <span className="drop-icon"><Icon name="upload" size={23}/></span>
              <strong>{file ? file.name : 'Drop your video here'}</strong>
              <span>{file ? 'Ready to upload · file size limit is enforced by the server' : 'or browse files from your device'}</span>
              <button type="button" className="button button-quiet" onClick={() => fileInputRef.current?.click()} disabled={busy}>{file ? 'Choose another file' : 'Browse files'}</button>
              <small>MP4 · MOV · MKV · WEBM · AVI</small>
            </div>
            <div className="upload-actions">
              <button className="button button-primary full-button" disabled={busy || !file} onClick={upload}>{busy ? <><span className="spinner"/> Uploading…</> : <>Upload and process <Icon name="arrow" size={16}/></>}</button>
              <span className="server-note">Upload progress is not provided by the current API.</span>
            </div>
            <div className="divider-label"><span/> OR USE A VIDEO LINK <span/></div>
            <div className="url-entry">
              <label className="url-field"><Icon name="link" size={17}/><input value={url} onChange={event => setUrl(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !busy) youtube() }} placeholder="Paste a public YouTube URL" aria-label="Public YouTube URL"/></label>
              <button className="button button-outline" disabled={busy || !url.trim()} onClick={youtube}>Add link</button>
            </div>
            <p className="input-footnote">YouTube availability depends on the source video and backend access.</p>
            {message && <div className="toast-message" role="status" aria-live="polite">{message}</div>}
          </section>

          <section className="panel process-panel">
            <div className="section-heading"><div><span className="section-kicker">HOW IT WORKS</span><h2>From video to quiz</h2><p>Actual backend stages, reflected as processing updates arrive.</p></div></div>
            {selected ? <>
              <div className="selected-video-head"><div className="video-thumbnail"><Icon name="play"/></div><div className="selected-video-copy"><strong>{selected.original_filename || selected.stored_filename || `Video #${selected.id}`}</strong><small>Video #{selected.id} · {selected.source_type}</small></div><span className={`status-pill ${selected.status}`}><i/>{statusLabel(selected.status)}</span><button className="clear-selection" onClick={() => { setSelected(null); setQuiz(null); setTranscript(''); setExamStarted(false); setEvaluation(null); setAttempt(null) }} aria-label="Close selected video" title="Close selected video">×</button></div>
              {processingView(selected)}
              <div className="process-footer"><span>Last updated {formatDate(selected.updated_at)}</span><button type="button" className="text-button" onClick={() => refresh()}>Refresh status <Icon name="refresh" size={14}/></button></div>
            </> : <>
              <div className="empty-pipeline"><div className="empty-orbit"><Icon name="spark" size={26}/></div><strong>Your processing flow</strong><p>Select a video to see real status updates for ingestion, FFmpeg, Whisper, and quiz generation.</p></div>
              <div className="pipeline compact-pipeline">{['Video ingestion', 'FFmpeg audio extraction', 'Whisper transcription', 'Quiz generation'].map((item, index) => <div className="pipeline-step pending" key={item}><span className="pipeline-node">{index + 1}</span><span className="pipeline-copy"><strong>{item}</strong><small>Waiting for a video</small></span><span className="pipeline-state">Queued</span></div>)}</div>
            </>}
          </section>
        </div>

        <section className="panel library-panel" id="library" aria-labelledby="library-heading">
          <div className="section-heading library-heading"><div><span className="section-kicker">YOUR WORKSPACE</span><h2 id="library-heading">Recent videos</h2><p>Choose a video to view its processing details, transcript, and quiz.</p></div><div className="library-actions">{sortedVideos.length > 3 && <button className="view-all-link" onClick={() => setShowAllVideos(value => !value)} aria-expanded={showAllVideos}>{showAllVideos ? 'Show latest 3' : 'View All'} <Icon name="arrow" size={13}/></button>}<button className="button button-outline" onClick={() => refresh()} disabled={videosLoading}><Icon name="refresh" size={15}/>{videosLoading ? 'Refreshing' : 'Refresh'}</button></div></div>
          {videoError && <div className="inline-alert error-alert" role="alert"><Icon name="alert"/><span>{videoError}</span><button className="text-button" onClick={() => refresh()}>Try again</button></div>}
          {videosLoading && !videos.length ? <div className="library-state" role="status"><span className="spinner dark-spinner"/> Loading your videos…</div>
            : !videoError && videos.length === 0 ? <div className="library-state empty-state"><span className="empty-library-icon"><Icon name="play" size={22}/></span><strong>Your video library is ready</strong><p>Upload a learning video or add a public YouTube link to get started.</p><a className="text-button" href="#create-quiz">Add your first video <Icon name="arrow" size={14}/></a></div>
              : <div className="video-table-wrap"><table className="video-table"><thead><tr><th>VIDEO</th><th>SOURCE</th><th>ADDED</th><th>STATUS</th><th/></tr></thead><tbody>{displayedVideos.map(video => <tr key={video.id} className={selected?.id === video.id ? 'row-selected' : ''}>
                <td><div className="table-video"><span className="table-video-icon"><Icon name="play" size={16}/></span><span><strong>{video.original_filename || video.stored_filename || `Video #${video.id}`}</strong><small>Video #{video.id}</small></span></div></td>
                <td><span className="source-label">{video.source_type === 'youtube' ? <Icon name="link" size={14}/> : <Icon name="upload" size={14}/>} {video.source_type}</span></td>
                <td className="date-cell">{formatDate(video.created_at)}</td>
                <td><span className={`status-pill ${video.status}`}><i/>{statusLabel(video.status)}</span></td>
                <td><button className="table-action" onClick={() => openVideo(video)}>{selected?.id === video.id ? 'Selected' : ['completed', 'completed_no_speech'].includes(video.status) ? 'Open quiz' : 'View status'} <Icon name="arrow" size={14}/></button></td>
              </tr>)}</tbody></table></div>}
        </section>

        {selected && <>
          <section className="panel quiz-panel" aria-labelledby="quiz-heading">
            <div className="section-heading library-heading"><div><span className="section-kicker">VIDEO #{selected.id} · STUDY SPACE</span><h2 id="quiz-heading">Quiz and transcript</h2><p>{selected.original_filename || selected.stored_filename}</p></div>{quiz?.quiz_version != null && <span className="version-tag">VERSION {quiz.quiz_version}</span>}</div>
            {quizLoading && !quiz && <div className="library-state" role="status"><span className="spinner dark-spinner"/> Loading quiz and transcript…</div>}
            {quizError && <div className="inline-alert error-alert" role="alert"><Icon name="alert"/><span>{quizError}</span><button className="text-button" onClick={() => loadDetails(selected.id)}>Retry</button></div>}
            {!quizLoading && !quiz && !quizError && !['completed', 'completed_no_speech'].includes(selected.status) && <div className="library-state"><Icon name="clock"/><span>Quiz content appears here when processing is complete.</span></div>}
            {quiz?.questions?.length === 0 && <div className="inline-alert info-alert">No quiz questions were generated for this video. The backend reports status: {statusLabel(selected.status)}.</div>}
            {quiz?.questions?.length > 0 && !examStarted && <>
              <div className="quiz-intro"><div className="quiz-intro-icon"><Icon name="spark"/></div><div><strong>{quiz.questions.length} questions ready</strong><span>Preview the questions, then start a quiz session.</span></div><button className="button button-primary" disabled={starting} onClick={startExam}>{starting ? <><span className="spinner"/> Starting…</> : 'Start exam'}</button></div>
              <div className="question-grid">{quiz.questions.map((question, index) => <article className="question-card preview-card" key={question.id}><div className="question-meta"><span>QUESTION {String(index + 1).padStart(2, '0')}</span><span className="difficulty-tag">{question.difficulty}</span></div><h3>{question.question}</h3>{questionTimestamp(question)}<ol type="A">{question.options.map((option, optionIndex) => <li key={`${question.id}-${optionIndex}`}>{option}</li>)}</ol></article>)}</div>
            </>}
            {quiz?.questions?.length > 0 && examStarted && <>
              <div className="exam-banner"><div><span className="section-kicker">{persistentExam ? `PERSISTENT EXAM · ATTEMPT #${attempt?.attempt_id}` : 'TEMPORARY QUIZ SESSION'}</span><strong>{persistentExam ? `Quiz version ${attempt?.quiz_version}` : 'Result will not be saved'}</strong></div><span>{Object.keys(answers).length} / {quiz.questions.length} answered</span></div>
              <div className="exam-question-list">{quiz.questions.map((question, index) => {
                const result = evaluation?.results?.find(item => item.question_id === question.id)
                return <article className={`question-card exam-question-card${result ? (result.correct ? ' correct-card' : ' incorrect-card') : ''}`} key={question.id}>
                  <div className="question-meta"><span>QUESTION {String(index + 1).padStart(2, '0')}</span><span className="difficulty-tag">{question.difficulty}</span></div><h3>{question.question}</h3>{questionTimestamp(question)}
                  <div className="answer-options">{question.options.map((option, optionIndex) => <label className={`answer-option${result?.selected_answer === option ? (result.correct ? ' answer-selected-correct' : ' answer-selected-wrong') : ''}`} key={`${question.id}-${optionIndex}`}><input type="radio" name={`question-${question.id}`} value={option} checked={answers[question.id] === option} disabled={Boolean(evaluation) || grading || submissionRetryLocked} onChange={() => setAnswers(current => ({ ...current, [question.id]: option }))}/><span className="option-letter">{String.fromCharCode(65 + optionIndex)}</span><span>{option}</span>{result?.correct && result.selected_answer === option && <Icon name="check" size={17}/>}</label>)}</div>
                  {result && <div className={`answer-feedback ${result.correct ? 'positive' : 'negative'}`}><strong><Icon name={result.correct ? 'check' : 'alert'} size={17}/>{result.feedback}</strong><p>Your answer: {result.selected_answer ?? 'No answer submitted'}</p><p>Correct answer: {result.correct_answer}</p><p>{result.explanation}</p></div>}
                </article>
              })}</div>
              {evaluation ? <div className="result-card"><div className="score-ring"><span>{evaluation.percentage}<small>%</small></span></div><div className="result-copy"><span className="section-kicker">QUIZ COMPLETE · {evaluation.score} / {evaluation.total}</span><h3>{persistentExam ? 'Your result is saved' : 'Your result is ready'}</h3><p>{evaluation.feedback}{!persistentExam && ' This result was not saved to quiz history.'}</p><button className="button button-outline" onClick={retakeExam}>Start another attempt</button></div></div>
                : <div className="exam-submit-row">{message && <p className="form-message" role="status">{message}</p>}<button className="button button-primary" disabled={grading || (persistentExam && !attempt?.attempt_id)} onClick={submitExam}>{grading ? <><span className="spinner"/> {persistentExam ? 'Saving result…' : 'Grading…'}</> : submissionRetryLocked ? 'Retry submission' : 'Submit exam'}</button></div>}
            </>}
            {transcript && <details className="transcript-details"><summary><span><Icon name="history" size={17}/> Review source transcript</span><span className="summary-plus">+</span></summary><p>{transcript}</p></details>}
            {quiz?.notice && <p className="quiz-notice">{quiz.notice}</p>}
          </section>

          <section className="panel history-panel" id="quiz-history" aria-labelledby="history-heading">
            <div className="section-heading library-heading"><div><span className="section-kicker">PERSISTED ATTEMPTS</span><h2 id="history-heading">Quiz history</h2><p>Saved exam attempts for video #{selected.id}.</p></div><button className="button button-outline" onClick={() => loadAttemptHistory(selected.id)} disabled={historyLoading}><Icon name="refresh" size={15}/>{historyLoading ? 'Loading' : 'Refresh history'}</button></div>
            {historyLoading && <div className="library-state small-state" role="status"><span className="spinner dark-spinner"/> Loading saved attempts…</div>}
            {historyError && <div className="inline-alert error-alert" role="alert"><Icon name="alert"/><span>{historyError}</span></div>}
            {!historyLoading && !historyError && history.length === 0 && <div className="library-state empty-history"><span className="empty-library-icon"><Icon name="history"/></span><strong>No exam attempts yet</strong><p>Start an exam from this video to create its first saved result.</p></div>}
            {history.length > 0 && <div className="history-list">{history.map((item, index) => <article className="history-row" key={item.attempt_id}><span className="history-index">{String(index + 1).padStart(2, '0')}</span><div className="history-main"><strong>Attempt #{item.attempt_id}</strong><span>Quiz version {item.quiz_version} · {item.total_questions} questions</span></div><span className={`status-pill ${item.status}`}><i/>{statusLabel(item.status)}</span><div className="history-score">{item.score == null ? 'Not submitted' : <><strong>{item.score} / {item.total_questions}</strong><small>{item.percentage}%</small></>}</div><div className="history-dates"><span>Started {formatDate(item.started_at)}</span>{item.submitted_at && <span>Submitted {formatDate(item.submitted_at)}</span>}</div>{item.status === 'completed' && <button className="table-action" disabled={historyResultLoading} onClick={() => openAttemptResult(item.attempt_id)}>{historyResultLoading ? 'Loading…' : 'View result'} <Icon name="arrow" size={14}/></button>}</article>)}</div>}
            {historyResultLoading && <div className="library-state small-state" role="status"><span className="spinner dark-spinner"/> Loading saved result…</div>}
            {historyResultError && <div className="inline-alert error-alert" role="alert"><Icon name="alert"/><span>{historyResultError}</span></div>}
            {historyResult && <article className="saved-result"><div className="saved-result-head"><div><span className="section-kicker">HISTORICAL RESULT · ATTEMPT #{historyResult.attempt_id}</span><h3>Quiz version {historyResult.quiz_version}</h3><span>Submitted {formatDate(historyResult.submitted_at)}</span></div><button className="button button-outline" onClick={() => setHistoryResult(null)}>Close</button></div><div className="saved-result-score"><strong>{historyResult.score}<small> / {historyResult.total}</small></strong><span>{historyResult.percentage}%</span><p>{historyResult.feedback}</p></div>{historyResult.results.map((item, index) => <article className={`question-card saved-question-card ${item.correct ? 'correct-card' : 'incorrect-card'}`} key={item.question_id}><div className="question-meta"><span>QUESTION {String(index + 1).padStart(2, '0')}</span><span className={item.correct ? 'review-correct' : 'review-incorrect'}>{item.correct ? 'Correct' : 'Review'}</span></div><h3>{item.question}</h3><div className="saved-answer"><span>Your answer</span><strong>{item.selected_answer ?? 'No answer submitted'}</strong></div><div className="saved-answer"><span>Correct answer</span><strong>{item.correct_answer}</strong></div><p className="explanation">{item.explanation}</p></article>)}</article>}
          </section>
        </>}

        <footer className="page-footer"><span>Video2Quiz AI Learning Studio</span><span>Built around your real video library and saved quiz results.</span></footer>
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<App />)
