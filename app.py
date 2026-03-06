import streamlit as st
import ezdxf
import pypdfium2 as pdfium
import io
import numpy as np
import cv2
import pytesseract
from PIL import Image
import math

# --- Page Configuration ---
st.set_page_config(page_title="Pro PDF-to-CAD Converter", page_icon="🏗️", layout="wide")

def process_page(page, msp, scale_val, simplify, noise, use_ocr):
    # Get physical page dimensions
    left, bottom, right, top = page.get_bbox()
    p_width = right - left
    p_height = top - bottom
    
    # 1. NATIVE DATA EXTRACTION (Handles Vectors and Oriented Text)
    vector_count = 0
    try:
        for obj in page.get_objects():
            # Handle Path/Lines
            if obj.type == 2: 
                path_data = obj.get_path()
                points = []
                for segment in path_data:
                    if hasattr(segment, 'points'):
                        for pt in segment.points:
                            points.append((pt.x * scale_val, (p_height - pt.y) * scale_val))
                if len(points) >= 2:
                    msp.add_lwpolyline(points)
                    vector_count += 1
            
            # Handle Native Text (Preserves Orientation)
            elif obj.type == 3: 
                text_str = obj.get_text()
                if text_str.strip():
                    pos = obj.get_pos() # (x, y)
                    fs = obj.get_fontsize()
                    
                    # Attempt to get rotation from the transformation matrix
                    # matrix = (a, b, c, d, e, f) where rotation is derived from a,b,c,d
                    matrix = obj.get_matrix()
                    rotation = math.degrees(math.atan2(matrix[1], matrix[0]))
                    
                    text_entity = msp.add_text(text_str, height=fs * scale_val)
                    text_entity.set_placement((pos[0] * scale_val, (p_height - pos[1]) * scale_val))
                    text_entity.dxf.rotation = rotation

    except Exception as e:
        st.sidebar.error(f"Vector/Native Text Error: {e}")

    # 2. RASTER PROCESSING (For Scans or "Flattened" PDFs)
    render_res = 4 
    bitmap = page.render(scale=render_res)
    pil_img = bitmap.to_pil().convert("L")
    img = np.array(pil_img)
    img_h, _ = img.shape
    ratio = scale_val / render_res

    if use_ocr:
        try:
            # Detect orientation of the whole page first
            osd = pytesseract.image_to_osd(pil_img, output_type=pytesseract.Output.DICT)
            page_rotation = osd.get('rotate', 0)

            # Get detailed OCR data
            custom_config = r'--oem 3 --psm 3'
            ocr_data = pytesseract.image_to_data(pil_img, config=custom_config, output_type=pytesseract.Output.DICT)
            
            for i in range(len(ocr_data['text'])):
                if int(ocr_data['conf'][i]) > 75 and ocr_data['text'][i].strip():
                    px_x, px_y = ocr_data['left'][i], ocr_data['top'][i]
                    px_w, px_h = ocr_data['width'][i], ocr_data['height'][i]

                    cad_x = px_x * ratio
                    cad_y = (img_h - px_y) * ratio
                    
                    txt = ocr_data['text'][i]
                    t_entity = msp.add_text(txt, height=px_h * ratio * 0.8)
                    t_entity.set_placement((cad_x, cad_y))

                    # Heuristic for vertical text if global rotation didn't catch it
                    if px_h > px_w * 1.8:
                        t_entity.dxf.rotation = 90
                    else:
                        t_entity.dxf.rotation = page_rotation
                    
                    # Masking to prevent double-tracing
                    cv2.rectangle(img, (px_x, px_y), (px_x + px_w, px_y + px_h), (255), -1)
        except:
            pass

    # 3. TRACING (Only if Vector extraction was poor)
    if vector_count < 20:
        if noise > 0:
            img = cv2.medianBlur(img, noise if noise % 2 != 0 else noise + 1)
        thresh = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        if cv2.countNonZero(thresh) > 0:
            skeleton = cv2.ximgproc.thinning(thresh) if hasattr(cv2, 'ximgproc') else thresh
            contours, _ = cv2.findContours(skeleton, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                epsilon = simplify * cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, epsilon, False)
                points = [(pt[0][0] * ratio, (img_h - pt[0][1]) * ratio) for pt in approx]
                if len(points) >= 2:
                    msp.add_lwpolyline(points)

# --- UI ---
st.title("📐 Pro PDF-to-CAD (Orientation Aware)")
with st.sidebar:
    scale_val = st.number_input("Scale Multiplier", value=1.0, step=0.1)
    smooth_val = st.slider("Smoothing", 0.001, 0.05, 0.01, format="%.3f")
    noise_val = st.slider("Denoise", 0, 9, 3, step=2)
    ocr_toggle = st.checkbox("Enable OCR", value=True)

uploaded_file = st.file_uploader("Upload PDF", type="pdf")
if uploaded_file and st.button("🚀 Generate DXF"):
    pdf = pdfium.PdfDocument(uploaded_file)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    for i, page in enumerate(pdf):
        process_page(page, msp, scale_val, smooth_val, noise_val, ocr_toggle)
    dxf_io = io.StringIO()
    doc.write(dxf_io)
    st.download_button("💾 Download DXF", dxf_io.getvalue(), "converted.dxf", "application/dxf")