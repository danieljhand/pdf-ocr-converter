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
- **pdftoppm**: Converts PDF pages to PNG images (part of poppler-utils)
- **tesseract**: Performs OCR on images to create searchable PDFs

### Python Libraries
- `os`: File system operations
- `subprocess`: Execute external commands
- `uuid`: Generate unique identifiers
- `datetime`: Handle timestamps
- `shutil`: File operations (cleanup)
- `streamlit`: Web application framework for the user interface

## Functionality

### Main Function: `process_pdfs(input_directory)`
Processes all PDF files in the specified directory through the following workflow:

1. **File Discovery**: Scans input directory for PDF files (case-insensitive `.pdf` extension)

2. **Timestamp Extraction**: Gets creation timestamp from original PDF file

3. **Image Conversion**: 
   - Creates temporary directory for each PDF
   - Uses `pdftoppm` to convert PDF pages to PNG images
   - Output format: `page-1.png`, `page-2.png`, etc.

4. **OCR Processing**:
   - Processes each PNG image with `tesseract`
   - Language: English (`-l eng`)
   - Output format: Searchable PDF

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
- Original PDF files are not modified

## Technical Constraints
- **File Size Limit**: 50MB per PDF file
- **Supported Formats**: PDF files only (validated before processing)
- **Memory Usage**: Processes files individually to manage memory
- **Concurrent Processing**: Single-threaded processing to avoid resource conflicts
- **Temporary Storage**: Uses system temp directory with automatic cleanup

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
4. Click "Process PDFs" to start OCR processing
5. Download the processed searchable PDFs individually when complete

## Technical Notes
- Streamlit session state manages uploaded files and processing results
- Temporary files are stored in system temp directory during processing
- Download functionality uses Streamlit's download_button component
- Temporary directories use format: `temp_[original_filename_without_extension]`
- Each PDF page generates a separate searchable PDF (current implementation)
- OCR language can be modified by changing the `-l eng` parameter
- Requires system PATH access to external tools

## Limitations
- Creates separate searchable PDF for each page (by design for better OCR accuracy)
- English OCR only (configurable via tesseract language parameter)
- Requires system installation of external tools
- File size limited to 50MB per PDF
- No batch processing optimization for very large files
- Processing time scales linearly with number of pages
