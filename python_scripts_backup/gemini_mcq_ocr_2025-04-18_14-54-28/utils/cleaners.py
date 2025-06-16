# utils/cleaners.py

import unicodedata
import re
from typing import Any # To hint that it might return original type if not string

def clean_excel_string(text: Any) -> Any:
    """
    Cleans a string for safe insertion into an Excel cell using openpyxl.
    Removes control characters and LaTeX math delimiters.

    Args:
        text: The input text (can be any type, but only processes strings).

    Returns:
        The cleaned string, or the original input if it wasn't a string.
    """
    if not isinstance(text, str):
        return text

    try:
        # 1. Fix corrupted LaTeX like 'rac' back to '\frac'
        text = text.replace('\x0c', '').replace('\f', '')  # Remove form feeds explicitly
        text = re.sub(r'\b([fF])rac', r'\\\1rac', text)     # Fix: frac → \frac

        # 2. Remove unsafe control characters
        cleaned_text = "".join(
            ch for ch in text
            if unicodedata.category(ch)[0] != "C" or ch in ('\t', '\n', '\r')
        )

        # 3. Remove remaining XML-unsafe chars
        cleaned_text = cleaned_text.replace('\x0b', '').replace('\x00', '')

        # 4. Remove LaTeX delimiters \( ... \) but preserve content
        cleaned_text = re.sub(r'\\\((.*?)\\\)', r'\1', cleaned_text)

        return cleaned_text

    except Exception as e:
        print(f"Warning: Error cleaning string for Excel: {e}. Returning original problematic text.")
        return text

def clean_docx_string(text: Any) -> Any:
    """
    Cleans a string for safe insertion into a DOCX document using python-docx.
    Removes control characters (except Tab, Newline, CR) and LaTeX inline math delimiters.

    Args:
        text: The input text (can be any type, but only processes strings).

    Returns:
        The cleaned string, or the original input if it wasn't a string.
    """
    if not isinstance(text, str):
        # If input is not a string, return it as is.
        return text

    try:
        # 1. Remove most control characters (Category C) except common whitespace.
        cleaned_text = "".join(
            ch for ch in text
            if unicodedata.category(ch)[0] != "C" or ch in ('\t', '\n', '\r')
        )

        # 2. Specifically remove vertical tab, form feed, etc.
        cleaned_text = cleaned_text.replace('\x0b', '').replace('\x0c', '')
        cleaned_text = cleaned_text.replace('\x00', '') # Explicitly remove null bytes


        # 3. Remove LaTeX \( ... \) inline math delimiters for DOCX output.
        cleaned_text = re.sub(r'\\\((.*?)\\\)', r'\1', cleaned_text)

        # 4. Ensure text is valid XML content (python-docx uses XML internally)
        # This is a basic check; a more robust XML sanitizer might be needed for complex cases.
        # Replace characters invalid in XML text nodes if necessary (though python-docx might handle some).
        # For example, low ASCII control chars not caught by unicodedata check.
        # cleaned_text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', cleaned_text) # Remove more control chars

        return cleaned_text

    except Exception as e:
        print(f"Warning: Error cleaning string for DOCX: {e}. Returning original problematic text.")
        return text

# --- End of cleaners.py ---