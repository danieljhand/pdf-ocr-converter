import os
import uuid
from datetime import datetime
import shutil
import tempfile
import streamlit as st
import zipfile
import io
import logging
import easyocr
from pdf2image import convert_from_bytes
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PyPDF2 import PdfReader
import numpy as np

# Fix for Pillow compatibility with older libraries
try:
    from PIL import Image
    if not hasattr(Image, 'ANTIALIAS'):
        Image.ANTIALIAS = Image.LANCZOS
    if not hasattr(Image, 'NEAREST'):
        Image.NEAREST = Image.Resampling.NEAREST
    if not hasattr(Image, 'BILINEAR'):
        Image.BILINEAR = Image.Resampling.BILINEAR
    if not hasattr(Image, 'BICUBIC'):
        Image.BICUBIC = Image.Resampling.BICUBIC
except ImportError:
    pass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration constants
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
DEFAULT_MAX_OUTPUT_PDF_SIZE_MB = 10  # Default maximum size for output PDFs

def check_gpu_availability():
    """
    Checks if GPU is available for EasyOCR.
    Returns (gpu_available, gpu_info)
    """
    try:
        # Try to import and check PyTorch CUDA
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "Unknown GPU"
            return True, f"{gpu_name} ({gpu_count} device{'s' if gpu_count > 1 else ''})"
    except ImportError:
        pass
    
    try:
        # Fallback: Try EasyOCR's own GPU detection
        import easyocr
        # Create a temporary reader to test GPU
        test_reader = easyocr.Reader(['en'], gpu=True, verbose=False)
        return True, "GPU detected by EasyOCR"
    except Exception:
        pass
    
    return False, "No GPU available - using CPU"

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
    Checks if required Python libraries are available.
    Returns (tools_available, missing_tools)
    """
    missing_tools = []
    
    try:
        import easyocr
    except ImportError:
        missing_tools.append('easyocr')
    
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        missing_tools.append('pdf2image')
    
    return len(missing_tools) == 0, missing_tools

def create_searchable_pdf(image, ocr_results, output_path, max_size_mb=DEFAULT_MAX_OUTPUT_PDF_SIZE_MB):
    """
    Creates a searchable PDF with the original image and OCR text overlay.
    Compresses the image if the resulting PDF exceeds max_size_mb.
    """
    from PIL import Image as PILImage
    import io
    
    max_size_bytes = max_size_mb * 1024 * 1024
    
    # Try creating PDF with original image first
    temp_output = output_path + ".temp"
    
    def create_pdf_with_image(img, ocr_data, path):
        """Helper function to create PDF with given image and OCR data"""
        img_width, img_height = img.size
        c = canvas.Canvas(path, pagesize=(img_width, img_height))
        
        # Add the image as background
        img_reader = ImageReader(img)
        c.drawImage(img_reader, 0, 0, width=img_width, height=img_height)
        
        # Add invisible OCR text overlay
        for (bbox, text, confidence) in ocr_data:
            if confidence > 0.5:
                x1, y1 = bbox[0]
                x3, y3 = bbox[2]
                
                x = x1
                y = img_height - y3
                width = x3 - x1
                height = y3 - y1
                
                c.setFillColorRGB(0, 0, 0, alpha=0)
                c.setFont("Helvetica", max(8, height * 0.8))
                c.drawString(x, y, text)
        
        c.save()
        return os.path.getsize(path)
    
    # Create initial PDF
    file_size = create_pdf_with_image(image, ocr_results, temp_output)
    
    # If file is within size limit, use it
    if file_size <= max_size_bytes:
        os.rename(temp_output, output_path)
        return
    
    # File is too large, need to compress
    logger.info(f"PDF size ({file_size / 1024 / 1024:.1f}MB) exceeds limit ({max_size_mb}MB), compressing...")
    
    # Calculate compression needed
    compression_ratio = max_size_bytes / file_size
    target_dimension = int(max(image.size) * (compression_ratio ** 0.5))
    target_dimension = min(target_dimension, 1200)  # Cap at 1200px
    
    # Resize image while maintaining aspect ratio
    compressed_image = image.copy()
    if max(compressed_image.size) > target_dimension:
        compressed_image.thumbnail((target_dimension, target_dimension), PILImage.LANCZOS)
    
    # Convert to RGB if RGBA for better compression
    if compressed_image.mode == 'RGBA':
        rgb_image = PILImage.new('RGB', compressed_image.size, (255, 255, 255))
        rgb_image.paste(compressed_image, mask=compressed_image.split()[-1])
        compressed_image = rgb_image
    
    # Apply JPEG compression
    jpeg_buffer = io.BytesIO()
    compressed_image.save(jpeg_buffer, format='JPEG', quality=85, optimize=True)
    jpeg_buffer.seek(0)
    compressed_image = PILImage.open(jpeg_buffer)
    
    # Scale OCR coordinates to match resized image
    original_width, original_height = image.size
    new_width, new_height = compressed_image.size
    width_scale = new_width / original_width
    height_scale = new_height / original_height
    
    scaled_ocr_results = []
    for (bbox, text, confidence) in ocr_results:
        scaled_bbox = []
        for point in bbox:
            scaled_x = point[0] * width_scale
            scaled_y = point[1] * height_scale
            scaled_bbox.append([scaled_x, scaled_y])
        scaled_ocr_results.append((scaled_bbox, text, confidence))
    
    # Create PDF with compressed image
    compressed_size = create_pdf_with_image(compressed_image, scaled_ocr_results, temp_output)
    
    # If still too large, try more aggressive compression
    if compressed_size > max_size_bytes:
        logger.info(f"Still too large ({compressed_size / 1024 / 1024:.1f}MB), applying more compression...")
        
        # More aggressive resizing
        target_dimension = int(target_dimension * 0.7)
        compressed_image = image.copy()
        compressed_image.thumbnail((target_dimension, target_dimension), PILImage.LANCZOS)
        
        if compressed_image.mode == 'RGBA':
            rgb_image = PILImage.new('RGB', compressed_image.size, (255, 255, 255))
            rgb_image.paste(compressed_image, mask=compressed_image.split()[-1])
            compressed_image = rgb_image
        
        # Lower JPEG quality
        jpeg_buffer = io.BytesIO()
        compressed_image.save(jpeg_buffer, format='JPEG', quality=70, optimize=True)
        jpeg_buffer.seek(0)
        compressed_image = PILImage.open(jpeg_buffer)
        
        # Recalculate scaled OCR coordinates
        new_width, new_height = compressed_image.size
        width_scale = new_width / original_width
        height_scale = new_height / original_height
        
        scaled_ocr_results = []
        for (bbox, text, confidence) in ocr_results:
            scaled_bbox = []
            for point in bbox:
                scaled_x = point[0] * width_scale
                scaled_y = point[1] * height_scale
                scaled_bbox.append([scaled_x, scaled_y])
            scaled_ocr_results.append((scaled_bbox, text, confidence))
        
        create_pdf_with_image(compressed_image, scaled_ocr_results, temp_output)
    
    # Move temp file to final location
    os.rename(temp_output, output_path)
    
    final_size = os.path.getsize(output_path)
    logger.info(f"Final PDF size: {final_size / 1024 / 1024:.1f}MB")

def process_single_pdf(pdf_file, pdf_name, max_output_size_mb=DEFAULT_MAX_OUTPUT_PDF_SIZE_MB):
    """
    Processes a single PDF file using pure Python libraries.
    Returns (processed_pdfs, error_message)
    """
    processed_pdfs = []
    
    # Validate PDF first
    is_valid, validation_error = validate_pdf_file(pdf_file, pdf_name)
    if not is_valid:
        logger.error(f"Validation failed for {pdf_name}: {validation_error}")
        return [], validation_error
    
    temp_dir = None
    reader = None
    
    try:
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Processing {pdf_name} in {temp_dir}")
        
        # Initialize EasyOCR reader with GPU detection
        if reader is None:
            gpu_available, gpu_info = check_gpu_availability()
            logger.info(f"GPU status: {gpu_info}")
            
            if gpu_available:
                st.info(f"🚀 Using GPU acceleration: {gpu_info}")
                reader = easyocr.Reader(['en'], gpu=True)
            else:
                st.info(f"💻 Using CPU processing: {gpu_info}")
                reader = easyocr.Reader(['en'], gpu=False)
        
        # Convert PDF to images using pdf2image
        pdf_file.seek(0)
        images = convert_from_bytes(pdf_file.getvalue(), dpi=300)
        
        if not images:
            return [], f"No pages could be extracted from {pdf_name}"
        
        # Use current timestamp since we can't get creation time from uploaded file
        creation_date = datetime.now().strftime("%Y-%m-%d")
        
        # Process each page image with EasyOCR
        for page_num, image in enumerate(images, 1):
            try:
                # Convert PIL image to numpy array for EasyOCR
                img_array = np.array(image)
                
                # Perform OCR
                ocr_results = reader.readtext(img_array)
                
                # Create searchable PDF with OCR text
                output_uuid = uuid.uuid4()
                output_pdf_name = f"{creation_date}-{output_uuid}.pdf"
                output_pdf_path = os.path.join(temp_dir, output_pdf_name)
                
                # Create PDF with original image and OCR text overlay
                create_searchable_pdf(image, ocr_results, output_pdf_path, max_size_mb=max_output_size_mb)
                
                # Verify output file was created and has content
                if not os.path.exists(output_pdf_path) or os.path.getsize(output_pdf_path) == 0:
                    logger.warning(f"OCR failed to create output for page {page_num}")
                    continue
                
                # Read the processed PDF data
                with open(output_pdf_path, "rb") as f:
                    pdf_data = f.read()
                
                processed_pdfs.append({
                    'name': output_pdf_name,
                    'data': pdf_data
                })
                
            except Exception as e:
                logger.warning(f"Failed to process page {page_num} of {pdf_name}: {e}")
                continue
        
        logger.info(f"Successfully processed {pdf_name}: {len(processed_pdfs)} pages")
        return processed_pdfs, None
        
    except ImportError as e:
        error_msg = f"Missing required Python library: {str(e)}"
        logger.error(f"Import error for {pdf_name}: {e}")
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
            st.error(f"Missing required Python libraries: {', '.join(missing_tools)}")
            st.info("**Installation:**")
            st.code("pip install easyocr pdf2image reportlab")
            return
        
        # Display GPU status
        gpu_available, gpu_info = check_gpu_availability()
        if gpu_available:
            st.success(f"🚀 GPU acceleration available: {gpu_info}")
        else:
            st.info(f"💻 Using CPU processing: {gpu_info}")
            st.caption("For faster processing, install PyTorch with CUDA support")
        
        # Add output size configuration
        st.subheader("Output Settings")
        max_output_size = st.slider(
            "Maximum output PDF size (MB)",
            min_value=1,
            max_value=50,
            value=DEFAULT_MAX_OUTPUT_PDF_SIZE_MB,
            step=1,
            help="Larger sizes preserve more image quality but create bigger files. Smaller sizes compress images more aggressively."
        )
        
        st.caption(f"Output PDFs will be compressed to stay under {max_output_size}MB each")
        
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
                
                processed_pdfs, error = process_single_pdf(uploaded_file, uploaded_file.name, max_output_size_mb=max_output_size)
                
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
