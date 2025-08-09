# PDF OCR Processing Application Specification

## Overview
This application processes PDF files by converting them to searchable PDFs using Optical Character Recognition (OCR). It takes non-searchable PDF files and creates searchable versions with timestamped, UUID-based filenames.

## Purpose
- Convert PDF pages to images for OCR processing
- Apply OCR to create searchable PDF content
- Organize output files with standardized naming convention
- Clean up temporary files automatically

## Dependencies
### External Tools Required
- No external system tools required (pure Python implementation)

### Python Libraries
- `os`: File system operations
- `subprocess`: Execute external commands
- `uuid`: Generate unique identifiers
- `datetime`: Handle timestamps
- `shutil`: File operations (cleanup)
- `streamlit`: Web application framework for the user interface
- `easyocr`: OCR processing library
- `pdf2image`: Convert PDF pages to images
- `reportlab`: PDF generation and manipulation
- `PyPDF2`: PDF file validation and reading
- `pillow`: Image processing
- `numpy`: Array operations for image data

## Functionality

### Main Function: `process_pdfs(input_directory)`
Processes all PDF files in the specified directory through the following workflow:

1. **File Discovery**: Scans input directory for PDF files (case-insensitive `.pdf` extension)

2. **Timestamp Extraction**: Gets creation timestamp from original PDF file

3. **Image Conversion**: 
   - Creates temporary directory for each PDF
   - Uses `pdf2image` library to convert PDF pages to PIL Image objects
   - High resolution conversion (300 DPI) for better OCR accuracy

4. **OCR Processing**:
   - Processes each image with `EasyOCR` library
   - Language: English (`['en']`)
   - GPU acceleration when available, CPU fallback
   - Confidence threshold filtering (>0.5)
   - Output format: Searchable PDF with invisible text overlay

5. **File Naming**: 
   - Format: `YYYY-MM-DD-UUID.pdf`
   - Date based on original PDF creation time
   - UUID ensures uniqueness

6. **Cleanup**: Removes temporary image directories and files

## Input/Output

### Input
- PDF files uploaded through Streamlit web interface
- Multiple file upload supported
- PDF files with any naming convention

### Output
- Searchable PDF files available for download
- Naming format: `YYYY-MM-DD-[UUID].pdf`
- Individual download buttons for each processed file
- ZIP archive download for all processed files
- **File Size Control**: Output PDFs compressed to stay under user-specified size limit
- Original PDF files are not modified

## Technical Constraints
- **Input File Size Limit**: 50MB per uploaded PDF file
- **Output File Size Limit**: Configurable via UI slider (1-19MB range, default 10MB per output PDF)
- **Supported Formats**: PDF files only (validated before processing)
- **Memory Usage**: Processes files individually to manage memory
- **Concurrent Processing**: Single-threaded processing to avoid resource conflicts
- **Temporary Storage**: Uses system temp directory with automatic cleanup
- **GPU Acceleration**: Automatically detects and uses GPU when available for faster processing
- **OCR Confidence**: Only includes OCR text with confidence > 0.5 in searchable PDFs

## Configuration Options

### Output PDF Size Control
- **UI Control**: Slider in "Output Settings" section allows users to set maximum output PDF size
- **Range**: 1MB to 19MB per output PDF (centered design with 10MB default in middle position)
- **Default**: 10MB per output PDF (positioned at center of slider range)
- **Behavior**: PDFs exceeding the limit are compressed by:
  - Reducing image resolution (max 1200px dimension)
  - Applying JPEG compression (quality 85)
  - Converting RGBA images to RGB for better compression
  - Scaling OCR coordinates to match resized images

### Compression Strategy
- **Image Optimization**: Automatically resizes images if width or height exceeds 1200px
- **Format Conversion**: Uses JPEG compression instead of PNG for smaller file sizes
- **Quality Control**: JPEG quality set to 85 for good balance of size vs quality
- **OCR Preservation**: Maintains OCR text overlay accuracy by scaling coordinates proportionally

