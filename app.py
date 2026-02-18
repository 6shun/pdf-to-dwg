import streamlit as st
import cloudconvert
import os
import time
import requests
from pathlib import Path

# --- CONFIGURATION ---
# It is better to set this in Streamlit Secrets (Settings > Secrets) as: CLOUDCONVERT_API_KEY = "your_key"
API_KEY = st.secrets.get("CLOUDCONVERT_API_KEY", "PASTE_YOUR_KEY_HERE_IF_NOT_USING_SECRETS")

# Initialize CloudConvert
if API_KEY != "PASTE_YOUR_KEY_HERE_IF_NOT_USING_SECRETS":
    cloudconvert_api = cloudconvert.Api(api_key=API_KEY)
else:
    st.error("Please set your CloudConvert API Key in Streamlit Secrets.")

st.set_page_config(page_title="Professional PDF to DWG", page_icon="🏗️")

st.title("🏗️ Professional PDF to DWG Converter")
st.markdown("""
This app uses a dedicated CAD engine to convert PDFs into **real DWG files**.
* **Cloud-Stable:** No segmentation faults.
* **Format:** Returns AutoCAD-compatible DWG files.
""")

# --- FILE UPLOAD ---
uploaded_files = st.file_uploader("Upload PDF blueprints", type="pdf", accept_multiple_files=True)

if uploaded_files and API_KEY:
    if st.button("🚀 Start Conversion"):
        for uploaded_file in uploaded_files:
            with st.status(f"Converting {uploaded_file.name}...", expanded=True) as status:
                try:
                    # 1. Create a temporary local file
                    temp_pdf = Path(f"temp_{uploaded_file.name}")
                    with open(temp_pdf, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    # 2. Start CloudConvert Job
                    # We convert PDF -> DWG
                    job = cloudconvert_api.Job.create(payload={
                        "tasks": {
                            "import-my-file": {
                                "operation": "import/upload"
                            },
                            "convert-my-file": {
                                "operation": "convert",
                                "input": "import-my-file",
                                "output_format": "dwg",
                                "engine": "autocad" # High quality engine
                            },
                            "export-my-file": {
                                "operation": "export/url",
                                "input": "convert-my-file"
                            }
                        }
                    })

                    # 3. Upload the file to the import task
                    upload_task = [t for t in job['tasks'] if t['name'] == 'import-my-file'][0]
                    cloudconvert_api.Task.upload(file_name=str(temp_pdf), task=upload_task)

                    # 4. Wait for job completion
                    status.write("Engine processing CAD vectors...")
                    res = cloudconvert_api.Job.wait(job['id'])
                    
                    # 5. Get the download URL
                    export_task = [t for t in res['tasks'] if t['name'] == 'export-my-file'][0]
                    file_url = export_task['result']['files'][0]['url']
                    file_name = export_task['result']['files'][0]['filename']

                    # 6. Download file and provide to user
                    response = requests.get(file_url)
                    st.download_button(
                        label=f"📥 Download {file_name}",
                        data=response.content,
                        file_name=file_name,
                        mime="application/acad"
                    )
                    
                    # Cleanup
                    os.remove(temp_pdf)
                    status.update(label=f"✅ {uploaded_file.name} Finished!", state="complete")

                except Exception as e:
                    st.error(f"Error converting {uploaded_file.name}: {str(e)}")

# --- SIDEBAR INFO ---
with st.sidebar:
    st.header("Setup Instructions")
    st.write("1. Create account at [CloudConvert](https://cloudconvert.com)")
    st.write("2. Copy your API Key.")
    st.write("3. Add it to Streamlit Secrets or paste in the code.")
    st.divider()
    if st.button("Clear Cache"):
        st.cache_data.clear()
        st.write("Cache cleared.")
