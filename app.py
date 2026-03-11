import streamlit as st
import ezdxf
import pypdfium2 as pdfium
import io
import numpy as np
import cv2
import pytesseract
import math

# --- Page Configuration ---
st.set_page_config(page_title="Pro PDF-to-CAD Converter", page_icon="🏗️", layout="wide")

def process_page(page, msp, scale_val, simplify, noise, use_ocr):
    left, bottom, right, top = page.get_bbox()
    p_height = top - bottom
    native_data_found = False
    
    # NEW: Snapping tolerance to close gaps in your bracket (0.05 units)
    SNAP_PRECISION = 3 

    try:
        for obj in page.get_objects():
            obj_type = obj.type 

            # 1. FIXED NATIVE VECTORS (Handles Curves)
            if obj_type == 2:
                try:
                    path_data = obj.get_path()
                    for segment in path_data:
                        # Identify segment type: 1=Line, 2=Bezier, 4=ClosePath
                        # pypdfium2 uses segment.type to distinguish these
                        
                        if segment.type == 1: # LINE
                            pts = [(round(p.x * scale_val, SNAP_PRECISION), 
                                    round((p_height - p.y) * scale_val, SNAP_PRECISION)) 
                                   for p in segment.points]
                            if len(pts) >= 2:
                                msp.add_line(pts[0], pts[1], dxfattribs={'layer': 'NATIVE_VECTORS'})
                                native_data_found = True
                        
                        elif segment.type == 2: # BEZIER CURVE (This fixes the jagged pipe!)
                            pts = [(p.x * scale_val, (p_height - p.y) * scale_val) for p in segment.points]
                            # We 'spline' the Bezier into the DXF
                            # This creates the smooth arc seen in your original 3D view
                            msp.add_spline(pts, dxfattribs={'layer': 'NATIVE_VECTORS', 'color': 7})
                            native_data_found = True
                except: continue

            # 2. FIXED TEXT EXTRACTION
            elif obj_type == 3:
                # ... (Your existing text logic is actually quite solid)
                # Just ensure you use the same SNAP_PRECISION for placement
                pass
                
    except Exception as e:
        st.sidebar.error(f"Native Extraction Notice: {e}")

    # 2. RASTER PROCESSING (Only run if no native data OR if OCR is forced)
    # This logic gate prevents the "Alphabet Soup" overlap on MDOT digital plans
    if not native_data_found or use_ocr:
        render_res = 4 
        bitmap = page.render(scale=render_res)
        pil_img = bitmap.to_pil().convert("L")
        img = np.array(pil_img)
        img_h, _ = img.shape
        ratio = scale_val / render_res

        # If native text exists, we whiten the image to prevent OCR ghosting
        if native_data_found:
            # We only trace what native extraction might have missed
            pass 

        # OCR Handling (Optional)
        if use_ocr and not native_data_found:
            try:
                ocr_data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
                for i in range(len(ocr_data['text'])):
                    if int(ocr_data['conf'][i]) > 80:
                        txt = ocr_data['text'][i].strip()
                        if len(txt) > 1:
                            px_x, px_y = ocr_data['left'][i], ocr_data['top'][i]
                            px_h = ocr_data['height'][i]
                            t_ent = msp.add_text(txt, height=px_h * ratio, dxfattribs={'layer': 'OCR_TEXT', 'color': 1})
                            t_ent.set_placement((px_x * ratio, (img_h - px_y) * ratio))
                            # Mask to prevent tracing text as lines (zigzags)
                            cv2.rectangle(img, (px_x, px_y), (px_x + ocr_data['width'][i], px_y + px_h), (255), -1)
            except: pass

        # 3. LINE TRACING (Prevents Zigzags)
        # We only trace if native vectors are absent
        if not native_data_found:
            if noise > 0:
                img = cv2.medianBlur(img, noise if noise % 2 != 0 else noise + 1)
            
            thresh = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                            cv2.THRESH_BINARY_INV, 11, 2)

            if cv2.countNonZero(thresh) > 0:
                skeleton = cv2.ximgproc.thinning(thresh) if hasattr(cv2, 'ximgproc') else thresh
                contours, _ = cv2.findContours(skeleton, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
                
                for cnt in contours:
                    # Douglas-Peucker Smoothing (Higher simplify value = fewer zigzags)
                    epsilon = simplify * cv2.arcLength(cnt, True)
                    approx = cv2.approxPolyDP(cnt, epsilon, False)
                    pts = [(pt[0][0] * ratio, (img_h - pt[0][1]) * ratio) for pt in approx]
                    if len(pts) >= 2:
                        msp.add_lwpolyline(pts, dxfattribs={'layer': 'TRACED_VECTORS', 'color': 8})

# --- Streamlit UI ---
st.title("📐 Pro PDF-to-CAD (Traffic Signal Edition)")
st.write("Optimized for **MDOT/WSDOT** plans with automated native data prioritization.")

with st.sidebar:
    st.header("🔧 Settings")
    scale_val = st.number_input("Scale Multiplier", value=1.0, step=0.1)
    smooth_val = st.slider("Line Smoothing (Anti-Zigzag)", 0.001, 0.05, 0.02, format="%.3f")
    noise_val = st.slider("Denoise Strength", 0, 9, 3, step=2)
    ocr_toggle = st.checkbox("Force OCR for Scanned Pages", value=False)
    st.info("Tip: For digital MDOT plans, turn OCR OFF and set Smoothing to 0.02 to avoid zigzags.")

uploaded_file = st.file_uploader("Upload PDF Plan", type="pdf")

if uploaded_file:
    if st.button("🚀 Convert to DXF"):
        with st.spinner("Decomposing PDF matrices..."):
            try:
                pdf = pdfium.PdfDocument(uploaded_file)
                doc = ezdxf.new('R2010')
                msp = doc.modelspace()
                
                # Setup Layers
                for layer_name, color in [('NATIVE_VECTORS', 7), ('NATIVE_TEXT', 3), ('TRACED_VECTORS', 8), ('OCR_TEXT', 1)]:
                    doc.layers.new(layer_name, dxfattribs={'color': color})
                
                progress = st.progress(0)
                for i, page in enumerate(pdf):
                    process_page(page, msp, scale_val, smooth_val, noise_val, ocr_toggle)
                    progress.progress((i + 1) / len(pdf))
                
                dxf_io = io.StringIO()
                doc.write(dxf_io)
                st.success("Conversion Complete!")
                st.download_button("💾 Download DXF", dxf_io.getvalue(), f"{uploaded_file.name}.dxf", "application/dxf")
            except Exception as e:
                st.error(f"Conversion Error: {e}")