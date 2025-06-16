# utils/ocr_processor.py

import fitz  # PyMuPDF
from PIL import Image
import google.generativeai as genai
import google.api_core.exceptions
import os
import io
import traceback
import json # For validation
import re # For backslash escaping and page number extraction
import time # For retry delays
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional # For type hinting

# --- Environment Variable Loading ---
try:
    load_dotenv()
    print("✅ .env file loaded successfully.")
except Exception as e:
    print(f"⚠️ Warning: Could not load .env file. Error: {e}")

# --- Gemini API Configuration ---
api_key = os.getenv("GEMINI_API_KEY")
gemini_api_key_valid = False # Flag to track API key status

# Use models specified by user in the last code block provided
SUPPORTED_GEMINI_MODELS = ['gemini-2.0-flash', 'gemini-2.0'] # User specified models
default_gemini_model_name = 'gemini-2.0-flash' # User specified default

if not api_key:
    print("\n❌❌❌ WARNING: GEMINI_API_KEY environment variable not found. Gemini features disabled. ❌❌❌\n")
else:
    try:
        print("⚙️ Configuring Google Generative AI...")
        genai.configure(api_key=api_key)
        # Test configuration
        try:
            # Try getting the default model to check key validity
            genai.get_model(f'models/{default_gemini_model_name}')
            print(f"✅ Gemini API Key seems valid. Default model '{default_gemini_model_name}' accessible.")
            gemini_api_key_valid = True
        except Exception as test_e:
             print(f"❌ ERROR: Gemini API Key found but failed configuration/test with default model '{default_gemini_model_name}'. Error: {test_e}")
             print("   Gemini features might be unavailable.")
             gemini_api_key_valid = False

    except Exception as e:
        print(f"❌ FATAL ERROR: General Gemini config failed: {e}"); traceback.print_exc(); gemini_api_key_valid = False

# --- Supported Models Dictionary (Exportable) ---
SUPPORTED_MODELS = {
    "gemini": SUPPORTED_GEMINI_MODELS if gemini_api_key_valid else [],
    "openai": [], # Placeholder
    "ollama": []  # Placeholder
}

def get_gemini_api_key_state() -> bool:
    """Returns True if the Gemini API key was found and tested okay."""
    return gemini_api_key_valid

# --- Language Mapping ---
LANGUAGE_MAP = { "English": "English", "Hindi": "Hindi", "Marathi": "Marathi", "Bengali": "Bengali", "Tamil": "Tamil", "Telugu": "Telugu", "Gujarati": "Gujarati", "Punjabi": "Punjabi" }

# --- PDF Processing Function (Unchanged) ---
def pdf_to_images(pdf_path, output_folder):
    image_paths = []
    print(f"🔄 [pdf_to_images] Converting: {pdf_path}")
    try:
        os.makedirs(output_folder, exist_ok=True)
        doc = fitz.open(pdf_path); num_pages = len(doc)
        print(f"   📄 [pdf_to_images] Pages: {num_pages}")
        # Increased DPI/Zoom for potentially better OCR quality
        zoom_x = 3.0; zoom_y = 3.0; mat = fitz.Matrix(zoom_x, zoom_y)
        for page_num in range(num_pages):
            page_index = page_num + 1
            page = doc.load_page(page_num); pix = page.get_pixmap(matrix=mat, alpha=False)
            img_filename = f"page_{page_index}.png"; img_path = os.path.join(output_folder, img_filename)
            # Save with higher quality if needed (though PNG is lossless)
            pix.save(img_path); image_paths.append(img_path)
        doc.close(); print(f"✅ [pdf_to_images] Generated {len(image_paths)} images.")
        if len(image_paths) != num_pages: print(f"   ⚠️ WARNING: Expected {num_pages}, generated {len(image_paths)} images!")
        return image_paths
    except fitz.fitz.FileNotFoundError: print(f"❌ [pdf_to_images] Error: File not found: {pdf_path}."); return []
    except Exception as e: print(f"❌ [pdf_to_images] Error during conversion: {e}"); traceback.print_exc(); return []

# --- Helper Function to Load Images (Unchanged) ---
def _load_images_for_prompt(image_inputs: List[Any]) -> Optional[List[Image.Image]]:
    loaded_images = []; print(f"   🖼️ Loading {len(image_inputs)} image input(s)...")
    all_loaded = True
    for i, img_input in enumerate(image_inputs):
        img = None
        try:
            if isinstance(img_input, str): # Path string
                if not os.path.exists(img_input): raise FileNotFoundError(f"Img path not found: {img_input}")
                img = Image.open(img_input)
            elif isinstance(img_input, bytes): # Raw bytes
                img = Image.open(io.BytesIO(img_input))
            elif isinstance(img_input, Image.Image): # Already a PIL Image
                img = img_input
            else: raise TypeError("Invalid image input type.")
            if img: loaded_images.append(img)
            else: raise ValueError("Image object is None after processing.")
        except Exception as img_e:
            print(f"   ❌ Error loading image input #{i+1}. Input type: {type(img_input)}. Error: {img_e}")
            all_loaded=False; break
    if all_loaded: print(f"      Successfully loaded all {len(loaded_images)} images.")
    return loaded_images if all_loaded else None

