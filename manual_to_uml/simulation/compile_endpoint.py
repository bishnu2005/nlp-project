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
        
    if len(sentences) > 500:
        raise HTTPException(status_code=400, detail=f"Validation Error: Manual size limit exceeded. Max 500 sentences, found {len(sentences)}.")

    # Phase 9: Deterministic Procedural Detector Gate
    from manual_to_uml.extraction.procedural_detector import is_procedural_manual
    
    is_procedural = is_procedural_manual(sentences)
    if is_procedural:
        logger.info("[FSM] Procedural manual detected")
        logger.info("[FSM] Deterministic builder used")
        logger.info("[FSM] LLM calls skipped")
        
        from manual_to_uml.extraction.procedural_fsm_builder import build_procedural_fsm
        ibr, human_review_flags = build_procedural_fsm(sentences)
        logger.info(f"[Compile] Procedural IBR assembled: {len(ibr.states)} states, {len(ibr.transitions)} transitions")
        
    else:
        # Step 3: LLM Extraction via local model
        logger.info(f"[LLM] Local Ollama extraction started (Fallback Mode)")
        from manual_to_uml.extraction.llm_extractor import LLMExtractor
        
        api_key = os.getenv("GEMINI_API_KEY")
        extractor = LLMExtractor(api_key=api_key)
        extractions = extractor.extract_all(sentences)
        logger.info(f"[LLM] Gemini extraction completed — {len(extractions)} results")

        # Step 3b: Convert extractions to Intermediate Representation (IR) Pipeline
        logger.info("[Compile] Step 3b: Converting primitives into Intermediate Representation (IR)...")
        from manual_to_uml.ir.ir_builder import build_ir
        primitives = []
        
        for ext in extractions:
            events = ext.events_implied
            conditions = [g.get("condition") for g in ext.guards_implied] if getattr(ext, "guards_implied", None) else []
            sids = []
            for sid_str in ext.source_sentence_ids:
                try:
                    sids.append(int(sid_str.replace("s", "")))
                except:
                    sids.append(0)
            
            p = build_ir(events, conditions, sids)
            primitives.extend(p)
            
        logger.info("IR primitives generated: %d", len(primitives))

        # Step 3c: State Abstraction (Solve State Explosion)
        logger.info("[Compile] Step 3c: Abstracting extractions into architectural FSM modes...")
        from manual_to_uml.extraction.state_abstractor import StateAbstractor
        abstractor = StateAbstractor()
        abstracted_extractions = abstractor.abstract(primitives, sentences)
        logger.info(f"[Compile] Abstraction compressed {len(primitives)} primitives to {len(abstracted_extractions)} state blocks")

        # Step 4: Assemble IBR
        logger.info("[Compile] Step 4: Assembling IBR from extractions...")
        from manual_to_uml.extraction.ibr_assembler import IBRAssembler
        assembler = IBRAssembler()
        ibr, human_review_flags = assembler.assemble(abstracted_extractions, sentences)
        logger.info(f"[Compile] IBR assembled: {len(ibr.states)} states, {len(ibr.transitions)} transitions")

    # Step 5: Run verification pipeline (structural + Z3 + Graph constraints)
    logger.info("[Compile] Step 5: Running verification pipeline...")
    from manual_to_uml.verification.structural_verifier import verify_structure
    from manual_to_uml.verification.z3_verifier import verify_ibr
    import networkx as nx

    structural_issues = verify_structure(ibr)
    guard_conflicts = verify_ibr(ibr)
    
    # 5b. FSM Complexity Bounds
    if len(ibr.states) > 30:
        raise HTTPException(status_code=400, detail=f"Validation Error: FSM exceeds size limits. Max states=30, got {len(ibr.states)}.")
    if len(ibr.transitions) > 100:
        raise HTTPException(status_code=400, detail=f"Validation Error: FSM exceeds size limits. Max transitions=100, got {len(ibr.transitions)}.")
        
    initial_states = [s for s in ibr.states if getattr(s, 'is_initial', False)]
    terminal_states = [s for s in ibr.states if getattr(s, 'is_terminal', False)]
    op_states = [s for s in ibr.states if not getattr(s, 'is_initial', False) and not getattr(s, 'is_terminal', False) and not getattr(s, 'is_fault', False)]

    # 5c. FSM Structural Validation
    if len(initial_states) != 1:
        raise HTTPException(status_code=400, detail=f"Validation Error: Exactly 1 Initial state required, found {len(initial_states)}.")
    if len(terminal_states) < 1:
        raise HTTPException(status_code=400, detail=f"Validation Error: >=1 Terminal state required, found {len(terminal_states)}.")
    if len(op_states) < 1:
        raise HTTPException(status_code=400, detail=f"Validation Error: >=1 Operational state required, found {len(op_states)}.")
    if len(ibr.transitions) < 1:
        raise HTTPException(status_code=400, detail=f"Validation Error: >=1 Transition required, found 0.")

    # 5d. NetworkX Constraints & Reachability
    G = nx.DiGraph()
    for s in ibr.states: G.add_node(s.id, is_initial=s.is_initial, is_terminal=s.is_terminal)
    for t in ibr.transitions: G.add_edge(t.from_state, t.to_state, event=t.event)
    
    start_node = initial_states[0].id
    reachable = set(nx.descendants(G, start_node))
    reachable.add(start_node)
    
    unreachable = [n for n in G.nodes if n not in reachable]
    if unreachable:
        human_review_flags.append(f"Graph Integrity Warning: States {unreachable} are completely unreachable from the starting point.")
        
    terminal_ids = {s.id for s in terminal_states}
    if not any(tid in reachable for tid in terminal_ids):
        raise HTTPException(status_code=400, detail="Validation Error: Terminal Reachability failed. No Terminal state is reachable from Initial state.")

    if not nx.is_weakly_connected(G) and len(G.nodes) > 1:
        human_review_flags.append("Graph Integrity Warning: The FSM is disconnected into isolated sub-graphs.")
        
    # 5e. Fault Chain Prevention
    fault_state_ids = {s.id for s in ibr.states if getattr(s, 'is_fault', False)}
    for t in ibr.transitions:
        if t.from_state in fault_state_ids and t.to_state in fault_state_ids:
             logger.error(f"[Fault Chain Detected] {t.from_state} -> {t.to_state}")
             raise HTTPException(status_code=400, detail=f"Validation Error: Fault chain prevention. '{t.from_state}' directly transitions to fault '{t.to_state}'.")

    # 5f. Traceability Constraints
    missing_trace = []
    used_sids = set()
    for s in ibr.states:
        if not getattr(s, 'source_sentence_ids', None): missing_trace.append(f"State '{s.id}'")
        else: used_sids.update(s.source_sentence_ids)
    for t in ibr.transitions:
        if not getattr(t, 'source_sentence_ids', None): missing_trace.append(f"Transition '{t.id}'")
        else: used_sids.update(t.source_sentence_ids)
    
    if missing_trace:
        logger.error(f"[Validation] Missing Traceability constraints on items: {missing_trace}")
        print(f"!!! MISSING TRACES: {missing_trace}")
        raise HTTPException(
            status_code=400,
            detail=f"Compilation rejected: {len(missing_trace)} structural objects missing Traceability mapping."
        )
        
    # 5g. Sentence Coverage Metric
    total_sentences = len(sentences)
    coverage = len(used_sids) / total_sentences if total_sentences > 0 else 0
    if coverage < 0.5:
        raise HTTPException(status_code=400, detail=f"Validation Error: Manual coverage too low ({coverage:.2f} < 0.5). Model extracted less than half of the text footprint.")

    # 5h. Guard Exclusivity Validation
    from manual_to_uml.verification.z3_verifier import ConflictType
    overlap_conflicts = [c for c in guard_conflicts if c.conflict_type == ConflictType.OVERLAP]
    if overlap_conflicts:
        err_msg = "; ".join([c.description for c in overlap_conflicts])
        raise HTTPException(
            status_code=400,
            detail=f"Validation Error: Guard Exclusivity Failed. Overlapping transitions detected. {err_msg}"
        )

    logger.info(f"[Compile] Verification complete — {len(structural_issues)} structural issues, {len(guard_conflicts)} guard conflicts, {len(human_review_flags)} warnings")

    from manual_to_uml.config import DEBUG_PIPELINE
    if DEBUG_PIPELINE:
        logger.info("[DEBUG] FSM SUMMARY")
        logger.info({
            "states_count": len(ibr.states),
            "transitions_count": len(ibr.transitions),
            "initial_state": [s.id for s in initial_states],
            "terminal_states": [s.id for s in terminal_states]
        })
        
        # Optional JSON output
        import json
        try:
            debug_out = {
                "sentences": [s.model_dump() if hasattr(s, "model_dump") else s.dict() for s in sentences],
                "states": [s.model_dump() if hasattr(s, "model_dump") else s.dict() for s in ibr.states],
                "transitions": [t.model_dump() if hasattr(t, "model_dump") else t.dict() for t in ibr.transitions]
            }
            with open("debug_pipeline_output.json", "w") as f:
                json.dump(debug_out, f, indent=2)
            logger.info("Wrote debug output to debug_pipeline_output.json")
        except Exception as e:
            logger.error(f"Failed to write debug json: {e}")

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
