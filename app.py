import streamlit as st
import ezdxf
import pypdfium2 as pdfium
import io
import numpy as np
import cv2
import pytesseract
from PIL import Image

# --- Page Setup ---
st.set_page_config(page_title="Ultimate PDF to DXF", page_icon="🏗️", layout="wide")

def process_page(page, doc, msp, scale, simplify, noise, use_ocr):
    """Processes a single PDF page into CAD entities."""
    # 1. Try Vector Extraction first
    found_vectors = False
    for obj in page.get_objects():
        if obj.type == 2: # PATH
            found_vectors = True
            try:
                path_data = obj.get_path()
                points = []
                for segment in path_data:
                    if hasattr(segment, 'points'):
                        for pt in segment.points:
                            points.append((pt.x * scale, pt.y * scale))
                if len(points) >= 2:
                    msp.add_lwpolyline(points)
            except: continue

    # 2. If no vectors or if user wants scan-processing, use Raster Logic
    if not found_vectors:
        # Render page to Image
        bitmap = page.render(scale=4) 
        pil_img = bitmap.to_pil().convert("L")
        img = np.array(pil_img)

        # OCR Handling
        if use_ocr:
            try:
                # Get OCR data (bounding boxes and text)
                ocr_data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
                for i in range(len(ocr_data['text'])):
                    if int(ocr_data['conf'][i]) > 60:
                        x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
                        txt = ocr_data['text'][i].strip()
                        if txt:
                            # Add real CAD Text
                            msp.add_text(txt, height=h*scale).set_placement(
                                (x * scale, (pil_img.height - (y + h)) * scale)
                            )
                            # Mask text area so the tracer doesn't turn it into messy lines
                            cv2.rectangle(img, (x, y), (x+w, y+h), (255), -1)
            except Exception as e:
                st.sidebar.warning(f"OCR Error: {e}")

        # Denoise and Threshold
        if noise > 0:
            img = cv2.medianBlur(img, noise if noise % 2 != 0 else noise + 1)
        
        thresh = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY_INV, 11, 2)
        
        # Skeletonization (The 'Pro' thinning step)
        skeleton = cv2.ximgproc.thinning(thresh) if hasattr(cv2, 'ximgproc') else thresh
        
        # Trace
        contours, _ = cv2.findContours(skeleton, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            epsilon = simplify * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, False)
            points = [(pt[0][0] * scale, (pil_img.height - pt[0][1]) * scale) for pt in approx]
            if len(points) >= 2:
                msp.add_lwpolyline(points)

# --- Streamlit UI ---
st.title("🏗️ Ultimate PDF to DXF Converter")
st.markdown("Handles **Vectors**, **Scanned Blueprints**, and **Text Recognition**.")

with st.sidebar:
    st.header("Settings")
    scale = st.number_input("Scale Multiplier", value=0.1, help="Adjust to match CAD units.")
    simplify = st.slider("Line Smoothing", 0.001, 0.05, 0.01)
    noise = st.slider("Denoise Strength", 0, 9, 3, step=2)
    use_ocr = st.checkbox("Enable Text Recognition (OCR)", value=True)
    st.info("Note: OCR helps prevent text from looking like 'scribbles'.")

uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file:
    if st.button("Start Professional Conversion"):
        try:
            pdf = pdfium.PdfDocument(uploaded_file)
            doc = ezdxf.new('R2010')
            msp = doc.modelspace()
            
            progress = st.progress(0)
            for i, page in enumerate(pdf):
                process_page(page, doc, msp, scale, simplify, noise, use_ocr)
                progress.progress((i + 1) / len(pdf))
            
            out = io.StringIO()
            doc.write(out)
            st.success("Conversion successful!")
            st.download_button("💾 Download DXF File", out.getvalue(), "converted_drawing.dxf", "application/dxf")
        except Exception as e:
            st.error(f"Critical Error: {e}")