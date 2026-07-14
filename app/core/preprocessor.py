"""
preprocessor.py
----------------
Image preprocessing pipeline that improves OCR accuracy.

Why this matters:
Tesseract performs significantly better on clean, high-contrast,
properly-aligned black & white text than on raw photos with shadows,
skew, or noise. This module takes a raw image and returns one that's
optimized for text recognition.

Pipeline: grayscale -> denoise -> adaptive threshold -> deskew
"""

import cv2
import numpy as np
from pathlib import Path
import pytesseract

def correct_orientation(image_path) -> "np.ndarray":
    """
    Detects and corrects 90/180/270-degree rotation using Tesseract's
    OSD (Orientation and Script Detection) mode, BEFORE our fine-grained
    deskew step (which only handles small tilts, not full rotations).

    Why this matters: phone photos are very often taken in the "wrong"
    orientation relative to the document (e.g. landscape certificate
    photographed in portrait mode), which OSD is specifically designed
    to detect and fix.
    """
    image = load_image(image_path)
    try:
        osd = pytesseract.image_to_osd(image)
        rotation = int([line for line in osd.split("\n") if "Rotate:" in line][0].split(":")[1].strip())
    except Exception:
        # OSD can fail on very sparse/noisy images — fall back to
        # assuming no rotation needed rather than crashing the pipeline.
        rotation = 0

    if rotation != 0:
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, -rotation, 1.0)
        image = cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC,
                                borderMode=cv2.BORDER_REPLICATE)
    return image


def load_image(image_path: Path) -> np.ndarray:
    """
    Loads an image from disk into an OpenCV array.
    Raises a clear error if the file can't be read (corrupted upload,
    unsupported format edge case, etc.) instead of letting OpenCV
    fail silently with a cryptic None-type error later.
    """
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not read image at {image_path}. "
                          f"File may be corrupted or in an unsupported format.")
    return image


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """
    Converts to grayscale. Tesseract works on single-channel intensity
    data anyway, so color information is discarded early to simplify
    every step after this.
    """
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def denoise(gray_image: np.ndarray) -> np.ndarray:
    """
    Removes small noise artifacts (common in phone camera photos —
    sensor grain, JPEG compression artifacts) without blurring text edges.
    fastNlMeansDenoising is slower than a simple blur but preserves
    edges much better, which matters a lot for character recognition.
    """
    return cv2.fastNlMeansDenoising(gray_image, h=10)


def adaptive_threshold(gray_image: np.ndarray) -> np.ndarray:
    """
    Converts to pure black & white using ADAPTIVE thresholding rather
    than a single global threshold value.

    Why adaptive: certificates are often photographed with uneven
    lighting (e.g. a shadow across half the page). A single global
    threshold would turn the shadowed half into a black blob. Adaptive
    thresholding calculates the threshold per local region instead,
    handling uneven lighting gracefully.
    """
    return cv2.adaptiveThreshold(
        gray_image,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,   # size of the local neighborhood considered
        C=10            # constant subtracted from the mean; tuned empirically
    )


def deskew(image: np.ndarray) -> np.ndarray:
    """
    Detects and corrects rotation/tilt in the image.

    Why: a certificate photographed at a slight angle (very common
    with phone cameras) confuses Tesseract's line-detection, causing
    it to misread or skip text entirely. We find the dominant text
    angle and rotate the image to straighten it.
    """
    coords = np.column_stack(np.where(image > 0))

    if len(coords) == 0:
        # Nothing detected (blank/fully white image) — nothing to deskew.
        return image

    angle = cv2.minAreaRect(coords)[-1]

    # cv2.minAreaRect returns angles in a range that needs normalizing;
    # this correction ensures we rotate the SHORT way, not upside down.
    if angle < -45:
        angle = 90 + angle
    else:
        angle = -angle

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

    rotated = cv2.warpAffine(
        image, rotation_matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE  # avoids black corners after rotation
    )
    return rotated


def preprocess_image(image_path: Path) -> np.ndarray:
    """
    Runs the full preprocessing pipeline on a given image file and
    returns an OCR-ready OpenCV image array.

    This is the single function the rest of the app should call —
    it hides the individual steps behind one clean interface.
    """
    image = correct_orientation(image_path)
    gray = to_grayscale(image)
    denoised = denoise(gray)
    thresholded = adaptive_threshold(denoised)
    final = deskew(thresholded)
    return final