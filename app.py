import streamlit as st
import subprocess
import os
import zipfile
from pathlib import Path

# --- CONFIGURATION ---
TEMP_DIR = Path("temp_conversion")
TEMP_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="PDF to DWG Converter", layout="wide")

def convert_pdf_to_dxf(input_pdf, output_dxf):
    """Uses Inkscape CLI to extract vectors from PDF to DXF."""
    try:
        # Inkscape command for PDF to DXF conversion
        subprocess.run([
            "inkscape", 
            str(input_pdf), 
            "--export-type=dxf", 
            f"--export-filename={output_dxf}"
        ], check=True, capture_output=True)
        return True
    except Exception as e:
        st.error(f"Inkscape Error: {e}")
        return False

def convert_dxf_to_dwg(input_dxf_folder, output_dwg_folder):
    """Uses ODA File Converter to wrap DXF into DWG."""
    # Command Format: ODAFileConverter input_dir output_dir OUT_VER OUT_TYPE RECURSE AUDIT
    try:
        subprocess.run([
            "ODAFileConverter", 
            str(input_dxf_folder), 
            str(output_dwg_folder), 
            "ACAD2018", "DWG", "0", "1"
        ], check=True, capture_output=True)
        return True
    except Exception as e:
        st.warning("ODA Converter not found or failed. Returning DXF instead.")
        return False

# --- UI INTERFACE ---
st.title("🏗️ Batch PDF to DWG/DXF Converter")
st.info("Upload PDF blueprints to convert them into editable CAD files.")

uploaded_files = st.file_uploader(
    "Choose PDF files", type="pdf", accept_multiple_files=True
)

if uploaded_files:
    if st.button("🚀 Start Batch Conversion"):
        converted_files = []
        progress_bar = st.progress(0)
        
        for i, uploaded_file in enumerate(uploaded_files):
            # Save uploaded file to temp
            pdf_path = TEMP_DIR / uploaded_file.name
            dxf_path = TEMP_DIR / uploaded_file.name.replace(".pdf", ".dxf")
            
            with open(pdf_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Step 1: PDF -> DXF
            with st.spinner(f"Processing {uploaded_file.name}..."):
                success = convert_pdf_to_dxf(pdf_path, dxf_path)
            
            if success:
                converted_files.append(dxf_path)
            
            progress_bar.progress((i + 1) / len(uploaded_files))

        # Optional Step 2: Try DXF -> DWG (requires ODA File Converter)
        convert_dxf_to_dwg(TEMP_DIR, TEMP_DIR)

        # Zip results for download
        zip_path = TEMP_DIR / "converted_cad_files.zip"
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in TEMP_DIR.glob("*.dwg"):
                zipf.write(file, arcname=file.name)
            # Fallback to DXF if DWG conversion didn't run
            if not list(TEMP_DIR.glob("*.dwg")):
                for file in TEMP_DIR.glob("*.dxf"):
                    zipf.write(file, arcname=file.name)

        st.success("✅ Conversion Complete!")
        
        with open(zip_path, "rb") as f:
            st.download_button(
                label="📥 Download All Converted Files",
                data=f,
                file_name="cad_export.zip",
                mime="application/zip"
            )

# Cleanup instructions
if st.sidebar.button("🧹 Clear Temp Files"):
    for file in TEMP_DIR.glob("*"):
        os.remove(file)
    st.sidebar.write("Temp files deleted.")