# --- Modified Helper: Build Common Prompt Parts (Includes chunk context hint) ---
def _build_common_prompt_parts(
    num_images_in_chunk: int,
    chunk_page_numbers: List[int],
    language: str,
    generate_explanation: bool,
    generate_answer: bool,
    custom_prompt: Optional[str] = None
) -> List[str]:
    """
    Builds the prompt list for a single chunk, specifying exact output formats.
    """
    lang_hint = LANGUAGE_MAP.get(language, language)
    page_num_str = ", ".join(map(str, sorted(chunk_page_numbers)))

    # --- Define Answer/Explanation/Source Instructions based on Flags ---
    answer_instruction = ""
    if generate_answer:
        # Priority: Extract if explicitly marked, otherwise generate *LABEL*.
        answer_instruction = f"""*   **Answer Field:**
        1.  Check for explicitly marked answer option (e.g., 'a', 'b', 'c', 'd', 'e') on pages {page_num_str}.
        2.  If found, populate `answer` field with ONLY the uppercase option label (e.g., "A", "B", "C", "D", "E").
        3.  If not found, THEN analyze question/options to determine the most likely correct option label and populate `answer` with the uppercase label.
        4.  If unsure, return `null`."""
    else:
        # Only extract *LABEL* if explicitly marked.
        answer_instruction = f"*   **Answer Field:** Extract the correct answer option label ONLY IF explicitly marked on pages {page_num_str}. Return ONLY the uppercase label (e.g., \"A\", \"B\", \"C\", \"D\", \"E\"). Otherwise, return `null`."

    explanation_instruction = ""
    if generate_explanation:
        # Priority: Extract/Summarize if present, otherwise generate.
        explanation_instruction = f"""*   **Explanation Field:**
        1.  Check for existing explanation for the question on pages {page_num_str}.
        2.  If found, extract/summarize it IN {lang_hint} and populate `explanation`.
        3.  If not found, THEN generate a concise explanation IN {lang_hint}.
        4.  If unable to do either, return `null`."""
    else:
        # Do not generate.
        explanation_instruction = f"*   **Explanation Field:** Return `null`. Do not generate explanations."

    # --- Source Info Instruction ---
    source_info_instruction = f"*   **Source Info Field:** Extract any source information (like exam name, year) associated with the question on pages {page_num_str}. If no source info is found, return an **empty string \"\"**."

    # --- Define field descriptions for JSON structure ---
    answer_field_desc = '"answer": "str (A, B, C...) | null" // Uppercase label or null.'
    explanation_field_desc = '"explanation": "str | null" // Explanation text or null.'
    source_info_field_desc = '"source_info": "str" // Source text or empty string "".' # Changed to empty string

    # --- Start building the prompt parts list ---
    prompt_parts = [
        f"You are processing {num_images_in_chunk} image(s) corresponding to original document pages: **{page_num_str}**. Ensure JSON keys use these exact page numbers.",
        f"Your primary task is OCR on THESE {num_images_in_chunk} images, structuring content into a SINGLE JSON object for pages {page_num_str} ONLY.\nPrimary language for ALL text output MUST be: **{lang_hint}**.",
        f"""
REQUIRED JSON structure (ONLY keys for pages {page_num_str}):
{{
  "page_{min(chunk_page_numbers)}_MCQs": [ {{ "question_number": "str", "question_text": "str", "options": ["str", ...], {answer_field_desc}, {explanation_field_desc}, {source_info_field_desc} }}, ... ],
  // ... include keys ONLY for pages {page_num_str} ...
  "page_{max(chunk_page_numbers)}_MCQs": [ {{ ... }} ],
  "header_footer_info": {{ "page_{min(chunk_page_numbers)}_header": "str|null", ..., "page_{max(chunk_page_numbers)}_footer": "str|null" }} // Keys ONLY for pages {page_num_str}
}}

CRITICAL INSTRUCTIONS (Apply FIRST to content from pages {page_num_str}):
*   Identify: `question_number`, `question_text`, `options`.
{answer_instruction}
{explanation_instruction}
{source_info_instruction}
*   Group MCQs by Page under `"page_N_MCQs"` key (use original page numbers: {page_num_str}). Maintain order.
*   Extract `header_footer_info` accurately for pages {page_num_str} IN {lang_hint}.
*   **VERY IMPORTANT:** Adhere strictly to the primary language: **{lang_hint}**.
*   Output ONLY the single, valid JSON object for pages {page_num_str}. Ensure correct JSON syntax/escaping.
"""
    ]

    # --- Append Custom Prompt if provided ---
    if custom_prompt:
        prompt_parts.append(f"\n--- Additional User Instructions (Apply to pages {page_num_str} - May override previous instructions) ---")
        prompt_parts.append(custom_prompt)
        prompt_parts.append("--- End of User Instructions ---")
        print(f"    HINT: Appending custom user prompt for chunk (Pages {page_num_str}).")

    # Add final formatting instructions (Math/Plain) - These should be appended AFTER custom prompt
    # The calling functions (call_gemini_ocr_math/plain) will append these

    return prompt_parts

