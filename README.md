# PDF OCR Processing Application

A Streamlit-based web application that converts non-searchable PDF files into searchable PDFs using Optical Character Recognition (OCR) powered by EasyOCR.

## Features

- 🔍 **OCR Processing**: Convert non-searchable PDFs to searchable PDFs with invisible text overlay
- 🚀 **GPU Acceleration**: Automatic GPU detection and acceleration when available
- 📁 **Batch Processing**: Upload and process multiple PDF files simultaneously
- 📏 **Size Control**: Configurable output PDF size limits (1-19MB) with automatic compression
- 📊 **Enhanced Progress Tracking**: Real-time page-level progress updates with detailed status messages
- 💾 **Flexible Downloads**: Download individual files or all files as a ZIP archive
- 🌐 **Web Interface**: User-friendly Streamlit web interface
- 🧹 **Auto Cleanup**: Automatic temporary file cleanup

## Quick Start

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd pdf-ocr-processing
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
streamlit run app.py
```

4. Open your browser to `http://localhost:8501`

## Usage

1. **Upload PDFs**: Select one or more PDF files (max 50MB each)
2. **Configure Settings**: Adjust maximum output PDF size (1-19MB, default 10MB centered on slider)
3. **Process**: Click "Process PDFs" to start OCR processing
4. **Download**: Download individual searchable PDFs or all files as ZIP

## Technical Specifications

### Input Requirements
- **File Format**: PDF files only
- **File Size**: Maximum 50MB per file
- **Content**: Any PDF (scanned documents, images, mixed content)

### Output Features
- **Format**: Searchable PDF with invisible OCR text overlay
- **Naming**: `YYYY-MM-DD-[UUID].pdf` format
- **Size Control**: Configurable compression (1-19MB limit, centered slider design)
- **Quality**: 300 DPI processing for optimal OCR accuracy
- **Progress Tracking**: Real-time page-level progress with detailed status updates

### Performance
- **OCR Engine**: EasyOCR with English language support
- **GPU Support**: Automatic CUDA detection and acceleration
- **CPU Fallback**: Graceful fallback when GPU unavailable
- **Confidence Filtering**: Only includes OCR text with >50% confidence

### Progress Tracking
- **Page-Level Updates**: Shows progress for individual pages within multi-page PDFs
- **Real-Time Status**: Detailed messages for each processing step
- **Accurate Progress Bar**: Pre-scans files to calculate total pages for precise completion percentage
- **Visual Feedback**: Success/error indicators with emojis (✅/❌)
- **Status Messages**: 
  - "Initializing OCR for [filename]..."
  - "Converting [filename] to images..."
  - "OCR processing page X/Y of [filename]..."
  - "Creating searchable PDF for page X/Y of [filename]..."
  - "Completed page X/Y of [filename]"

## Dependencies

### Core Libraries
- `streamlit` - Web application framework
- `easyocr` - OCR processing engine
- `pdf2image` - PDF to image conversion
- `reportlab` - PDF generation
- `PyPDF2` - PDF validation and reading
- `pillow` - Image processing
- `numpy` - Array operations
- `torch` - PyTorch for GPU acceleration (optional)

### System Requirements
- **Memory**: 4GB+ RAM recommended for large PDFs
- **GPU**: CUDA-compatible GPU optional (for acceleration)
- **Storage**: Temporary space for processing (auto-cleaned)

## Configuration

### Output PDF Size Control
The application automatically compresses output PDFs to stay within the specified size limit:

- **Slider Range**: 1-19MB with 10MB default positioned at center for intuitive control
- **Image Resizing**: Reduces resolution when images exceed 1200px
- **JPEG Compression**: Applies 85% quality JPEG compression (70% for aggressive compression)
- **Format Optimization**: Converts RGBA to RGB for better compression
- **OCR Preservation**: Maintains text overlay accuracy through coordinate scaling
- **Progressive Compression**: Applies moderate compression first, then more aggressive if needed

### GPU Acceleration
- **Automatic Detection**: Detects CUDA-capable GPUs automatically
- **Fallback**: Uses CPU processing when GPU unavailable
- **Performance**: 3-5x faster processing with GPU acceleration

## Error Handling

The application handles common issues gracefully:

- **Invalid PDFs**: Validates file format before processing
- **Size Limits**: Enforces file size restrictions
- **Memory Issues**: Processes files individually to manage memory
- **Partial Failures**: Individual file errors don't stop batch processing
- **Resource Cleanup**: Ensures temporary files are always cleaned up

## Troubleshooting

### Common Issues

**"Missing required Python libraries" error:**
```bash
pip install easyocr pdf2image reportlab PyPDF2 pillow numpy
```

**GPU not detected:**
- Install PyTorch with CUDA support:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

**Large file processing slow:**
- Reduce output PDF size limit for faster processing
- Use GPU acceleration if available
- Process fewer files simultaneously

**OCR accuracy issues:**
- Ensure input PDFs have good image quality
- Check that text is clearly visible in original PDF
- Consider preprocessing images for better contrast

### Performance Tips

1. **Use GPU acceleration** for 3-5x faster processing
2. **Reduce output size limit** for faster compression
3. **Process smaller batches** to avoid memory issues
4. **Ensure good input quality** for better OCR results

### Progress and Performance Issues

**Progress bar not updating smoothly:**
- Large PDFs may show longer pauses between updates
- Each page processes individually for accurate tracking
- GPU acceleration significantly improves processing speed

**Processing seems slow:**
- Check if GPU acceleration is being used (shown in UI)
- Reduce output PDF size limit for faster compression
- Consider processing fewer files simultaneously

**Progress percentage jumps:**
- Normal behavior when files have different page counts
- Progress is calculated based on total pages across all files
- Individual file completion may cause larger jumps

## File Structure

```
pdf-ocr-processing/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── docs/
│   └── specification.md   # Detailed technical specification
└── README.md             # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or contributions:
- Check the [specification document](docs/specification.md) for technical details
- Review common troubleshooting steps above
- Open an issue for bugs or feature requests

## Changelog

### Current Version
- EasyOCR integration with GPU acceleration
- Configurable output PDF size limits
- Automatic image compression and optimization
- Batch processing with individual file downloads
- ZIP archive download for multiple files
- Comprehensive error handling and validation
