import streamlit as st
import ezdxf
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
import io
import numpy as np
import cv2
import pytesseract
from PIL import Image
import math

# --- Page Configuration ---
st.set_page_config(page_title="Pro PDF-to-CAD Converter", page_icon="🏗️", layout="wide")

def process_page(page, msp, scale_val, simplify, noise, use_ocr):
    # Get physical page dimensions (in points)
    left, bottom, right, top = page.get_bbox()
    p_width = right - left
    p_height = top - bottom
    
    # 1. NATIVE VECTOR & TEXT EXTRACTION
    # This section handles high-quality digital PDFs (MDOT/WSDOT exports)
    vector_count = 0
    try:
        for obj in page.get_objects():
            # PATH OBJECTS (Lines, Polylines, Rectangles)
            if obj.type == pdfium_c.FPDF_PAGEOBJECT_PATH:
                try:
                    path_data = obj.get_path()
                    points = []
                    for segment in path_data:
                        if hasattr(segment, 'points'):
                            for pt in segment.points:
                                # Flip Y: CAD (0,0) is bottom-left, PDF (0,0) is often top-left
                                points.append((pt.x * scale_val, (p_height - pt.y) * scale_val))
                    if len(points) >= 2:
                        msp.add_lwpolyline(points, dxfattribs={'layer': 'VECTORS_NATIVE'})
                        vector_count += 1
                except:
                    continue
            
            # TEXT OBJECTS (Preserves exact rotation and font size)
            elif obj.type == pdfium_c.FPDF_PAGEOBJECT_TEXT:
                try:
                    text_str = obj.get_text()
                    if text_str and text_str.strip():
                        pos = obj.get_pos() # (x, y)
                        fs = obj.get_fontsize()
                        
                        # Extract rotation from transformation matrix
                        # [a, b, c, d, e, f] -> rotation = atan2(b, a)
                        matrix = obj.get_matrix()
                        rotation = math.degrees(math.atan2(matrix[1], matrix[0]))
                        
                        text_entity = msp.add_text(text_str, 
                                                   height=fs * scale_val, 
                                                   dxfattribs={'layer': 'TEXT_NATIVE'})
                        text_entity.set_placement((pos[0] * scale_val, (p_height - pos[1]) * scale_val))
                        text_entity.dxf.rotation = rotation
                except:
                    continue
    except Exception as e:
        st.sidebar.error(f"Native Extraction Error: {e}")

    # 2. RASTER PROCESSING (For Scans or Hybrid Content)
    render_res = 4 
    bitmap = page.render(scale=render_res)
    pil_img = bitmap.to_pil().convert("L")
    img = np.array(pil_img)
    img_h, _ = img.shape
    
    # Ratio to convert high-res pixels back to CAD units
    ratio = scale_val / render_res

    if use_ocr:
        try:
            # Orientation and Script Detection (OSD) for scanned pages
            osd = pytesseract.image_to_osd(pil_img, output_type=pytesseract.Output.DICT)
            page_rotation = osd.get('rotate', 0)

            custom_config = r'--oem 3 --psm 3'
            ocr_data = pytesseract.image_to_data(pil_img, config=custom_config, output_type=pytesseract.Output.DICT)
            
            for i in range(len(ocr_data['text'])):
                conf = int(ocr_data['conf'][i])
                txt = ocr_data['text'][i].strip()
                
                if conf > 75 and len(txt) > 1:
                    px_x, px_y = ocr_data['left'][i], ocr_data['top'][i]
                    px_w, px_h = ocr_data['width'][i], ocr_data['height'][i]

                    cad_x = px_x * ratio
                    cad_y = (img_h - px_y) * ratio
                    
                    t_entity = msp.add_text(txt, height=px_h * ratio * 0.8, dxfattribs={'layer': 'TEXT_OCR'})
                    t_entity.set_placement((cad_x, cad_y))

                    # Heuristic for vertical text: if box is very tall
                    if px_h > px_w * 1.8:
                        t_entity.dxf.rotation = 90
                    else:
                        t_entity.dxf.rotation = page_rotation
                    
                    # MASK: Whiten out text so the line tracer ignores it
                    cv2.rectangle(img, (px_x, px_y), (px_x + px_w, px_y + px_h), (255), -1)
        except:
            pass

    # 3. LINE TRACING (Only used if the PDF lacks native vectors)
    if vector_count < 20:
        if noise > 0:
            img = cv2.medianBlur(img, noise if noise % 2 != 0 else noise + 1)
        
        thresh = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY_INV, 11, 2)

        if cv2.countNonZero(thresh) > 0:
            # Thinning reduces lines to 1-pixel spines to prevent "hollow" boxes in CAD
            skeleton = cv2.ximgproc.thinning(thresh) if hasattr(cv2, 'ximgproc') else thresh
            
            contours, _ = cv2.findContours(skeleton, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                epsilon = simplify * cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, epsilon, False)
                points = [(pt[0][0] * ratio, (img_h - pt[0][1]) * ratio) for pt in approx]
                if len(points) >= 2:
                    msp.add_lwpolyline(points, dxfattribs={'layer': 'VECTORS_TRACED'})

# --- User Interface ---
st.title("📐 Professional PDF to DXF Converter")
st.write("Optimized for **MDOT/WSDOT Engineering Plans** with oriented text and vector layers.")

with st.sidebar:
    st.header("🔧 Settings")
    scale_val = st.number_input("Scale Multiplier", value=1.0, step=0.1)
    smooth_val = st.slider("Line Smoothing", 0.001, 0.05, 0.01, format="%.3f")
    noise_val = st.slider("Denoise Strength", 0, 9, 3, step=2)
    ocr_toggle = st.checkbox("Enable OCR for Scans", value=True)
    st.divider()
    st.info("The tool will prioritize native CAD vectors if they exist in the PDF.")

uploaded_file = st.file_uploader("Upload PDF file", type="pdf")

if uploaded_file:
    if st.button("🚀 Generate CAD File"):
        with st.spinner("Analyzing PDF layers and extracting geometry..."):
            try:
                pdf = pdfium.PdfDocument(uploaded_file)
                doc = ezdxf.new('R2010')
                
                # Setup Layers for organization
                doc.layers.new('VECTORS_NATIVE', dxfattribs={'color': 7})
                doc.layers.new('VECTORS_TRACED', dxfattribs={'color': 8})
                doc.layers.new('TEXT_NATIVE', dxfattribs={'color': 2})
                doc.layers.new('TEXT_OCR', dxfattribs={'color': 3})
                
                msp = doc.modelspace()
                
                progress_bar = st.progress(0)
                for i, page in enumerate(pdf):
                    process_page(page, msp, scale_val, smooth_val, noise_val, ocr_toggle)
                    progress_bar.progress((i + 1) / len(pdf))
                
                dxf_io = io.StringIO()
                doc.write(dxf_io)
                
                st.success("Conversion Successful!")
                st.download_button(
                    label="💾 Download DXF",
                    data=dxf_io.getvalue(),
                    file_name=f"converted_{uploaded_file.name.split('.')[0]}.dxf",
                    mime="application/dxf"
                )
            except Exception as e:
                st.error(f"Error during processing: {e}")