# --- Helper: Safely Parse Gemini JSON (Unchanged) ---
def safely_parse_gemini_json(raw_response: str) -> Optional[Dict[str, Any]]:
    """
    Cleans and attempts to parse JSON string from Gemini,
    escaping potentially problematic single backslashes.
    Returns parsed dictionary or None on failure.
    """
    if not raw_response or not isinstance(raw_response, str):
        print("      ❌ [safe_parse] Input is not a valid string.")
        return None

    # print("       S [safe_parse] Attempting to clean and parse JSON...") # Verbose
    # 1. Remove code block markers
    text_to_parse = raw_response.strip()
    if text_to_parse.startswith("```json"):
        text_to_parse = text_to_parse[7:]
    elif text_to_parse.startswith("```"): # Handle case where ```json is missing but ``` is present
        text_to_parse = text_to_parse[3:]
    if text_to_parse.endswith("```"):
        text_to_parse = text_to_parse[:-3]
    text_to_parse = text_to_parse.strip()

    if not text_to_parse:
        print("      ❌ [safe_parse] Response empty after cleaning markers.")
        return None

    # 2. Escape single backslashes (Crucial for LaTeX)
    try:
        # This regex is crucial for handling LaTeX correctly before JSON parsing.
        escaped_text = re.sub(r'(?<!\\)\\(?![\\/"bfnrtu])', r'\\\\', text_to_parse)
        if escaped_text != text_to_parse: print("      🛠️ [safe_parse] Applied backslash escaping.") # Verbose
        else: print("       [safe_parse] No problematic backslashes found to escape.") # Verbose

        # 3. Attempt to parse
        parsed_data = json.loads(escaped_text)
        print("      ✅ [safe_parse] JSON parsed successfully!")
        return parsed_data

    except json.JSONDecodeError as json_err:
        print(f"      ❌❌❌ [safe_parse] JSON Decode Error: {json_err}")
        err_pos = json_err.pos
        context_win = 60 # Increase context window slightly
        start_ctx = max(0, err_pos - context_win)
        end_ctx = min(len(escaped_text), err_pos + context_win)
        print(f"         Context around char {err_pos}: '{escaped_text[start_ctx:err_pos]} <ERROR> {escaped_text[err_pos:end_ctx]}'")
        # Also log original text context if escaping happened
        if escaped_text != text_to_parse:
             start_ctx_orig = max(0, err_pos - context_win) # Recalculate for original length mapping (approximate)
             end_ctx_orig = min(len(text_to_parse), err_pos + context_win)
             print(f"         Original Text Context: '{text_to_parse[start_ctx_orig:err_pos]} <ERROR> {text_to_parse[err_pos:end_ctx_orig]}'")
        return None
    except Exception as e:
        print(f"      ❌❌❌ [safe_parse] Unexpected error during parsing/escaping: {e}")
        traceback.print_exc()
        return None

