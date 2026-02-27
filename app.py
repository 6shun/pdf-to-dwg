import streamlit as st
import ezdxf
import pypdfium2 as pdfium
import io

# Page Configuration
st.set_page_config(page_title="PDF to DXF Converter", page_icon="📐")

def convert_pdf_to_dxf(pdf_file, scale_factor):
    # Load the PDF document
    pdf = pdfium.PdfDocument(pdf_file)
    
    # Create a new DXF document (R2010 for high compatibility)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    vector_count = 0

    for page in pdf:
        # Get all objects (Path, Text, Image, etc.)
        for obj in page.get_objects():
            # Type 2 corresponds to PATH objects (lines, shapes)
            if obj.type == 2:
                try:
                    path_data = obj.get_path()
                    points = []
                    
                    for segment in path_data:
                        # Extract and scale coordinates
                        if hasattr(segment, 'points'):
                            for pt in segment.points:
                                # PDF coords are typically (x, y)
                                points.append((pt.x * scale_factor, pt.y * scale_factor))
                    
                    if len(points) >= 2:
                        msp.add_lwpolyline(points)
                        vector_count += 1
                except Exception:
                    continue

    if vector_count == 0:
        raise ValueError("No vector paths found. This PDF might be a scanned image.")

    # Write DXF to a string buffer
    dxf_buffer = io.StringIO()
    doc.write(dxf_buffer)
    return dxf_buffer.getvalue()

# --- UI Layout ---
st.title("📐 PDF to DXF Online Converter")
st.markdown("""
Convert vector-based PDFs (from AutoCAD, Rhino, etc.) into DXF files that you can open in any CAD software.
""")

st.sidebar.header("Settings")
scale = st.sidebar.number_input("Scale Factor", value=1.0, help="Multiply coordinates by this value (e.g., 25.4 to convert inches to mm).")

uploaded_file = st.file_uploader("Upload your PDF", type="pdf")

if uploaded_file:
    if st.button("Convert to DXF"):
        with st.spinner("Analyzing PDF vectors..."):
            try:
                dxf_output = convert_pdf_to_dxf(uploaded_file, scale)
                
                st.success(f"Success! Converted into DXF format.")
                st.download_button(
                    label="💾 Download DXF File",
                    data=dxf_output,
                    file_name=f"{uploaded_file.name.rsplit('.', 1)[0]}.dxf",
                    mime="application/dxf"
                )
            except ValueError as ve:
                st.warning(f"Notice: {ve}")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

st.divider()
st.info("💡 **Pro Tip:** If the downloaded file is empty, the PDF is likely a 'raster' (scanned image). This tool only works with 'vector' PDFs exported directly from design software.")