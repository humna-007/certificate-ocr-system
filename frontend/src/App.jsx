import { useState, useRef, useCallback } from 'react'
import axios from 'axios'
import './App.css'
import * as XLSX from 'xlsx'
import CameraCapture from './CameraCapture'

const API_URL = 'https://192.168.18.83:8000'

const FIELD_LABELS = {
  candidate_name: 'Candidate name',
  organization: 'Organization',
  issue_date: 'Issue date',
  certificate_id: 'Certificate ID',
  grade: 'Grade',
}

function App() {
  const [showTool, setShowTool] = useState(false)
  const [status, setStatus] = useState('idle')
  const [result, setResult] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [copyStatus, setCopyStatus] = useState(null)
  const [showCamera, setShowCamera] = useState(false)
  const fileInputRef = useRef(null)

  const handleFile = useCallback(async (file) => {
    if (!file) return
    setStatus('processing')
    setErrorMessage('')
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await axios.post(`${API_URL}/extract`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(response.data.data)
      setStatus('success')
    } catch (err) {
      const message =
        err.response?.data?.detail ||
        'Something went wrong while processing this file. Please try again.'
      setErrorMessage(message)
      setStatus('error')
    }
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setIsDragging(false)
    handleFile(e.dataTransfer.files?.[0])
  }, [handleFile])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback(() => setIsDragging(false), [])

  const handleFileInputChange = (e) => {
    handleFile(e.target.files?.[0])
    e.target.value = ''
  }

  const reset = () => {
    setStatus('idle')
    setResult(null)
    setErrorMessage('')
  }

  const copyToClipboard = async () => {
    const lines = Object.entries(FIELD_LABELS).map(
      ([key, label]) => `${label}: ${result[key] || 'Not found'}`
    )
    try {
      await navigator.clipboard.writeText(lines.join('\n'))
      setCopyStatus('Copied')
      setTimeout(() => setCopyStatus(null), 1500)
    } catch {
      setCopyStatus('Copy failed')
      setTimeout(() => setCopyStatus(null), 1500)
    }
  }

  const triggerDownload = (blob, filename) => {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const downloadJSON = () => {
    const cleanData = Object.fromEntries(
      Object.keys(FIELD_LABELS).map((key) => [key, result[key] || null])
    )
    const blob = new Blob([JSON.stringify(cleanData, null, 2)], { type: 'application/json' })
    triggerDownload(blob, 'certificate_extraction.json')
  }

  const downloadExcel = () => {
    const rows = Object.entries(FIELD_LABELS).map(([key, label]) => ({
      Field: label,
      Value: result[key] || 'Not found',
    }))
    const worksheet = XLSX.utils.json_to_sheet(rows)
    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Extraction')
    XLSX.writeFile(workbook, 'certificate_extraction.xlsx')
  }

  return (
    <div className="app">
      <div className="navbar">
  <div className="nav-brand">
    <span className="nav-mark">OC</span>
    <span className="nav-name">certificate-ocr-system</span>
  </div>
  <span className="nav-tag">v1.0.0</span>
</div>

      {!showTool ? (
  <div className="landing">
    <span className="eyebrow">● Tesseract OCR + AI extraction</span>
    <h1 className="app-title">Extract certificate data instantly</h1>
    <p className="app-subtitle">
      Upload a certificate image or PDF, or capture one with your camera.
      We extract the candidate name, organization, date, and more —
      no login required.
    </p>

    <div className="how-it-works">
      <div className="how-step">
        <span className="how-number">01</span>
        <p><strong>Upload</strong> a certificate image, PDF, or take a photo</p>
      </div>
      <div className="how-step">
        <span className="how-number">02</span>
        <p><strong>We process</strong> it with OCR and AI-based field extraction</p>
      </div>
      <div className="how-step">
        <span className="how-number">03</span>
        <p><strong>Get</strong> structured, exportable results in seconds</p>
      </div>
    </div>

    <div className="cta-row">
      <button className="primary" onClick={() => setShowTool(true)}>
        Try it now
      </button>
      <p className="trust-line">JPG · PNG · TIFF · PDF · no signup · free</p>
    </div>

    <div className="features-grid">
      <div className="feature-card">
        <div className="feature-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 4h16v16H4z" /><path d="M8 9h8M8 13h5" />
          </svg>
        </div>
        <p className="feature-title">Tesseract OCR</p>
        <p className="feature-desc">Industry-standard text recognition, tuned with custom image preprocessing</p>
      </div>
      <div className="feature-card">
        <div className="feature-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2l2.5 6.5L21 11l-6.5 2.5L12 20l-2.5-6.5L3 11l6.5-2.5z" />
          </svg>
        </div>
        <p className="feature-title">AI-assisted extraction</p>
        <p className="feature-desc">LLM fallback catches noisy scans and stylized certificates regex alone misses</p>
      </div>
      <div className="feature-card">
        <div className="feature-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 3v12M7 10l5 5 5-5M5 21h14" />
          </svg>
        </div>
        <p className="feature-title">Export anywhere</p>
        <p className="feature-desc">Copy, JSON, or Excel — plug results straight into your workflow</p>
      </div>
    </div>

    <div className="stats-row">
      <div className="stat">
        <p className="stat-number">&lt;30s</p>
        <p className="stat-label">avg. processing time</p>
      </div>
      <div className="stat">
        <p className="stat-number">95%+</p>
        <p className="stat-label">accuracy on clean scans</p>
      </div>
      <div className="stat">
        <p className="stat-number">$0</p>
        <p className="stat-label">no signup, no cost</p>
      </div>
    </div>
  </div>
) : (
         
        <>
          {status === 'idle' && (
            <>
              <div
                className={`upload-zone ${isDragging ? 'dragging' : ''}`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => fileInputRef.current?.click()}
              >
                <p style={{ fontSize: 15, color: 'var(--text-primary)', fontWeight: 500 }}>
                  Drag and drop your certificate here
                </p>
                <p>or click to browse</p>
                <p className="file-hint">JPG · PNG · TIFF · PDF — max 10MB</p>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/tiff,application/pdf"
                style={{ display: 'none' }}
                onChange={handleFileInputChange}
              />

              <div className="action-row">
                <button onClick={() => setShowCamera(true)}>Use camera instead</button>
                <button onClick={() => setShowTool(false)}>Back</button>
              </div>
            </>
          )}

          {showCamera && (
            <CameraCapture
              onCapture={(file) => {
                setShowCamera(false)
                handleFile(file)
              }}
              onClose={() => setShowCamera(false)}
            />
          )}

          {status === 'processing' && (
            <div className="spinner-wrap">
              <div className="spinner" />
              <p>Extracting text…</p>
            </div>
          )}

          {status === 'error' && (
            <>
              <div className="error-box">{errorMessage}</div>
              <div className="action-row">
                <button className="primary" onClick={reset}>Try again</button>
              </div>
            </>
          )}

          {status === 'success' && result && (
            <>
              <div className="results">
                <div className="results-header">
                  <span>extraction_result.json</span>
                  <span>200 OK</span>
                </div>
                {Object.entries(FIELD_LABELS).map(([key, label]) => (
                  <div className="field-row" key={key}>
                    <span className="field-label">{label}</span>
                    <span className={`field-value ${!result[key] ? 'empty' : ''}`}>
                      {result[key] || 'not found'}
                      {result[`${key}_source`] === 'llm' && <span className="badge">AI</span>}
                    </span>
                  </div>
                ))}
              </div>
              <div className="action-row">
                <button onClick={copyToClipboard}>{copyStatus || 'Copy to clipboard'}</button>
                <button onClick={downloadJSON}>Download JSON</button>
                <button onClick={downloadExcel}>Download Excel</button>
                <button className="primary" onClick={reset}>Process another</button>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

export default App