import streamlit as st
import ezdxf
import pypdfium2 as pdfium
import io
import numpy as np
import cv2
import pytesseract
from PIL import Image

# --- Page Configuration ---
st.set_page_config(page_title="Pro PDF-to-CAD Converter", page_icon="🏗️", layout="wide")

def process_page(page, msp, scale, simplify, noise, use_ocr):
    # 1. ATTEMPT VECTOR EXTRACTION
    # (Fastest and most accurate for PDFs exported from CAD)
    found_vectors = False
    try:
        for obj in page.get_objects():
            if obj.type == 2: # PATH object
                path_data = obj.get_path()
                points = []
                for segment in path_data:
                    if hasattr(segment, 'points'):
                        for pt in segment.points:
                            points.append((pt.x * scale, pt.y * scale))
                if len(points) >= 2:
                    msp.add_lwpolyline(points)
                    found_vectors = True
    except:
        pass

    # 2. RASTER PROCESSING (For Scans or Hybrid PDFs)
    # We render at scale=4 (approx 300 DPI) for high tracing accuracy
    bitmap = page.render(scale=4)
    pil_img = bitmap.to_pil().convert("L")
    img = np.array(pil_img)

    # OCR TEXT HANDLING
    if use_ocr:
        try:
            # Get detailed OCR data
            ocr_data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
            for i in range(len(ocr_data['text'])):
                # Confidence > 80 to avoid "ghost" text artifacts
                if int(ocr_data['conf'][i]) > 80:
                    x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
                    txt = ocr_data['text'][i].strip()
                    
                    if len(txt) > 1:
                        # Add real CAD Text entity
                        msp.add_text(txt, height=h*scale).set_placement(
                            (x * scale, (pil_img.height - y) * scale)
                        )
                        # MASK: Whiten out the text so the line-tracer ignores it
                        cv2.rectangle(img, (x, y), (x + w, y + h), (255), -1)
        except Exception as e:
            st.sidebar.warning(f"OCR Notice: {e}")

    # IMAGE PRE-PROCESSING
    if noise > 0:
        img = cv2.medianBlur(img, noise if noise % 2 != 0 else noise + 1)
    
    # Adaptive threshold handles uneven scans/shadows
    thresh = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 11, 2)

    # SKELETONIZATION (Reduces thick lines to 1-pixel spines)
    # This prevents "hollow" double lines in CAD
    if cv2.countNonZero(thresh) > 0:
        skeleton = cv2.ximgproc.thinning(thresh) if hasattr(cv2, 'ximgproc') else thresh
        
        # TRACING
        contours, _ = cv2.findContours(skeleton, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            # Douglas-Peucker Simplification for smooth lines
            epsilon = simplify * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, False)
            
            points = [(pt[0][0] * scale, (pil_img.height - pt[0][1]) * scale) for pt in approx]
            if len(points) >= 2:
                msp.add_lwpolyline(points)

# --- Streamlit User Interface ---
st.title("📐 Professional PDF to DXF Converter")
st.write("Converts **Vectors**, **Scanned Blueprints**, and **Text** into layered CAD files.")

with st.sidebar:
    st.header("🔧 Engine Settings")
    scale_val = st.number_input("Scale Multiplier", value=1.0, step=0.1, help="Adjust to fix drawing size.")
    smooth_val = st.slider("Line Smoothing", 0.001, 0.05, 0.01, format="%.3f")
    noise_val = st.slider("Denoise Strength", 0, 9, 3, step=2)
    ocr_toggle = st.checkbox("Enable OCR Text Recognition", value=True)
    st.divider()
    st.info("Tip: If the output is empty, increase 'Scale' or check if the PDF is password protected.")

uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

if uploaded_file:
    if st.button("🚀 Generate CAD File"):
        with st.spinner("Processing pages... This may take a minute for large scans."):
            try:
                pdf = pdfium.PdfDocument(uploaded_file)
                doc = ezdxf.new('R2010')
                msp = doc.modelspace()
                
                progress_bar = st.progress(0)
                for i, page in enumerate(pdf):
                    process_page(page, msp, scale_val, smooth_val, noise_val, ocr_toggle)
                    progress_bar.progress((i + 1) / len(pdf))
                
                # Save to Buffer
                dxf_io = io.StringIO()
                doc.write(dxf_io)
                
                st.success("Conversion Finished!")
                st.download_button(
                    label="💾 Download DXF",
                    data=dxf_io.getvalue(),
                    file_name=f"converted_{uploaded_file.name.split('.')[0]}.dxf",
                    mime="application/dxf"
                )
            except Exception as e:
                st.error(f"Error during conversion: {e}")