import { useRef, useEffect, useState, useCallback } from 'react'

/**
 * CameraCapture
 * ---------------
 * A self-contained camera modal using getUserMedia — the standard
 * browser API for direct camera stream access. This works reliably
 * across desktop and mobile, unlike relying on <input capture>,
 * which desktop browsers largely ignore.
 *
 * Flow: open camera stream -> show live preview -> user clicks
 * "Capture" -> we draw the current video frame onto a hidden canvas
 * -> convert canvas to a File -> hand it back to the parent via onCapture.
 */
function CameraCapture({ onCapture, onClose }) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let isMounted = true

    async function startCamera() {
      try {
        // "environment" requests the back camera on phones (better for
        // photographing documents); desktops simply ignore this hint
        // and use whatever webcam is available.
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment' },
        })
        if (!isMounted) {
          // Component unmounted while permission dialog was open —
          // clean up immediately instead of leaving the camera live.
          stream.getTracks().forEach((track) => track.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
        }
      } catch (err) {
        // Covers: permission denied, no camera hardware, camera
        // already in use by another app — all real, common cases.
        setError(
          err.name === 'NotAllowedError'
            ? 'Camera access was denied. Please allow camera permission and try again.'
            : 'Could not access camera. Make sure a camera is connected and not in use elsewhere.'
        )
      }
    }

    startCamera()

    return () => {
      isMounted = false
      // Always release the camera when the modal closes — leaving a
      // camera stream open in the background is both a resource leak
      // and a privacy concern.
      streamRef.current?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  const handleCapture = useCallback(() => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas) return

    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

    canvas.toBlob((blob) => {
      if (blob) {
        const file = new File([blob], `capture-${Date.now()}.jpg`, {
          type: 'image/jpeg',
        })
        onCapture(file)
      }
    }, 'image/jpeg', 0.92)
  }, [onCapture])

  return (
    <div className="camera-overlay">
      <div className="camera-modal">
        {error ? (
          <div className="error-box">{error}</div>
        ) : (
          <video ref={videoRef} autoPlay playsInline className="camera-video" />
        )}
        <canvas ref={canvasRef} style={{ display: 'none' }} />
        <div className="action-row">
          {!error && (
            <button className="primary" onClick={handleCapture}>
              Capture photo
            </button>
          )}
          <button onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  )
}

export default CameraCapture