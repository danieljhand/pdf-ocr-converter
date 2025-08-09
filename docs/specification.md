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
- Directory path containing PDF files
- PDF files with any naming convention

### Output
- Searchable PDF files in the same directory
- Naming format: `YYYY-MM-DD-[UUID].pdf`
- Original PDF files remain unchanged

## Error Handling
- **FileNotFoundError**: Missing external tools (pdftoppm, tesseract)
- **subprocess.CalledProcessError**: Command execution failures
- **General Exception**: Catches unexpected errors
- All errors are logged with descriptive messages

## Usage
1. Run the application: `python app.py`
2. Enter the directory path containing PDF files when prompted
3. Application processes all PDFs automatically
4. Completion message displayed when finished

## Technical Notes
- Temporary directories use format: `temp_[original_filename_without_extension]`
- Each PDF page generates a separate searchable PDF (current implementation)
- OCR language can be modified by changing the `-l eng` parameter
- Requires system PATH access to external tools

## Limitations
- Currently creates one searchable PDF per page rather than combining pages
- Limited to English OCR (configurable)
- Requires external tool installation
- No batch size limits or memory management for large files