# --- Helper: Call Gemini API for a single request (Unchanged Core Logic) ---
def _call_gemini_and_get_json(
    model_name: str,
    prompt_parts: List[Any],
    image_inputs: List[Any] # Should be PIL Images here
) -> Optional[Dict[str, Any]]:
    """
    Internal function makes API call using specified model with explicit safety settings,
    gets response, uses safe parser.
    """
    global gemini_api_key_valid # Access the global flag
    if not gemini_api_key_valid:
        print("❌ Error: Cannot call Gemini, API key is invalid or not configured.")
        return None
    if not image_inputs:
         print("❌ Error: _call_gemini_and_get_json called with no image inputs.")
         return None

    # --- Dynamic Model Initialization with EXPLICIT Safety Settings ---
    try:
        # Define explicit safety settings known to be generally supported
        # Exclude potentially problematic ones like CIVIC_INTEGRITY if needed
        explicit_safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            # Consider commenting out CIVIC_INTEGRITY if the error persists
            # {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"},
        ]
        print(f"   ⚙️ Initializing Gemini Model: models/{model_name} with explicit safety settings.")

        # Set generation config (optional)
        # generation_config = genai.types.GenerationConfig(...)

        gemini_model = genai.GenerativeModel(
            model_name=f'models/{model_name}',
            safety_settings=explicit_safety_settings # <<< USE THE EXPLICIT LIST
            # generation_config=generation_config
        )
        print(f"   ✅ Model 'models/{model_name}' initialized for this call.")
    except Exception as model_init_err:
        print(f"❌ Error initializing Gemini model '{model_name}': {model_init_err}")
        # If model init fails, maybe API key / model name is wrong
        # Consider setting gemini_api_key_valid = False here if appropriate
        return None

    # API Call
    request_content = prompt_parts + image_inputs
    print(f"   📡 Sending request to Gemini (Model: {model_name}, Images: {len(image_inputs)})...")
    try:
        response = gemini_model.generate_content(request_content, stream=False)
        print("   ✔️ Received response from Gemini.")
    except google.api_core.exceptions.ResourceExhausted as res_ex:
         print(f"❌ Gemini API call failed: Resource Exhausted (Quota?). {res_ex}")
         return None
    # Catch InvalidArgument specifically, often related to request structure/content
    except google.api_core.exceptions.InvalidArgument as inv_arg:
         print(f"❌ Gemini API call failed: Invalid Argument. Check prompt/images/safety settings. {inv_arg}")
         # Log parts of the prompt for debugging (be careful with sensitive data)
         # print(f"   DEBUG: Prompt Parts (text only, first 200 chars): {[str(p)[:200] for p in prompt_parts if isinstance(p, str)]}")
         return None
    except google.api_core.exceptions.GoogleAPIError as api_err:
        print(f"❌ Gemini API call failed: {type(api_err).__name__} - {api_err}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error during Gemini API call: {e}")
        traceback.print_exc()
        return None

    # Process Response
    try:
        raw_text_response = ""
        if not response.candidates:
             block_reason_info = "N/A"
             try: block_reason_info = f"Reason: {response.prompt_feedback.block_reason.name}, Safety: {response.prompt_feedback.safety_ratings}"
             except Exception: pass
             error_msg = f"Error: No candidates in response. Prompt Blocked? {block_reason_info}."
             print(f"❌ {error_msg}"); return None

        candidate = response.candidates[0]
        finish_reason = getattr(getattr(candidate, 'finish_reason', None), 'name', "UNKNOWN")

        if candidate.content and candidate.content.parts:
            raw_text_response = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
            print(f"   📝 Received raw text response (finish: {finish_reason}, len: {len(raw_text_response)})")

            parsed_data = safely_parse_gemini_json(raw_text_response)

            if parsed_data is not None:
                if finish_reason == "MAX_TOKENS":
                     print("   ⚠️ WARNING: Chunk response stopped due to MAX_TOKENS. JSON might be incomplete for this chunk!")
                     parsed_data["_warning_max_tokens_chunk"] = True
                elif finish_reason == "SAFETY":
                     print("   ⚠️ WARNING: Chunk response stopped due to SAFETY settings.")
                     try: print(f"      Safety Ratings: {candidate.safety_ratings}")
                     except Exception: pass
                     parsed_data["_warning_safety_chunk"] = True
                elif finish_reason not in ["STOP", "UNSPECIFIED", ""]:
                     print(f"   ⚠️ WARNING: Chunk finished with non-standard reason: {finish_reason}")
                return parsed_data # Success
            else:
                # JSON parsing failed
                print(f"      Raw Response Snippet (Failed Parse): '{raw_text_response[:250]}...'")
                return None # Treat parsing failure as overall failure for retry

        # Handle generation stopped without content
        elif finish_reason != "STOP":
             safety_ratings_info = "N/A"
             try: safety_ratings_info = str(candidate.safety_ratings)
             except Exception: pass
             error_msg = f"Error: Generation stopped without content. Reason: {finish_reason}. Safety Ratings: {safety_ratings_info}"
             print(f"❌ {error_msg}"); return None
        else: # finish_reason == "STOP" but no content parts
            print("⚠️ Warn: Gemini finished with STOP but returned no content parts for chunk."); return None

    except AttributeError as ae:
        print(f"❌ Error accessing response attributes: {ae}")
        print(f"   Raw response object type: {type(response)}")
        return None
    except Exception as e:
        print(f"❌ Error processing Gemini response for chunk: {e}"); traceback.print_exc(); return None

