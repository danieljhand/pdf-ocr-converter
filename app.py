import os
from PyPDF2 import PdfReader, PdfWriter

def split_multi_page_pdfs(directory):
    """
    Parses all PDF files in a directory. For multi-page PDFs, it creates
    separate single-page PDF documents in the same directory.

    Args:
        directory (str): The path to the directory containing the PDF files.
    """
    for filename in os.listdir(directory):
        if filename.lower().endswith(".pdf"):
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, 'rb') as pdf_file:
                    pdf_reader = PdfReader(pdf_file)
                    num_pages = len(pdf_reader.pages)

                    if num_pages > 1:
                        print(f"Processing multi-page PDF: {filename} ({num_pages} pages)")
                        base_name, _ = os.path.splitext(filename)
                        for page_num in range(num_pages):
                            pdf_writer = PdfWriter()
                            pdf_writer.add_page(pdf_reader.pages[page_num])
                            output_filename = os.path.join(directory, f"{base_name}_page_{page_num + 1}.pdf")
                            with open(output_filename, 'wb') as output_pdf:
                                pdf_writer.write(output_pdf)
                        print(f"  Created {num_pages} single-page PDFs for {filename}")
                    elif num_pages == 1:
                        print(f"Skipping single-page PDF: {filename}")
                    else:
                        print(f"Warning: Could not read any pages in {filename}")
            except Exception as e:
                print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    target_directory = input("Enter the directory containing the PDF files: ")
    target_directory = "/Volumes/google_drive_sensitive/04 Archives/Scanned Documents to Sort" 
    if os.path.isdir(target_directory):
        split_multi_page_pdfs(target_directory)
        print("PDF processing complete.")
    else:
        print("Invalid directory provided.")
