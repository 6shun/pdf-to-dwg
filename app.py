import streamlit as st
import ezdxf
import pypdfium2 as pdfium
import io
import numpy as np
import cv2
from PIL import Image

st.set_page_config(page_title="Pro PDF-to-CAD Converter", page_icon="📐")

def process_scanned_page(page, msp, scale, simplify_factor, noise_level):
    # 1. High-Res Render (DPI matters for tracing)
    bitmap = page.render(scale=4) 
    pil_img = bitmap.to_pil().convert("L") # Grayscale
    img = np.array(pil_img)

    # 2. Denoising (Removes speckles from old scans)
    if noise_level > 0:
        img = cv2.medianBlur(img, noise_level if noise_level % 2 != 0 else noise_level + 1)

    # 3. Thresholding (Adaptive works better for uneven scans)
    thresh = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 11, 2)

    # 4. Skeletonization (Thinning the lines to a 1-pixel spine)
    # This prevents the "hollow double line" effect
    kernel = np.ones((3,3), np.uint8)
    skeleton = cv2.ximgproc.thinning(thresh) if hasattr(cv2, 'ximgproc') else thresh

    # 5. Find Contours
    contours, _ = cv2.findContours(skeleton, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        # 6. Douglas-Peucker Simplification
        # This turns "jittery" lines into smooth CAD lines
        epsilon = simplify_factor * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, False)
        
        points = []
        for pt in approx:
            x, y = pt[0]
            # Flip Y for CAD space (Origin at bottom-left)
            points.append((x * scale, (pil_img.height - y) * scale))
        
        if len(points) >= 2:
            msp.add_lwpolyline(points)

def main():
    st.title("📐 Pro PDF to DXF Converter")
    st.markdown("Uses **Skeletonization** and **Douglas-Peucker** algorithms for cleaner CAD output.")

    with st.sidebar:
        st.header("Tuning Controls")
        scale = st.number_input("Global Scale", value=0.1)
        simplify = st.slider("Line Simplification", 0.001, 0.05, 0.01, help="Higher = straighter lines, lower = more detail.")
        noise = st.slider("Denoise Strength", 0, 9, 3, step=2)

    uploaded_file = st.file_uploader("Upload Scanned or Vector PDF", type="pdf")

    if uploaded_file:
        if st.button("Generate Professional DXF"):
            pdf = pdfium.PdfDocument(uploaded_file)
            doc = ezdxf.new('R2010')
            msp = doc.modelspace()

            progress_bar = st.progress(0)
            for i, page in enumerate(pdf):
                process_scanned_page(page, msp, scale, simplify, noise)
                progress_bar.progress((i + 1) / len(pdf))

            # Buffer and Download
            out_buf = io.StringIO()
            doc.write(out_buf)
            st.success("Conversion Complete!")
            st.download_button("Download DXF", out_buf.getvalue(), "pro_output.dxf", "application/dxf")

if __name__ == "__main__":
    main()