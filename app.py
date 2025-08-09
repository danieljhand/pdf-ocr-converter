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

# Configure PIL to handle large images safely
from PIL import Image as PILImage
PILImage.MAX_IMAGE_PIXELS = None  # Remove the limit, but we'll add our own checks

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
    
    # Check image dimensions and reduce if too large
    max_pixels = 50_000_000  # 50 megapixels - reasonable limit
    current_pixels = image.size[0] * image.size[1]
    
    if current_pixels > max_pixels:
        logger.info(f"Image too large ({current_pixels:,} pixels), resizing for safety...")
        # Calculate scale factor to reduce to max_pixels
        scale_factor = (max_pixels / current_pixels) ** 0.5
        new_width = int(image.size[0] * scale_factor)
        new_height = int(image.size[1] * scale_factor)
        image = image.resize((new_width, new_height), PILImage.LANCZOS)
        logger.info(f"Resized to {new_width}x{new_height} ({new_width * new_height:,} pixels)")
    
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
    
    # Start with conservative compression - try JPEG quality reduction first
    compressed_image = image.copy()
    
    # Convert to RGB if RGBA for better compression
    if compressed_image.mode == 'RGBA':
        rgb_image = PILImage.new('RGB', compressed_image.size, (255, 255, 255))
        rgb_image.paste(compressed_image, mask=compressed_image.split()[-1])
        compressed_image = rgb_image
    
    # Try different JPEG quality levels before resizing
    for quality in [90, 80, 70, 60]:
        jpeg_buffer = io.BytesIO()
        compressed_image.save(jpeg_buffer, format='JPEG', quality=quality, optimize=True)
        jpeg_buffer.seek(0)
        test_image = PILImage.open(jpeg_buffer)
        
        # Test PDF size with this compression
        test_size = create_pdf_with_image(test_image, ocr_results, temp_output)
        
        if test_size <= max_size_bytes:
            # Cache the successful JPEG compression settings
            create_searchable_pdf._last_compression_settings = {
                'method': 'jpeg_only',
                'jpeg_quality': quality
            }
            logger.info(f"Achieved target size with JPEG quality {quality}: {test_size / 1024 / 1024:.1f}MB")
            logger.info(f"Cached compression settings: JPEG quality {quality}")
            os.rename(temp_output, output_path)
            return
        
        logger.info(f"JPEG quality {quality} still too large: {test_size / 1024 / 1024:.1f}MB")
    
    # If JPEG compression alone isn't enough, try gradual resizing
    original_width, original_height = image.size
    max_dimension = max(original_width, original_height)
    
    # Try different resize levels
    for resize_factor in [0.9, 0.8, 0.7, 0.6, 0.5]:
        target_dimension = int(max_dimension * resize_factor)
        
        # Don't go below reasonable resolution
        if target_dimension < 600:
            break
            
        compressed_image = image.copy()
        compressed_image.thumbnail((target_dimension, target_dimension), PILImage.LANCZOS)
        
        # Convert to RGB if needed
        if compressed_image.mode == 'RGBA':
            rgb_image = PILImage.new('RGB', compressed_image.size, (255, 255, 255))
            rgb_image.paste(compressed_image, mask=compressed_image.split()[-1])
            compressed_image = rgb_image
        
        # Apply moderate JPEG compression
        jpeg_buffer = io.BytesIO()
        compressed_image.save(jpeg_buffer, format='JPEG', quality=75, optimize=True)
        jpeg_buffer.seek(0)
        compressed_image = PILImage.open(jpeg_buffer)
        
        # Scale OCR coordinates to match resized image
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
        
        # Test PDF size with this compression
        test_size = create_pdf_with_image(compressed_image, scaled_ocr_results, temp_output)
        
        if test_size <= max_size_bytes:
            # Cache the successful resize + JPEG compression settings
            create_searchable_pdf._last_compression_settings = {
                'method': 'resize_and_jpeg',
                'resize_factor': resize_factor,
                'jpeg_quality': 75
            }
            logger.info(f"Achieved target size with {resize_factor*100:.0f}% resize: {test_size / 1024 / 1024:.1f}MB")
            logger.info(f"Cached compression settings: {resize_factor*100:.0f}% resize + JPEG quality 75")
            os.rename(temp_output, output_path)
            return
        
        logger.info(f"Resize to {resize_factor*100:.0f}% still too large: {test_size / 1024 / 1024:.1f}MB")
    
    # If we get here, use the last compressed version (it's the best we can do)
    logger.warning(f"Could not achieve target size, using maximum compression: {test_size / 1024 / 1024:.1f}MB")
    os.rename(temp_output, output_path)
    
    # Cache the compression settings for subsequent pages
    if file_size <= max_size_bytes:
        # No compression was needed
        create_searchable_pdf._last_compression_settings = {
            'method': 'no_compression'
        }
        logger.info("Cached compression settings: no compression needed")
        os.rename(temp_output, output_path)
        return
    
    # If we get here, use the last compressed version (it's the best we can do)
    logger.warning(f"Could not achieve target size, using maximum compression: {test_size / 1024 / 1024:.1f}MB")
    
    # Cache the final compression settings used
    if 'resize_factor' in locals():
        create_searchable_pdf._last_compression_settings = {
            'method': 'resize_and_jpeg',
            'resize_factor': resize_factor,
            'jpeg_quality': 75
        }
        logger.info(f"Cached compression settings: {resize_factor*100:.0f}% resize + JPEG quality 75")
    else:
        create_searchable_pdf._last_compression_settings = {
            'method': 'jpeg_only',
            'jpeg_quality': 60  # Last quality tried
        }
        logger.info("Cached compression settings: JPEG quality 60")
    
    os.rename(temp_output, output_path)
    
    final_size = os.path.getsize(output_path)
    logger.info(f"Final PDF size: {final_size / 1024 / 1024:.1f}MB")

