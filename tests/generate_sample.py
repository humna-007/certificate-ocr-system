"""
generate_sample.py
--------------------
Generates a simple test certificate image so we can verify our
OCR pipeline end-to-end without needing a real scanned certificate.
Not part of the production app — just a dev/testing utility.
"""

from PIL import Image, ImageDraw, ImageFont

def generate_sample_certificate(output_path="sample_certificates/test_cert.png"):
    img = Image.new("RGB", (900, 600), color="white")
    draw = ImageDraw.Draw(img)

    # Using default font since custom font files may not exist on your system —
    # good enough for OCR testing purposes.
    font_large = ImageFont.load_default()
    
    lines = [
        (300, 60, "TEEROP PVT. LIMITED"),
        (280, 140, "CERTIFICATE OF COMPLETION"),
        (250, 220, "This certifies that Humna Shaukat"),
        (280, 260, "has successfully completed the"),
        (300, 300, "Gen AI and LLM Applications Internship"),
        (350, 340, "with grade A"),
        (320, 420, "Date: 13/07/2026"),
        (280, 460, "Certificate ID: CERT-2026-0042"),
    ]

    for x, y, text in lines:
        draw.text((x, y), text, fill="black", font=font_large)

    img.save(output_path)
    print(f"Sample certificate saved to {output_path}")

if __name__ == "__main__":
    generate_sample_certificate()