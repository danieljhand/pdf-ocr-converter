import os
import subprocess
import uuid
from datetime import datetime
import shutil
import tempfile
import streamlit as st

def process_single_pdf(pdf_file, pdf_name):
    """
    Processes a single PDF file:
    1. Converts each page to a PNG image using pdftoppm.
    2. Performs OCR on each PNG using tesseract to create searchable PDFs.
    3. Returns list of processed PDF data with timestamps and UUIDs.
    """
    processed_pdfs = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save uploaded file to temporary location
        input_pdf_path = os.path.join(temp_dir, pdf_name)
        with open(input_pdf_path, "wb") as f:
            f.write(pdf_file.getvalue())
        
        try:
            # Use current timestamp since we can't get creation time from uploaded file
            creation_date = datetime.now().strftime("%Y-%m-%d")
            
            # Create a temporary directory for the PNG images
            temp_image_dir = os.path.join(temp_dir, f"temp_{os.path.splitext(pdf_name)[0]}")
            os.makedirs(temp_image_dir, exist_ok=True)
            
            # Use pdftoppm to convert PDF pages to PNG
            output_base = os.path.join(temp_image_dir, "page")
            pdftoppm_command = [
                "pdftoppm",
                "-png",
                input_pdf_path,
                output_base
            ]
            subprocess.run(pdftoppm_command, check=True, capture_output=True)
            
            # Process each PNG image with tesseract
            for png_file in sorted(os.listdir(temp_image_dir)):
                if png_file.lower().endswith(".png"):
                    png_path = os.path.join(temp_image_dir, png_file)
                    output_uuid = uuid.uuid4()
                    output_pdf_name = f"{creation_date}-{output_uuid}.pdf"
                    output_pdf_path = os.path.join(temp_dir, output_pdf_name)
                    
                    tesseract_command = [
                        "tesseract",
                        png_path,
                        os.path.splitext(output_pdf_path)[0],
                        "-l", "eng",
                        "pdf"
                    ]
                    subprocess.run(tesseract_command, check=True, capture_output=True)
                    
                    # Read the processed PDF data
                    with open(output_pdf_path, "rb") as f:
                        pdf_data = f.read()
                    
                    processed_pdfs.append({
                        'name': output_pdf_name,
                        'data': pdf_data
                    })
            
            return processed_pdfs, None
            
        except FileNotFoundError as e:
            return [], f"Error: {e}. Make sure 'pdftoppm' and 'tesseract' are installed and in your system's PATH."
        except subprocess.CalledProcessError as e:
            return [], f"Error processing {pdf_name}: {e.stderr.decode()}"
        except Exception as e:
            return [], f"An unexpected error occurred: {e}"

def main():
    st.title("PDF OCR Processing Application")
    st.write("Upload PDF files to convert them into searchable PDFs using OCR")
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Choose PDF files",
        type="pdf",
        accept_multiple_files=True,
        help="Upload one or more PDF files to process"
    )
    
    if uploaded_files:
        st.write(f"Uploaded {len(uploaded_files)} file(s)")
        
        # Display uploaded files
        for file in uploaded_files:
            st.write(f"📄 {file.name}")
        
        # Process button
        if st.button("Process PDFs", type="primary"):
            # Initialize session state for results
            if 'processed_results' not in st.session_state:
                st.session_state.processed_results = []
            
            st.session_state.processed_results = []
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_files = len(uploaded_files)
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Processing {uploaded_file.name}...")
                
                processed_pdfs, error = process_single_pdf(uploaded_file, uploaded_file.name)
                
                if error:
                    st.error(f"Error processing {uploaded_file.name}: {error}")
                else:
                    st.session_state.processed_results.extend(processed_pdfs)
                    st.success(f"Successfully processed {uploaded_file.name} - Created {len(processed_pdfs)} searchable PDF(s)")
                
                # Update progress
                progress_bar.progress((i + 1) / total_files)
            
            status_text.text("Processing complete!")
    
    # Display download buttons for processed files
    if 'processed_results' in st.session_state and st.session_state.processed_results:
        st.subheader("Download Processed PDFs")
        
        for result in st.session_state.processed_results:
            st.download_button(
                label=f"Download {result['name']}",
                data=result['data'],
                file_name=result['name'],
                mime="application/pdf"
            )

if __name__ == "__main__":
    main()