# --- Modified: Gemini OCR Function for Math (Now used per chunk) ---
def call_gemini_ocr_math(
    model_name: str,
    image_inputs: List[Any], # Should be PIL Images
    chunk_page_numbers: List[int], # Page numbers for context
    language: str,
    generate_explanation: bool,
    generate_answer: bool,
    custom_prompt: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Builds prompt and calls Gemini for math content FOR A SINGLE CHUNK."""
    if not image_inputs: print("❌ Error: No image inputs provided to call_gemini_ocr_math."); return None
    page_num_str = ", ".join(map(str, chunk_page_numbers))
    # print(f"🧠 Preparing Gemini MATH call for CHUNK (Pages: {page_num_str}, Model: {model_name}, Custom: {bool(custom_prompt)})...") # Verbose
    try:
        prompt_parts = _build_common_prompt_parts(
            len(image_inputs), chunk_page_numbers, language,
            generate_explanation, generate_answer, custom_prompt
        )
        # Add math-specific formatting instruction AFTER base/custom prompts
        prompt_parts.append("""
--- Mathematical Content Formatting (Applies to pages {page_num_str}) ---
*   Identify ALL mathematical expressions within `question_text`, `options`, and `explanation` (if generated).
*   Format ONLY these math parts using standard inline LaTeX notation: `\\(...\\)`.
*   Apply `\\(...\\)` consistently. All other text remains plain.
""")
        # print("   ➕ Requesting STANDARD `\\(...\\)` LaTeX within JSON output for chunk.") # Verbose
        prompt_parts.append(f"\nGenerate the single, valid JSON object containing data ONLY for pages {page_num_str} according to ALL instructions.")

        return _call_gemini_and_get_json(model_name, prompt_parts, image_inputs)
    except Exception as e: print(f"❌ Error in call_gemini_ocr_math setup for chunk: {e}"); traceback.print_exc(); return None

# --- Modified: Gemini OCR Function for Plain Text (Now used per chunk) ---
def call_gemini_ocr_plain(
    model_name: str,
    image_inputs: List[Any], # Should be PIL Images
    chunk_page_numbers: List[int], # Page numbers for context
    language: str,
    generate_explanation: bool,
    generate_answer: bool,
    custom_prompt: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Builds prompt and calls Gemini for plain text content FOR A SINGLE CHUNK."""
    if not image_inputs: print("❌ Error: No image inputs provided to call_gemini_ocr_plain."); return None
    page_num_str = ", ".join(map(str, chunk_page_numbers))
    # print(f"🧠 Preparing Gemini PLAIN TEXT call for CHUNK (Pages: {page_num_str}, Model: {model_name}, Custom: {bool(custom_prompt)})...") # Verbose
    try:
        prompt_parts = _build_common_prompt_parts(
            len(image_inputs), chunk_page_numbers, language,
            generate_explanation, generate_answer, custom_prompt
        )
        # Add plain text specific instruction AFTER base/custom prompts
        prompt_parts.append("""
--- Text Formatting (Applies to pages {page_num_str}) ---
*   Ensure all text in JSON values (`question_text`, `options`, `explanation` (if generated), etc.) is **PLAIN TEXT ONLY**.
*   **DO NOT** add any LaTeX or markdown formatting.
""")
        # print("   📄 Requesting PLAIN TEXT only within JSON output for chunk.") # Verbose
        prompt_parts.append(f"\nGenerate the single, valid JSON output containing plain text data ONLY for pages {page_num_str} according to ALL instructions.")

        return _call_gemini_and_get_json(model_name, prompt_parts, image_inputs)
    except Exception as e: print(f"❌ Error in call_gemini_ocr_plain setup for chunk: {e}"); traceback.print_exc(); return None

def call_gemini_raw_text(
    model_name: str,
    prompt_parts: List[str],
    image_inputs: List[Image.Image]
) -> Optional[str]:
    """
    Calls Gemini with raw text expectation (not JSON).
    """
    try:
        gemini_model = genai.GenerativeModel(
            model_name=f'models/{model_name}',
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )
        response = gemini_model.generate_content(prompt_parts + image_inputs, stream=False)
        if response and response.candidates and response.candidates[0].content.parts:
            return "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text')).strip()
    except Exception as e:
        print(f"❌ Error in call_gemini_raw_text: {e}")
    return None

def build_raw_ocr_prompt(language: str, custom_prompt: Optional[str] = None) -> str:
    """
    Builds the prompt for raw text extraction, emphasizing paragraph separation.
    """
    prompt = f"""
You are an OCR system. Extract ALL visible readable text from the provided image. Maintain the vertical reading order as closely as possible.

**CRITICAL Formatting Instructions:**
1.  Use **double line breaks (`\\n\\n`)** to separate distinct paragraphs, headings, or visually separated blocks of text.
2.  Use single line breaks (`\\n`) ONLY where they naturally occur within a paragraph (e.g., poetry, addresses).
3.  Preserve the original text content accurately.
4.  Do not add any commentary, summaries, or interpretations. Just transcribe.
5.  Do not use Markdown or JSON formatting. Output plain text.
6.  Keep text in original language: {language}.
7.  If the page is empty or contains no readable text, return ONLY the phrase: "[No readable content found on this page]"
""".strip() # Use strip() here to remove leading/trailing whitespace from the whole prompt string

    if custom_prompt:
        # Ensure custom prompt is stripped before appending
        prompt += f"\n\n--- Additional User Instructions (These might override previous instructions) ---\n{custom_prompt.strip()}\n--- End User Instructions ---"

    return prompt

def build_raw_math_ocr_prompt(language: str, custom_prompt: Optional[str] = None) -> str:
    """
    Builds the prompt for raw text extraction, emphasizing paragraph separation
    AND requesting inline LaTeX formatting for math.
    """
    prompt = f"""
You are an OCR system. Extract ALL visible readable text from the provided image. Maintain the vertical reading order as closely as possible.

**CRITICAL Formatting Instructions:**
1.  Use **double line breaks (`\\n\\n`)** to separate distinct paragraphs, headings, or visually separated blocks of text.
2.  Use single line breaks (`\\n`) ONLY where they naturally occur within a paragraph (e.g., poetry, addresses).
3.  Preserve the original text content accurately.
4.  Identify **all mathematical expressions** (equations, formulas, symbols, variables used mathematically).
5.  Format **ONLY these mathematical parts** using standard inline LaTeX notation: `\\(...\\)`.
6.  **All other text MUST remain plain text.** Do not use LaTeX for non-mathematical content.
7.  Do not add any commentary, summaries, or interpretations. Just transcribe.
8.  Do not use Markdown or JSON formatting (except for the requested LaTeX). Output plain text with LaTeX for math.
9.  Keep text in original language: {language}.
10. If the page is empty or contains no readable text, return ONLY the phrase: "[No readable content found on this page]"
""".strip()

    if custom_prompt:
        # Ensure custom prompt is stripped before appending
        prompt += f"\n\n--- Additional User Instructions (These might override previous instructions, apply them carefully considering the LaTeX requirement) ---\n{custom_prompt.strip()}\n--- End User Instructions ---"

    return prompt

# --- NEW HELPER: Process a SINGLE chunk with retries ---
def _process_single_chunk_with_retries(
    chunk_image_paths: List[str],
    chunk_page_numbers: List[int], # Page numbers for context in prompt
    company: str,
    model: str,
    language: str,
    content_mode: str,
    generate_explanation: bool,
    generate_answer: bool,
    custom_prompt: Optional[str],
    max_retries: int,
    retry_delay_seconds: int
) -> Optional[Dict[str, Any]]:
    """
    Loads images for a chunk, handles the actual API call via appropriate function (math/plain)
    and manages retries for that chunk.
    """
    if not chunk_image_paths: return None

    start_page = min(chunk_page_numbers)
    end_page = max(chunk_page_numbers)

    # Load images for this specific chunk first
    loaded_chunk_images = _load_images_for_prompt(chunk_image_paths)
    if loaded_chunk_images is None:
         print(f"      ❌ Failed to load images for chunk pages {start_page}-{end_page}. Skipping chunk.")
         return None # Cannot proceed without images for the chunk

    for attempt in range(max_retries):
        print(f"      🔄 Chunk Attempt {attempt + 1} of {max_retries} (Pages {start_page}-{end_page})...")
        parsed_data = None
        try:
            if company == "gemini":
                if not gemini_api_key_valid:
                     print(f"         ❌ [Attempt {attempt+1}] Cannot call Gemini, API key invalid.")
                     return None

                # Call the appropriate mode-specific function for the chunk
                if content_mode == 'math':
                    parsed_data = call_gemini_ocr_math(
                        model_name=model,
                        image_inputs=loaded_chunk_images, # Pass loaded PIL images
                        chunk_page_numbers=chunk_page_numbers,
                        language=language,
                        generate_explanation=generate_explanation,
                        generate_answer=generate_answer,
                        custom_prompt=custom_prompt
                    )
                else: # content_mode == 'text'
                    parsed_data = call_gemini_ocr_plain(
                        model_name=model,
                        image_inputs=loaded_chunk_images, # Pass loaded PIL images
                        chunk_page_numbers=chunk_page_numbers,
                        language=language,
                        generate_explanation=generate_explanation,
                        generate_answer=generate_answer,
                        custom_prompt=custom_prompt
                    )
            # --- (elif for other companies: openai, ollama) ---
            else:
                print(f"         ❌ [Attempt {attempt+1}] Unsupported company: {company}")
                return None

            # --- Check result of the attempt ---
            if parsed_data is not None and isinstance(parsed_data, dict):
                # --- Basic Validation: Check if ALL expected page MCQ keys are present ---
                # This helps catch cases where the AI missed processing a page within the chunk
                all_keys_found = True
                missing_keys = []
                for page_num in chunk_page_numbers:
                     mcq_key = f"page_{page_num}_MCQs"
                     if mcq_key not in parsed_data:
                         # It's possible a page genuinely has no MCQs, but missing the key entirely is suspicious
                         print(f"         ⚠️ [Attempt {attempt+1}] Warning: Expected key '{mcq_key}' potentially missing in response for chunk.")
                         missing_keys.append(mcq_key)
                         # Decide if missing key is a hard failure requiring retry
                         # all_keys_found = False

                # If strict key check is needed:
                # if not all_keys_found:
                #     print(f"         ❌ [Attempt {attempt+1}] Failed due to missing expected page keys: {missing_keys}")
                #     # Fall through to retry logic

                # --- If passed validation (or validation is relaxed) ---
                #else:
                print(f"         ✅ [Attempt {attempt+1}] Successfully received and parsed JSON for chunk (Pages {start_page}-{end_page}).")
                # Enforce 'original_page' as a fallback (AI should ideally include it based on prompt)
                for page_num in chunk_page_numbers:
                    mcq_key = f"page_{page_num}_MCQs"
                    if mcq_key in parsed_data and isinstance(parsed_data[mcq_key], list):
                        for mcq_item in parsed_data[mcq_key]:
                            if isinstance(mcq_item, dict): # Ensure item is a dict
                                mcq_item.setdefault('original_page', page_num) # Set if missing
                return parsed_data # Success for this chunk!


            # --- Handle failure for this attempt ---
            print(f"         ⚠️ [Attempt {attempt+1}] Failed to get valid/complete parsed JSON for chunk (Pages {start_page}-{end_page}).")
            # (Includes cases where parsed_data is None or validation failed)
            if attempt < max_retries - 1:
                print(f"            Retrying chunk in {retry_delay_seconds} seconds...")
                time.sleep(retry_delay_seconds)
            # else: # No need for specific message here, loop will exit naturally

        except Exception as e:
            print(f"         ❌❌❌ [Attempt {attempt+1}] Unexpected Error during SINGLE CHUNK processing (Pages {start_page}-{end_page}): {e}")
            traceback.print_exc()
            # If unexpected error occurs, don't retry immediately unless it's the last attempt anyway
            if attempt >= max_retries - 1:
                 print(f"         ❌ [Attempt {attempt+1}] Failed chunk due to unexpected error on last attempt.")
                 # Fall through to return None outside loop

    # Failed all retries for this chunk
    print(f"      ❌ Failed processing chunk for pages {start_page}-{end_page} after all retries.")
    return None

# --- NEW Main Entry Point: Process Images in Chunks ---
def call_ocr_model_in_chunks(
    company: str,
    model: str,
    all_image_paths: List[str], # List of ALL image paths for the document
    language: str,
    content_mode: str,
    generate_explanation: bool,
    generate_answer: bool,
    custom_prompt: Optional[str] = None,
    max_retries_per_chunk: int = 2,
    chunk_size: int = 1,
    retry_delay_seconds: int = 5
) -> Optional[Dict[str, Any]]:
    """
    Processes images in chunks OR handles a single image. Combines results.
    """
    if not all_image_paths:
        print("❌ [call_ocr_model_in_chunks] No image paths provided.")
        return None

    total_pages = len(all_image_paths)
    chunk_size = max(1, chunk_size) # Ensure chunk size is at least 1

    # --- Handle Single Image Upload Case ---
    is_single_direct_upload = False
    if total_pages == 1:
        # Check if the single filename matches the expected 'page_N.png' pattern
        match = re.search(r'page_(\d+)\.png$', os.path.basename(all_image_paths[0]))
        if not match:
            is_single_direct_upload = True
            print(f"ℹ️ [Chunking] Detected single direct image upload: {os.path.basename(all_image_paths[0])}. Processing as Page 1.")
            # Treat this single image as chunk size 1, page number 1
            chunk_size = 1
    # -------------------------------------

    print(f"⚡ [Chunking] Starting processing for {total_pages} page(s) in chunks of up to {chunk_size}.")

    combined_results = { "header_footer_info": {} }
    processing_errors = []

    # --- Iterate through image paths in chunks ---
    for i in range(0, total_pages, chunk_size):
        chunk_image_paths = all_image_paths[i:min(i + chunk_size, total_pages)]
        if not chunk_image_paths: continue

        # --- Determine original page numbers for this chunk ---
        chunk_page_numbers = []
        start_page, end_page = 0, 0 # Initialize
        try:
            # --- MODIFIED Page Number Logic ---
            if is_single_direct_upload:
                 chunk_page_numbers = [1] # Assign page number 1 for single upload
            else:
                 # Attempt to extract from filenames (for PDFs)
                 for p in chunk_image_paths:
                     match = re.search(r'page_(\d+)\.png$', os.path.basename(p))
                     if match:
                         chunk_page_numbers.append(int(match.group(1)))
                     else:
                          # This should ideally not happen if it's not a single direct upload
                          raise ValueError(f"Could not extract page number from expected PDF page filename: {os.path.basename(p)}")
                 if not chunk_page_numbers: # Should not happen if loop runs and regex works
                      raise ValueError("Page number extraction resulted in an empty list.")
            # ---------------------------------

            chunk_page_numbers.sort()
            start_page = min(chunk_page_numbers)
            end_page = max(chunk_page_numbers)
            print(f"\n--- Processing Chunk: Pages {start_page}-{end_page} ({len(chunk_image_paths)} images) ---")

        except (ValueError, IndexError) as e:
             print(f"⚠️ [Chunking] Error determining page numbers for chunk starting at index {i}. Error: {e}. Paths: {chunk_image_paths}")
             print("    Skipping this chunk.")
             processing_errors.append(f"Page number determination error for chunk {i//chunk_size + 1}")
             continue # Skip to the next chunk
        # --- End Page Number Logic ---

        # --- Call the SINGLE CHUNK processing function with retries ---
        # (The rest of the loop calling _process_single_chunk_with_retries and combining results
        # remains the same as the previous version)
        chunk_result_data = _process_single_chunk_with_retries(
            chunk_image_paths=chunk_image_paths,
            chunk_page_numbers=chunk_page_numbers, # Pass determined page numbers
            company=company, model=model, language=language, content_mode=content_mode,
            generate_explanation=generate_explanation, generate_answer=generate_answer,
            custom_prompt=custom_prompt, max_retries=max_retries_per_chunk,
            retry_delay_seconds=retry_delay_seconds
        )

        # --- Combine results from the chunk ---
        if chunk_result_data and isinstance(chunk_result_data, dict):
            print(f"   ✅ [Chunk Pages {start_page}-{end_page}] Successfully processed and received data.")
            # Merge MCQ data
            for page_num in chunk_page_numbers:
                page_mcq_key = f"page_{page_num}_MCQs"
                mcqs_from_chunk_page = chunk_result_data.get(page_mcq_key)
                if mcqs_from_chunk_page is not None and isinstance(mcqs_from_chunk_page, list):
                    if mcqs_from_chunk_page:
                        print(f"      Merging {len(mcqs_from_chunk_page)} MCQs from page {page_num}.")
                    combined_results[page_mcq_key] = mcqs_from_chunk_page

            # Merge header/footer info
            chunk_hf_info = chunk_result_data.get("header_footer_info", {})
            if isinstance(chunk_hf_info, dict):
                 combined_results["header_footer_info"].update(chunk_hf_info)

            # Capture chunk-specific warnings
            if chunk_result_data.get("_warning_max_tokens_chunk"): processing_errors.append(f"Chunk Pages {start_page}-{end_page}: Hit MAX_TOKENS.")
            if chunk_result_data.get("_warning_safety_chunk"): processing_errors.append(f"Chunk Pages {start_page}-{end_page}: Stopped due to SAFETY.")
        else:
            print(f"   ❌ [Chunk Pages {start_page}-{end_page}] FAILED to get valid data after retries.")
            processing_errors.append(f"Chunk failed for pages {start_page}-{end_page}")

    # --- Final Check ---
    if not any(k.startswith("page_") and k.endswith("_MCQs") for k in combined_results):
         print("❌ [Chunking] No MCQs could be extracted from any chunk successfully.")
         return None

    if processing_errors:
        print(f"⚠️ [Chunking] Completed with {len(processing_errors)} chunk error(s)/warning(s): {processing_errors}")
        combined_results["_processing_warnings"] = processing_errors

    print(f"✅ [Chunking] Finished processing all chunks. Returning combined results.")
    combined_results.pop("_warning_max_tokens_chunk", None) # Clean temp flags
    combined_results.pop("_warning_safety_chunk", None)
    return combined_results

# --- End of ocr_processor.py ---