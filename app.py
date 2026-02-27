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
    
    # Create a new DXF document
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    for page_index in range(len(pdf)):
        page = pdf[page_index]
        # Get all objects on the page
        obj_list = page.get_objects()
        
        for obj in obj_list:
            # In pypdfium2 v4+, we check the object type via constants
            # or by checking if it's a 'PdfPath' object
            if isinstance(obj, pdfium.PdfPath):
                # Get the path segments (moves, lines, curves)
                path_data = obj.get_path()
                points = []
                
                for segment in path_data:
                    # segment usually returns (type, x, y) or similar
                    # We extract the coordinate points
                    if len(segment) >= 3:
                        points.append((segment[-2], segment[-1]))
                
                if len(points) >= 2:
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