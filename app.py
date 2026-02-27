import streamlit as st
import ezdxf
import pypdfium2 as pdfium
import io
import numpy as np
import cv2
import pytesseract

def process_clean_page(page, msp, scale, simplify_factor):
    # 1. Render to Image
    bitmap = page.render(scale=4)
    pil_img = bitmap.to_pil().convert("L")
    img = np.array(pil_img)
    
    # 2. OCR Step: Find Text and Mask it
    # We use pytesseract to get 'data' which includes bounding boxes
    ocr_data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
    
    for i in range(len(ocr_data['text'])):
        if int(ocr_data['conf'][i]) > 50:  # Only trust high-confidence text
            x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
            text_str = ocr_data['text'][i].strip()
            
            if text_str:
                # Add real Text to CAD
                msp.add_text(text_str, height=h*scale).set_placement(
                    (x * scale, (pil_img.height - (y + h)) * scale)
                )
                # MASK: Draw a white rectangle over the text so the tracer ignores it
                cv2.rectangle(img, (x, y), (x + w, y + h), (255), -1)

    # 3. Tracing Step (now ignoring the masked text areas)
    thresh = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 11, 2)
    
    # Skeletonize to keep lines thin
    skeleton = cv2.ximgproc.thinning(thresh) if hasattr(cv2, 'ximgproc') else thresh
    contours, _ = cv2.findContours(skeleton, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        epsilon = simplify_factor * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, False)
        points = [(pt[0][0] * scale, (pil_img.height - pt[0][1]) * scale) for pt in approx]
        
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