import streamlit as st
import subprocess
import os
import zipfile
from pathlib import Path

# Setup temporary directory
TEMP_DIR = Path("temp_conversion")
TEMP_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Free PDF to CAD", page_icon="🏗️")

def convert_pdf_to_dxf(input_pdf, output_dxf):
    try:
        # Added -gs:ps2write to force the older, more stable conversion path
        cmd = [
            "pstoedit",
            "-f", "dxf:-polyline",
            "-df", "Courier", # Fallback for missing fonts
            str(input_pdf),
            str(output_dxf)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# --- UI ---
st.title("🏗️ Free Batch PDF to DXF Converter")
st.info("Converts vector PDFs to DXF (CAD) for free. Best for blueprints and schematics.")

uploaded_files = st.file_uploader("Upload PDF files", type="pdf", accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 Convert to DXF"):
        dxf_files = []
        
        for uploaded_file in uploaded_files:
            pdf_path = TEMP_DIR / uploaded_file.name
            dxf_name = uploaded_file.name.replace(".pdf", ".dxf")
            dxf_path = TEMP_DIR / dxf_name
            
            # Save upload to temp
            with open(pdf_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Convert
            with st.spinner(f"Processing {uploaded_file.name}..."):
                if convert_pdf_to_dxf(pdf_path, dxf_path):
                    dxf_files.append(dxf_path)
        
        if dxf_files:
            st.success(f"Successfully converted {len(dxf_files)} files!")
            
            # If multiple files, create a ZIP
            if len(dxf_files) > 1:
                zip_path = TEMP_DIR / "converted_files.zip"
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for f in dxf_files:
                        zipf.write(f, arcname=f.name)
                
                with open(zip_path, "rb") as f:
                    st.download_button("📥 Download All (ZIP)", f, "cad_drawings.zip")
            else:
                # If single file, download directly
                with open(dxf_files[0], "rb") as f:
                    st.download_button(f"📥 Download {dxf_files[0].name}", f, dxf_files[0].name)

# Sidebar cleanup
if st.sidebar.button("🧹 Clear temporary files"):
    for file in TEMP_DIR.glob("*"):
        os.remove(file)
    st.sidebar.write("Cleaned!")