## User Interface Features

### Progress Tracking
The application provides detailed, real-time progress updates during PDF processing:

- **File Analysis**: Pre-scans uploaded PDFs to count total pages for accurate progress calculation
- **Page-Level Progress**: Shows progress for individual pages within multi-page PDFs
- **Progress Bar**: Visual progress bar with percentage completion based on total pages processed
- **Status Updates**: Real-time status messages showing current operation:
  - "Initializing OCR for [filename]..."
  - "Converting [filename] to images..."
  - "OCR processing page X/Y of [filename]..."
  - "Creating searchable PDF for page X/Y of [filename]..."
  - "Completed page X/Y of [filename]"
- **Error Reporting**: Individual page/file errors displayed without stopping batch processing
- **Completion Summary**: Final status showing total searchable PDFs created

### Progress Display Components
- **Overall Progress Bar**: Shows percentage completion across all files and pages
- **Status Text**: Current overall progress (e.g., "Progress: 15/23 pages processed (65.2%)")
- **Detail Text**: Specific operation being performed on current file/page
- **Success/Error Indicators**: Visual feedback with emojis (✅ for success, ❌ for errors)

### Output Settings Interface
- **Size Control Slider**: Horizontally centered slider with 10MB default value
- **Range Display**: Shows 1MB minimum to 19MB maximum with 1MB increments
- **Help Text**: Explains trade-off between file size and image quality
- **Real-time Feedback**: Shows selected size limit below slider

## Error Handling
- **Input Validation**: Validates uploaded files are proper PDFs before processing
- **File Size Limits**: Enforces maximum file size to prevent memory issues
- **External Tool Validation**: Checks for required tools before processing begins
- **Graceful Degradation**: Individual file failures don't stop batch processing
- **Resource Management**: Ensures temporary files are cleaned up even on errors
- **User Feedback**: Provides clear, actionable error messages
- **Logging**: Comprehensive logging for debugging and monitoring

### Common Error Scenarios
- Invalid or corrupted PDF files
- Missing external dependencies (pdftoppm, tesseract)
- Insufficient system resources or memory
- Network interruptions during upload
- Partial processing failures

## Usage
1. Run the Streamlit application: `streamlit run app.py`
2. Open the web interface in your browser (typically http://localhost:8501)
3. Upload one or more PDF files using the file uploader
4. Configure maximum output PDF size using the slider (1-19MB, default 10MB centered)
5. Click "Process PDFs" to start OCR processing
6. Download the processed searchable PDFs individually or as a ZIP archive when complete

## Technical Notes
- Streamlit session state manages uploaded files and processing results
- Temporary files are stored in system temp directory during processing
- Download functionality uses Streamlit's download_button component
- Temporary directories use format: `temp_[original_filename_without_extension]`
- Each PDF page generates a separate searchable PDF (current implementation)
- OCR language can be modified by changing the `['en']` parameter in EasyOCR Reader initialization
- GPU acceleration automatically detected and used when PyTorch with CUDA is available
- OCR text overlay is invisible but searchable, preserving original document appearance
- Requires system PATH access to external tools
- Output PDF size is controlled through image compression and resizing while preserving OCR accuracy

## Performance Optimization
- **GPU Detection**: Automatically detects CUDA-capable GPUs for accelerated OCR processing
- **CPU Fallback**: Gracefully falls back to CPU processing when GPU is unavailable
- **Memory Management**: Processes images in-memory without temporary image files
- **Confidence Filtering**: Only includes high-confidence OCR results (>50%) in searchable text
- **Image Quality**: Uses 300 DPI conversion for optimal OCR accuracy

## Limitations
- Creates separate searchable PDF for each page (by design for better OCR accuracy)
- English OCR only (configurable via tesseract language parameter)
- Requires system installation of external tools
- Input file size limited to 50MB per uploaded PDF
- Output file size configurable (1-50MB) with automatic compression applied
- No batch processing optimization for very large files
- Processing time scales linearly with number of pages
