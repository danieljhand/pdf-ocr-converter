import os
import uuid
from datetime import date
from PyPDF2 import PdfReader, PdfWriter

def split_and_rename_pdfs(directory):
    """
    Parses all PDF files in a directory. For each page in a PDF, it creates
    a separate single-page PDF document with a filename in the format
    "YYYY-MM-DD-UUID.pdf" in the same directory.

    Args:
        directory (str): The path to the directory containing the PDF files.
    """
    today_date_str = date.today().strftime("%Y-%m-%d")
    for filename in os.listdir(directory):
        if filename.lower().endswith(".pdf"):
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, 'rb') as pdf_file:
                    pdf_reader = PdfReader(pdf_file)
                    num_pages = len(pdf_reader.pages)

                    print(f"Processing PDF: {filename} ({num_pages} pages)")
                    for page_num in range(num_pages):
                        pdf_writer = PdfWriter()
                        pdf_writer.add_page(pdf_reader.pages[page_num])
                        unique_id = uuid.uuid4()
                        output_filename = os.path.join(directory, f"{today_date_str}-{unique_id}.pdf")
                        with open(output_filename, 'wb') as output_pdf:
                            pdf_writer.write(output_pdf)
                        print(f"  Created {today_date_str}-{unique_id}.pdf (page {page_num + 1} of {filename})")

            except Exception as e:
                print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    target_directory = input("Enter the directory containing the PDF files: ")
    if os.path.isdir(target_directory):
        split_and_rename_pdfs(target_directory)
        print("PDF processing complete.")
    else:
        print("Invalid directory provided.")
