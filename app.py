import os
import subprocess
import uuid
from datetime import datetime
import shutil
import tempfile
import streamlit as st
import zipfile
import io
import logging
import platform
from PyPDF2 import PdfReader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration constants
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

def validate_pdf_file(pdf_file, pdf_name):
    """
    Validates uploaded PDF file for size and format.
    Returns (is_valid, error_message)
    """
    try:
        # Check file size
        pdf_file.seek(0, 2)  # Seek to end
        file_size = pdf_file.tell()
        pdf_file.seek(0)  # Reset to beginning
        
        if file_size > MAX_FILE_SIZE_BYTES:
            return False, f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds limit of {MAX_FILE_SIZE_MB}MB"
        
        # Validate PDF format
        try:
            pdf_reader = PdfReader(pdf_file)
            if len(pdf_reader.pages) == 0:
                return False, "PDF file contains no pages"
        except Exception as e:
            return False, f"Invalid PDF format: {str(e)}"
        finally:
            pdf_file.seek(0)  # Reset for processing
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error validating {pdf_name}: {e}")
        return False, f"Validation error: {str(e)}"

def check_external_tools():
    """
    Checks if required external tools are available.
    Returns (tools_available, missing_tools)
    """
    tools_config = {
        'pdftoppm': ['pdftoppm', '-h'],  # Use -h instead of --version
        'tesseract': ['tesseract', '--version']
    }
    missing_tools = []
    
    for tool_name, command in tools_config.items():
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            # Accept both success (0) and help exit codes (1) for pdftoppm
            if result.returncode not in [0, 1]:
                missing_tools.append(tool_name)
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            missing_tools.append(tool_name)
    
    return len(missing_tools) == 0, missing_tools

def process_single_pdf(pdf_file, pdf_name):
    """
    Processes a single PDF file with comprehensive error handling.
    Returns (processed_pdfs, error_message)
    """
    processed_pdfs = []
    
    # Validate PDF first
    is_valid, validation_error = validate_pdf_file(pdf_file, pdf_name)
    if not is_valid:
        logger.error(f"Validation failed for {pdf_name}: {validation_error}")
        return [], validation_error
    
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Processing {pdf_name} in {temp_dir}")
        
        # Save uploaded file to temporary location
        input_pdf_path = os.path.join(temp_dir, pdf_name)
        with open(input_pdf_path, "wb") as f:
            f.write(pdf_file.getvalue())
        
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
        
        result = subprocess.run(pdftoppm_command, check=True, capture_output=True, text=True)
        logger.info(f"pdftoppm completed for {pdf_name}")
        
        # Check if any PNG files were created
        png_files = [f for f in os.listdir(temp_image_dir) if f.lower().endswith(".png")]
        if not png_files:
            return [], f"No pages could be extracted from {pdf_name}"
        
        # Process each PNG image with tesseract
        for png_file in sorted(png_files):
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
            
            subprocess.run(tesseract_command, check=True, capture_output=True, text=True)
            
            # Verify output file was created and has content
            if not os.path.exists(output_pdf_path) or os.path.getsize(output_pdf_path) == 0:
                logger.warning(f"OCR failed to create output for {png_file}")
                continue
            
            # Read the processed PDF data
            with open(output_pdf_path, "rb") as f:
                pdf_data = f.read()
            
            processed_pdfs.append({
                'name': output_pdf_name,
                'data': pdf_data
            })
        
        logger.info(f"Successfully processed {pdf_name}: {len(processed_pdfs)} pages")
        return processed_pdfs, None
        
    except FileNotFoundError as e:
        error_msg = f"Missing required tool. Please install pdftoppm and tesseract: {str(e)}"
        logger.error(f"Tool missing for {pdf_name}: {e}")
        return [], error_msg
    except subprocess.CalledProcessError as e:
        error_msg = f"Processing failed: {e.stderr.decode() if e.stderr else str(e)}"
        logger.error(f"Subprocess error for {pdf_name}: {e}")
        return [], error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Unexpected error processing {pdf_name}: {e}")
        return [], error_msg
    finally:
        # Ensure cleanup happens even on errors
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory for {pdf_name}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {temp_dir}: {e}")

def create_zip_archive(processed_pdfs):
    """
    Creates a ZIP archive containing all processed PDF files.
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for pdf in processed_pdfs:
            zip_file.writestr(pdf['name'], pdf['data'])
    
    zip_buffer.seek(0)
    return zip_buffer

def main():
    st.title("PDF OCR Processing Application")
    st.write("Upload PDF files to convert them into searchable PDFs using OCR")
    
    # File uploader with validation
    uploaded_files = st.file_uploader(
        "Choose PDF files",
        type="pdf",
        accept_multiple_files=True,
        help=f"Upload PDF files (max {MAX_FILE_SIZE_MB}MB each)"
    )

    if uploaded_files:
        st.write(f"Uploaded {len(uploaded_files)} file(s)")
        
        # Check external tools first
        tools_available, missing_tools = check_external_tools()
        if not tools_available:
            st.error(f"Missing required tools: {', '.join(missing_tools)}")
            
            # Platform-specific installation instructions
            system = platform.system().lower()
            
            if system == "darwin":  # macOS
                st.info("**macOS Installation:**")
                st.code("brew install poppler tesseract")
            elif system == "linux":
                st.info("**Linux Installation:**")
                st.code("sudo apt-get install poppler-utils tesseract-ocr  # Ubuntu/Debian")
                st.code("sudo yum install poppler-utils tesseract        # RHEL/CentOS")
            else:
                st.info("**Installation required:**")
                st.write("- **poppler-utils** (for pdftoppm)")
                st.write("- **tesseract-ocr** (for OCR processing)")
            
            return
        
        # Display uploaded files with size info
        for file in uploaded_files:
            file_size_mb = len(file.getvalue()) / 1024 / 1024
            if file_size_mb > MAX_FILE_SIZE_MB:
                st.error(f"📄 {file.name} ({file_size_mb:.1f}MB) - Exceeds size limit")
            else:
                st.write(f"📄 {file.name} ({file_size_mb:.1f}MB)")
        
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
        
        # Individual downloads
        for result in st.session_state.processed_results:
            st.download_button(
                label=f"Download {result['name']}",
                data=result['data'],
                file_name=result['name'],
                mime="application/pdf"
            )
        
        # ZIP archive download
        st.subheader("Download All as ZIP Archive")
        zip_buffer = create_zip_archive(st.session_state.processed_results)
        st.download_button(
            label="Download All PDFs as ZIP",
            data=zip_buffer,
            file_name="processed_pdfs.zip",
            mime="application/zip"
        )

if __name__ == "__main__":
    main()
