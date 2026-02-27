import streamlit as st
import ezdxf
import pypdfium2 as pdfium
import io

def convert_pdf_to_dxf(pdf_file):
    pdf = pdfium.PdfDocument(pdf_file)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # PDFium Object Type Constants:
    # 1: TEXT, 2: PATH, 3: IMAGE, 4: SHADING, 5: FORM
    
    for page in pdf:
        obj_list = page.get_objects()
        for obj in obj_list:
            # Check if it's a PATH object using the integer ID
            if obj.type == 2: 
                try:
                    # In newer versions, we access the path directly
                    path_data = obj.get_path()
                    points = []
                    
                    for segment in path_data:
                        # Extract coordinates from the segment points
                        if hasattr(segment, 'points'):
                            for pt in segment.points:
                                points.append((pt.x, pt.y))
                    
                    if len(points) >= 2:
                        msp.add_lwpolyline(points)
                except AttributeError:
                    # Fallback for older/different sub-versions
                    continue

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