def process_single_pdf(pdf_file, pdf_name, max_output_size_mb=DEFAULT_MAX_OUTPUT_PDF_SIZE_MB, progress_callback=None):
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
        
        if progress_callback:
            progress_callback(f"Initializing OCR for {pdf_name}...")
        
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
        
        if progress_callback:
            progress_callback(f"Converting {pdf_name} to images...")
        
        # Convert PDF to images using pdf2image
        pdf_file.seek(0)
        file_size_mb = len(pdf_file.getvalue()) / 1024 / 1024
        
        # Use lower DPI for larger files to prevent memory issues
        if file_size_mb > 20:
            dpi = 200  # Lower DPI for large files
        elif file_size_mb > 10:
            dpi = 250  # Medium DPI for medium files
        else:
            dpi = 300  # Full DPI for smaller files
            
        logger.info(f"Converting {pdf_name} ({file_size_mb:.1f}MB) at {dpi} DPI")
        images = convert_from_bytes(pdf_file.getvalue(), dpi=dpi)
        
        if not images:
            return [], f"No pages could be extracted from {pdf_name}"
        
        # Check and resize images if they're too large
        max_pixels = 50_000_000  # 50 megapixels
        processed_images = []
        
        for i, image in enumerate(images):
            current_pixels = image.size[0] * image.size[1]
            if current_pixels > max_pixels:
                logger.info(f"Page {i+1} too large ({current_pixels:,} pixels), resizing...")
                scale_factor = (max_pixels / current_pixels) ** 0.5
                new_width = int(image.size[0] * scale_factor)
                new_height = int(image.size[1] * scale_factor)
                image = image.resize((new_width, new_height), PILImage.LANCZOS)
                logger.info(f"Page {i+1} resized to {new_width}x{new_height}")
            processed_images.append(image)
        
        images = processed_images  # Use the processed images
        
        total_pages = len(images)
        if progress_callback:
            progress_callback(f"Processing {total_pages} pages from {pdf_name}...")
        
        # Use current timestamp since we can't get creation time from uploaded file
        creation_date = datetime.now().strftime("%Y-%m-%d")
        
        # Process each page image with EasyOCR
        compression_settings = None  # Cache for optimal compression settings
        
        for page_num, image in enumerate(images, 1):
            try:
                if progress_callback:
                    progress_callback(f"OCR processing page {page_num}/{total_pages} of {pdf_name}...")
                
                # Convert PIL image to numpy array for EasyOCR
                img_array = np.array(image)
                
                # Perform OCR
                ocr_results = reader.readtext(img_array)
                
                if progress_callback:
                    progress_callback(f"Creating searchable PDF for page {page_num}/{total_pages} of {pdf_name}...")
                
                # Create searchable PDF with OCR text
                output_uuid = uuid.uuid4()
                output_pdf_name = f"{creation_date}-{output_uuid}.pdf"
                output_pdf_path = os.path.join(temp_dir, output_pdf_name)
                
                # Create PDF with cached compression settings for pages after the first
                if page_num == 1:
                    # First page: find optimal compression and cache it
                    create_searchable_pdf(image, ocr_results, output_pdf_path, max_size_mb=max_output_size_mb)
                    # Extract compression settings from the first page processing
                    compression_settings = getattr(create_searchable_pdf, '_last_compression_settings', None)
                else:
                    # Subsequent pages: use cached compression settings
                    create_searchable_pdf_with_settings(image, ocr_results, output_pdf_path, max_size_mb=max_output_size_mb, compression_settings=compression_settings)
                
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
                
                if progress_callback:
                    progress_callback(f"Completed page {page_num}/{total_pages} of {pdf_name}")
                
            except Exception as e:
                logger.warning(f"Failed to process page {page_num} of {pdf_name}: {e}")
                if progress_callback:
                    progress_callback(f"Error on page {page_num}/{total_pages} of {pdf_name}: {str(e)}")
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
            max_value=19,
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
            
            # Enhanced progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            detail_text = st.empty()
            
            # Calculate total pages for more accurate progress
            total_files = len(uploaded_files)
            total_pages = 0
            file_page_counts = {}
            
            # First pass: count pages in each PDF for accurate progress
            status_text.text("Analyzing uploaded files...")
            for uploaded_file in uploaded_files:
                try:
                    uploaded_file.seek(0)
                    pdf_reader = PdfReader(uploaded_file)
                    page_count = len(pdf_reader.pages)
                    file_page_counts[uploaded_file.name] = page_count
                    total_pages += page_count
                    uploaded_file.seek(0)  # Reset for processing
                except Exception as e:
                    file_page_counts[uploaded_file.name] = 1  # Assume 1 page if can't read
                    total_pages += 1
            
            processed_pages = 0
            
            def update_progress(message):
                """Callback function to update progress display"""
                nonlocal processed_pages
                detail_text.text(message)
                
                # Increment page counter for certain operations
                if "Completed page" in message:
                    processed_pages += 1
                    progress = min(processed_pages / total_pages, 1.0)
                    progress_bar.progress(progress)
                    status_text.text(f"Progress: {processed_pages}/{total_pages} pages processed ({progress*100:.1f}%)")
            
            status_text.text(f"Processing {total_files} files ({total_pages} total pages)...")
            
            for i, uploaded_file in enumerate(uploaded_files):
                file_pages = file_page_counts.get(uploaded_file.name, 1)
                update_progress(f"Starting {uploaded_file.name} ({file_pages} pages)...")
                
                processed_pdfs, error = process_single_pdf(
                    uploaded_file, 
                    uploaded_file.name, 
                    max_output_size_mb=max_output_size,
                    progress_callback=update_progress
                )
                
                if error:
                    st.error(f"Error processing {uploaded_file.name}: {error}")
                    detail_text.text(f"❌ Failed: {uploaded_file.name}")
                else:
                    st.session_state.processed_results.extend(processed_pdfs)
                    st.success(f"✅ Successfully processed {uploaded_file.name} - Created {len(processed_pdfs)} searchable PDF(s)")
                    detail_text.text(f"✅ Completed: {uploaded_file.name}")
            
            # Final progress update
            progress_bar.progress(1.0)
            status_text.text(f"🎉 Processing complete! Created {len(st.session_state.processed_results)} searchable PDFs")
            detail_text.text("All files processed successfully!")
    
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
