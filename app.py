import streamlit as st
import ezdxf
import pypdfium2 as pdfium
import io
import os

st.set_page_config(page_title="PDF to DXF Converter", page_icon="🏗️")

st.title("🏗️ PDF to DXF Converter")
st.write("Upload a vector PDF to convert it into a CAD-readable DXF format.")

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

import pypdfium2 as pdfium
import ezdxf
import io

def convert_pdf_to_dxf(pdf_file):
    # 1. Load the PDF
    pdf = pdfium.PdfDocument(pdf_file)
    
    # 2. Setup the DXF
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    for page in pdf:
        # 3. Iterate through objects
        for obj in page.get_objects():
            # Check if it's a Path object (lines, shapes, etc.)
            if isinstance(obj, pdfium.PdfPath):
                points = []
                # 4. Extract segments from the path
                path_data = obj.get_path() 
                
                for segment in path_data:
                    # Each segment contains points (usually 1 for lines, more for curves)
                    if hasattr(segment, 'points') and len(segment.points) > 0:
                        # Grab the x, y coordinates
                        p = segment.points[-1]
                        points.append((p.x, p.y))
                
                # 5. Add to DXF if we have a valid line
                if len(points) >= 2:
                    msp.add_lwpolyline(points)

    # 6. Stream to buffer
    dxf_buffer = io.StringIO()
    doc.write(dxf_buffer)
    return dxf_buffer.getvalue()


if uploaded_file:
    with st.spinner("Processing vectors..."):
        try:
            dxf_data = convert_pdf_to_dxf(uploaded_file)
            
            st.success("Conversion complete!")
            st.download_button(
                label="Download DXF File",
                data=dxf_data,
                file_name=f"{uploaded_file.name.rsplit('.', 1)[0]}.dxf",
                mime="application/dxf"
            )
        except Exception as e:
            st.error(f"An error occurred: {e}")
            st.info("Note: This tool works best with vector PDFs (exported from CAD). Scanned PDFs require OCR/Trace logic.")