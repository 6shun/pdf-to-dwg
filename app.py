import streamlit as st
import ezdxf
import pypdfium2 as pdfium
import io
import os

st.set_page_config(page_title="PDF to DXF Converter", page_icon="🏗️")

st.title("🏗️ PDF to DXF Converter")
st.write("Upload a vector PDF to convert it into a CAD-readable DXF format.")

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

def convert_pdf_to_dxf(pdf_file):
    # Load the PDF
    pdf = pdfium.PdfDocument(pdf_file)
    
    # Create a new DXF document (R2010 is widely compatible)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    for page_index in range(len(pdf)):
        page = pdf[page_index]
        # High-level extraction of vector paths
        # Note: This assumes the PDF contains vector data, not just a scanned image
        path_objects = page.get_objects()
        
        for obj in path_objects:
            if obj.type == pdfium.PDFOBJ_PATH:
                path_data = obj.get_path()
                # Simplified path extraction
                points = []
                for segment in path_data:
                    # Capture coordinates (x, y)
                    points.append((segment[1], segment[2]))
                
                if len(points) >= 2:
                    msp.add_lwpolyline(points)

    # Save to a buffer
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