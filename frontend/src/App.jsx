import { useState, useRef, useCallback } from 'react'
import axios from 'axios'
import './App.css'
import * as XLSX from 'xlsx'
import CameraCapture from './CameraCapture'

// Backend API base URL. Hardcoded for local development — in a real
// production deployment this would come from an environment variable
// (import.meta.env.VITE_API_URL) so the frontend can point at different
// backends per environment without code changes.
const API_URL = 'https://192.168.18.83:8000'

// Human-readable labels for the fields our backend returns, so the UI
// doesn't show raw snake_case keys like "candidate_name" to the user.
const FIELD_LABELS = {
  candidate_name: 'Candidate name',
  organization: 'Organization',
  issue_date: 'Issue date',
  certificate_id: 'Certificate ID',
  grade: 'Grade',
}

function App() {
  // 'idle' | 'processing' | 'success' | 'error'
  const [status, setStatus] = useState('idle')
  const [result, setResult] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [copyStatus, setCopyStatus] = useState(null)
  const fileInputRef = useRef(null)
  const [showCamera, setShowCamera] = useState(false)

  // Central upload handler — used by both drag-drop and file picker,
  // so we don't duplicate the upload logic in two places.
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
      // Axios wraps server error responses in err.response.data — we
      // prefer that specific message (e.g. "No text could be extracted")
      // over a generic fallback, since it's actually useful to the user.
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
    const file = e.dataTransfer.files?.[0]
    handleFile(file)
  }, [handleFile])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback(() => setIsDragging(false), [])

  const handleFileInputChange = (e) => {
    const file = e.target.files?.[0]
    handleFile(file)
    // Reset so selecting the same file twice in a row still fires onChange
    e.target.value = ''
  }

  const reset = () => {
    setStatus('idle')
    setResult(null)
    setErrorMessage('')
  }

  // Copies extracted fields as clean readable text — not raw JSON —
// so pasting into an email/chat/doc looks natural rather than
// dumping code-formatted syntax on a non-technical reader.
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

// Triggers a browser download by creating a temporary invisible link
// and clicking it programmatically — the standard vanilla-JS pattern
// for client-side file downloads (no backend round-trip needed).
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
  const blob = new Blob([JSON.stringify(cleanData, null, 2)], {
    type: 'application/json',
  })
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
      <p className="app-label">certificate-ocr-system</p>
      <h1 className="app-title">Extract certificate data instantly</h1>
      <p className="app-subtitle">
        Upload a certificate image or PDF. We'll extract the candidate name,
        organization, date, and more — no login required.
      </p>

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
            <button onClick={() => setShowCamera(true)}>
  Use camera instead
</button>
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
                  {result[`${key}_source`] === 'llm' && (
                    <span className="badge">AI</span>
                  )}
                </span>
              </div>
            ))}
          </div>
          <div className="action-row">
  <button onClick={copyToClipboard}>
    {copyStatus || 'Copy to clipboard'}
  </button>
  <button onClick={downloadJSON}>Download JSON</button>
  <button onClick={downloadExcel}>Download Excel</button>
  <button className="primary" onClick={reset}>Process another</button>
</div>
        </>
      )}
    </div>
  )
}

export default App