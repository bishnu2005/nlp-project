import os
import logging
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

compile_router = APIRouter(prefix="/api", tags=["compilation"])


# --- Response Models ---

class CompileResponse(BaseModel):
    ibr_model: Dict[str, Any]
    verification: Dict[str, Any]
    human_review_flags: List[str]


# --- Text extraction helpers ---

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF using PyMuPDF (fitz)."""
    import fitz  # PyMuPDF

    logger.info("[OCR] Extracting text from PDF...")
    text_parts = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page_num, page in enumerate(doc):
            page_text = page.get_text()
            text_parts.append(page_text)
            logger.info(f"[OCR] Page {page_num + 1}: extracted {len(page_text)} chars")

    full_text = "\n".join(text_parts)
    logger.info(f"[OCR] PDF extraction complete — {len(full_text)} chars total across {len(text_parts)} pages")
    return full_text


def extract_text_from_image(file_bytes: bytes) -> str:
    """Extract text from an image using pytesseract OCR."""
    import pytesseract
    from PIL import Image
    import io

    logger.info("[OCR] Extracting text from image via Tesseract OCR...")
    image = Image.open(io.BytesIO(file_bytes))
    text = pytesseract.image_to_string(image)
    logger.info(f"[OCR] Image OCR complete — {len(text)} chars extracted")
    return text


# --- Main endpoint ---

@compile_router.post("/compile-manual", response_model=CompileResponse)
async def compile_manual(
    manual_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """
    Compile a procedural manual into a verified IBR model.
    
    Accepts either:
    - manual_text: raw text pasted by the user
    - file: a PDF or image (JPG/PNG) upload
    """
    # Step 1: Resolve the input text
    text = None

    if manual_text and manual_text.strip():
        text = manual_text.strip()
        logger.info(f"[Compile] Using provided manual text ({len(text)} chars)")

    elif file:
        file_bytes = await file.read()
        filename = file.filename.lower() if file.filename else ""
        content_type = file.content_type or ""

        logger.info(f"[Compile] Received file: {file.filename} ({content_type}, {len(file_bytes)} bytes)")

        if filename.endswith(".pdf") or "pdf" in content_type:
            text = extract_text_from_pdf(file_bytes)
        elif any(filename.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff")):
            text = extract_text_from_image(file_bytes)
        elif "image" in content_type:
            text = extract_text_from_image(file_bytes)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {filename}. Accepted: .pdf, .jpg, .png"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'manual_text' or upload a file (PDF/image)."
        )

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="No text could be extracted from the input.")

    # Step 2: Preprocess → NLP sentence splitting
    logger.info("[Compile] Step 2: Preprocessing manual text...")
    from manual_to_uml.extraction.preprocessor import preprocess_manual
    sentences = preprocess_manual(text)
    logger.info(f"[Compile] Preprocessed into {len(sentences)} sentences")

    if not sentences:
        raise HTTPException(status_code=400, detail="No sentences could be extracted from the manual text.")

    # Step 3: LLM Extraction via Gemini
    logger.info("[LLM] Gemini extraction started")
    from manual_to_uml.extraction.llm_extractor import LLMExtractor
    
    api_key = os.getenv("GEMINI_API_KEY")
    extractor = LLMExtractor(api_key=api_key)
    extractions = extractor.extract_all(sentences)
    logger.info(f"[LLM] Gemini extraction completed — {len(extractions)} results")

    # Step 3b: State Abstraction (Solve State Explosion)
    logger.info("[Compile] Step 3b: Abstracting extractions into architectural FSM modes...")
    from manual_to_uml.extraction.state_abstractor import StateAbstractor
    abstractor = StateAbstractor()
    abstracted_extractions = abstractor.abstract(extractions, sentences)
    logger.info(f"[Compile] Abstraction compressed {len(extractions)} extractions to {len(abstracted_extractions)} state blocks")

    # Step 4: Assemble IBR
    logger.info("[Compile] Step 4: Assembling IBR from extractions...")
    from manual_to_uml.extraction.ibr_assembler import IBRAssembler
    assembler = IBRAssembler()
    ibr, human_review_flags = assembler.assemble(abstracted_extractions, sentences)
    logger.info(f"[Compile] IBR assembled: {len(ibr.states)} states, {len(ibr.transitions)} transitions")

    # Step 5: Run verification pipeline (structural + Z3)
    logger.info("[Compile] Step 5: Running verification pipeline...")
    from manual_to_uml.verification.structural_verifier import verify_structure
    from manual_to_uml.verification.z3_verifier import verify_ibr

    structural_issues = verify_structure(ibr)
    guard_conflicts = verify_ibr(ibr)

    logger.info(f"[Compile] Verification complete — {len(structural_issues)} structural issues, {len(guard_conflicts)} guard conflicts")

    # Step 6: Build response
    ibr_dict = ibr.model_dump()

    verification = {
        "structural_issues": [issue.model_dump() for issue in structural_issues],
        "guard_conflicts": [conflict.model_dump() for conflict in guard_conflicts],
    }

    logger.info("[Compile] Pipeline complete — returning IBR model")

    return CompileResponse(
        ibr_model=ibr_dict,
        verification=verification,
        human_review_flags=human_review_flags,
    )
