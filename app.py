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
    pdf = pdfium.PdfDocument(pdf_file)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # PDF coordinates usually start from bottom-left
    # DXF coordinates also start from bottom-left
    
    for page_index in range(len(pdf)):
        page = pdf[page_index]
        
        # This is the modern way to loop through objects
        for obj in page.get_objects():
            # Check if the object is a PATH (lines, rectangles, etc.)
            # Type 2 is usually the constant for PATH in PDFium
            if obj.get_type() == 2: 
                path_data = obj.get_path()
                points = []
                
                # Iterate through path segments (MoveTo, LineTo, etc.)
                for segment in path_data:
                    # Each segment contains points; we extract the last (x, y)
                    if len(segment.points) > 0:
                        pt = segment.points[-1]
                        points.append((pt.x, pt.y))
                
                if len(points) >= 2:
                    # Create the polyline in CAD space
                    msp.add_lwpolyline(points)

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