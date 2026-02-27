import streamlit as st
import ezdxf
import pypdfium2 as pdfium
import io
import numpy as np
import cv2
from PIL import Image

st.set_page_config(page_title="Universal PDF to DXF", page_icon="🏗️")

def trace_image_to_dxf(pdf_file, msp, scale_factor):
    """Converts raster/scanned PDF pages to DXF lines using OpenCV."""
    pdf = pdfium.PdfDocument(pdf_file)
    for page in pdf:
        # 1. Render PDF page to image (300 DPI for accuracy)
        bitmap = page.render(scale=4) # scale=4 provides high res for tracing
        pil_image = bitmap.to_pil()
        
        # 2. Convert to OpenCV format (Grayscale)
        opencv_img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2GRAY)
        
        # 3. Thresholding: Make it strictly Black and White
        _, thresh = cv2.threshold(opencv_img, 127, 255, cv2.THRESH_BINARY_INV)
        
        # 4. Find Contours (The 'Tracing' part)
        contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            # Simplify the contour to reduce DXF file size
            epsilon = 0.001 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            
            points = []
            for pt in approx:
                x, y = pt[0]
                # Flip Y coordinate because Images start top-left, CAD starts bottom-left
                points.append((x * scale_factor, (pil_image.height - y) * scale_factor))
            
            if len(points) > 1:
                msp.add_lwpolyline(points)

def convert_pdf_to_dxf(pdf_file, scale_factor):
    pdf = pdfium.PdfDocument(pdf_file)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    found_vectors = False
    for page in pdf:
        for obj in page.get_objects():
            if obj.type == 2: # Path
                found_vectors = True
                path_data = obj.get_path()
                points = []
                for segment in path_data:
                    if hasattr(segment, 'points'):
                        for pt in segment.points:
                            points.append((pt.x * scale_factor, pt.y * scale_factor))
                if len(points) >= 2:
                    msp.add_lwpolyline(points)

    # If no vectors were found, trigger the Tracing logic
    if not found_vectors:
        st.info("No vectors detected. Switching to 'Scanned Image' tracing mode...")
        trace_image_to_dxf(pdf_file, msp, scale_factor)

    dxf_buffer = io.StringIO()
    doc.write(dxf_buffer)
    return dxf_buffer.getvalue()

# --- Streamlit UI ---
st.title("🏗️ Universal PDF to DXF Converter")
st.write("Supports both **Vector PDFs** and **Scanned Blueprints**.")

scale = st.sidebar.number_input("Scale Factor", value=0.1)
uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file:
    if st.button("Convert Now"):
        with st.spinner("Processing... (Scans take longer)"):
            try:
                result = convert_pdf_to_dxf(uploaded_file, scale)
                st.success("Conversion Finished!")
                st.download_button("Download DXF", result, "output.dxf", "application/dxf")
            except Exception as e:
                st.error(f"Error: {e}")