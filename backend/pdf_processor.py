import io
from pypdf import PdfReader

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Takes PDF file bytes and returns the extracted text as a string.
    """
    try:
        # Create a file-like object from the bytes
        pdf_file = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_file)
        
        extracted_text = ""
        # Loop through all the pages and extract text
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"
                
        return extracted_text.strip()
    except Exception as e:
        raise Exception(f"Error reading PDF: {str(e)}")