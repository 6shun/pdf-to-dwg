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
    pdf = pdfium.PdfDocument(pdf_file)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    for page in pdf:
        # Loop through all objects on the page
        for obj in page.get_objects():
            # Check the integer type directly
            # 2 = PATH (Lines, Rectangles), 1 = TEXT
            if obj.type == 2: 
                path_data = obj.get_path()
                points = []
                
                # Iterate through drawing segments
                for segment in path_data:
                    # In newer versions, segment is an object with 'points'
                    if hasattr(segment, 'points') and len(segment.points) > 0:
                        # Grab the (x, y) of the last point in the segment
                        last_pt = segment.points[-1]
                        points.append((last_pt.x, last_pt.y))
                
                # If we have at least 2 points, draw a line in CAD
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