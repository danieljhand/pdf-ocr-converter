import os
import subprocess
import uuid
from datetime import datetime
import shutil  # For moving files

def process_pdfs(input_directory):
    """
    Processes all PDF files in the input directory:
    1. Converts each page to a PNG image using pdftoppm.
    2. Performs OCR on each PNG using tesseract to create a searchable PDF.
    3. Renames the searchable PDF to "YYYY-MM-DD-UUID.pdf" based on the
       original PDF's creation time.
    4. Cleans up the intermediate PNG image files.
    """
    for filename in os.listdir(input_directory):
        if filename.lower().endswith(".pdf"):
            input_pdf_path = os.path.join(input_directory, filename)

            try:
                # Get the creation timestamp of the original PDF
                creation_timestamp = os.path.getctime(input_pdf_path)
                creation_date = datetime.fromtimestamp(creation_timestamp).strftime("%Y-%m-%d")

                print(f"Processing PDF: {filename}")

                # Create a temporary directory for the PNG images
                temp_image_dir = os.path.join(input_directory, f"temp_{os.path.splitext(filename)[0]}")
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
                for png_file in os.listdir(temp_image_dir):
                    if png_file.lower().endswith(".png"):
                        png_path = os.path.join(temp_image_dir, png_file)
                        output_uuid = uuid.uuid4()
                        output_pdf_name = f"{creation_date}-{output_uuid}.pdf"
                        output_pdf_path = os.path.join(input_directory, output_pdf_name)

                        tesseract_command = [
                            "tesseract",
                            png_path,
                            os.path.splitext(output_pdf_path)[0],  # Output base name (without .pdf)
                            "-l", "eng",  # You can change the language if needed
                            "pdf"
                        ]
                        subprocess.run(tesseract_command, check=True, capture_output=True)
                        print(f"  Created searchable PDF: {output_pdf_name}")

                # Clean up the temporary image directory
                shutil.rmtree(temp_image_dir)

            except FileNotFoundError as e:
                print(f"Error: {e}. Make sure 'pdftoppm' and 'tesseract' are installed and in your system's PATH.")
            except subprocess.CalledProcessError as e:
                print(f"Error processing {filename}: {e.stderr.decode()}")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    target_directory = input("Enter the directory containing the PDF files: ")
    if os.path.isdir(target_directory):
        process_pdfs(target_directory)
        print("PDF processing complete.")
    else:
        print("Invalid directory provided.")
