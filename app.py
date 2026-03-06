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

def process_page(page, msp, scale_val, simplify, noise, use_ocr):
    # Get physical page dimensions (in points)
    left, bottom, right, top = page.get_bbox()
    p_width = right - left
    p_height = top - bottom
    
    # 1. ATTEMPT VECTOR EXTRACTION
    # (Prioritize this for MDOT/WSDOT style digital exports)
    vector_count = 0
    try:
        for obj in page.get_objects():
            if obj.type == 2: # PATH object
                path_data = obj.get_path()
                points = []
                for segment in path_data:
                    if hasattr(segment, 'points'):
                        for pt in segment.points:
                            # Flip Y: CAD (0,0) is bottom-left
                            points.append((pt.x * scale_val, (p_height - pt.y) * scale_val))
                if len(points) >= 2:
                    msp.add_lwpolyline(points)
                    vector_count += 1
    except Exception as e:
        st.sidebar.error(f"Vector Error: {e}")

    # 2. RASTER PROCESSING
    # Higher scale (4) improves OCR, but we must normalize coordinates later
    render_resolution = 4 
    bitmap = page.render(scale=render_resolution)
    pil_img = bitmap.to_pil().convert("L")
    img = np.array(pil_img)
    img_h, img_w = img.shape

    # Normalization ratio: converts pixel coords back to CAD units
    # (scale_val / render_resolution)
    ratio = scale_val / render_resolution

    # OCR TEXT HANDLING
    if use_ocr:
        try:
            # PSM 3 is better for sparse text on blueprints
            custom_config = r'--oem 3 --psm 3'
            ocr_data = pytesseract.image_to_data(pil_img, config=custom_config, output_type=pytesseract.Output.DICT)
            
            for i in range(len(ocr_data['text'])):
                conf = int(ocr_data['conf'][i])
                txt = ocr_data['text'][i].strip()
                
                if conf > 75 and len(txt) > 1:
                    # Raw pixel coordinates from Tesseract
                    px_x, px_y = ocr_data['left'][i], ocr_data['top'][i]
                    px_w, px_h = ocr_data['width'][i], ocr_data['height'][i]

                    # Scale coordinates to CAD Model Space
                    cad_x = px_x * ratio
                    cad_y = (img_h - px_y) * ratio
                    cad_text_h = px_h * ratio * 0.8 # 0.8 factor for text padding

                    # Add to CAD
                    msp.add_text(txt, height=cad_text_h).set_placement((cad_x, cad_y))
                    
                    # MASK: Whiten out text in the image so line-tracing skips it
                    cv2.rectangle(img, (px_x, px_y), (px_x + px_w, px_y + px_h), (255), -1)
        except Exception as e:
            st.sidebar.warning(f"OCR Notice: {e}")

    # 3. LINE TRACING (Only if no vectors were found to prevent ghosting)
    if vector_count < 10:
        if noise > 0:
            img = cv2.medianBlur(img, noise if noise % 2 != 0 else noise + 1)
        
        thresh = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY_INV, 11, 2)

        if cv2.countNonZero(thresh) > 0:
            # Use thinning to find the centerline of thick blueprint lines
            skeleton = cv2.ximgproc.thinning(thresh) if hasattr(cv2, 'ximgproc') else thresh
            
            contours, _ = cv2.findContours(skeleton, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                epsilon = simplify * cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, epsilon, False)
                
                # Normalize trace points back to CAD units
                points = [(pt[0][0] * ratio, (img_h - pt[0][1]) * ratio) for pt in approx]
                if len(points) >= 2:
                    msp.add_lwpolyline(points)

# --- Streamlit User Interface ---
st.title("📐 Professional PDF to DXF Converter")
st.write("Specialized for **Traffic Signal Plans** and **MDOT/WSDOT Blueprints**.")

with st.sidebar:
    st.header("🔧 Engine Settings")
    scale_val = st.number_input("Scale Multiplier", value=1.0, step=0.1, help="Usually 1.0 for digital PDFs.")
    smooth_val = st.slider("Line Smoothing", 0.001, 0.05, 0.01, format="%.3f")
    noise_val = st.slider("Denoise Strength", 0, 9, 3, step=2)
    ocr_toggle = st.checkbox("Enable OCR Text Recognition", value=True)
    st.divider()
    st.info("Logic: If the PDF contains native CAD vectors, the engine will use them directly to ensure table alignment.")

uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

if uploaded_file:
    if st.button("🚀 Generate CAD File"):
        with st.spinner("Processing..."):
            try:
                pdf = pdfium.PdfDocument(uploaded_file)
                doc = ezdxf.new('R2010')
                msp = doc.modelspace()
                
                progress_bar = st.progress(0)
                for i, page in enumerate(pdf):
                    process_page(page, msp, scale_val, smooth_val, noise_val, ocr_toggle)
                    progress_bar.progress((i + 1) / len(pdf))
                
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
                st.error(f"Error: {e}")