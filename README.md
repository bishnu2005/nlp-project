# Manual-to-UML

**Neuro-Symbolic Compilation of Procedural Manuals into Verified Executable State Machine Models with Deterministic Conversational Interface**

This project compiles unstructured procedural text into a formally verified UML state machine representation (Intermediate Behavioral Representation or IBR). It features an interactive React simulator, an integrated verification engine utilizing Z3 SMT solving, and a deterministic conversational assistant.

## Features
- **Phase 1: Core Formal Layer**: Strongly typed IBR schemas and symbolic guards. Verified via Z3 solver and NetworkX graph analysis.
- **Phase 2: UML Generation & Reporting**: Exports representations to PlantUML and builds detailed HTML behavioral conformance reports.
- **Phase 3: Interactive Simulator**: FastAPI backend coupled with a rich React frontend leveraging Cytoscape for real-time model interaction and traceability.
- **Phase 4: NLP Extraction**: Leverages spaCy, coreferee, and few-shot OpenAI LLM compilation to break unstructured manuals into the IBR structure.
- **Phase 5: Ambiguity Detection**: Linguistic checks identifying vague quantifiers and semantic multiparsing in procedural instructions.
- **Phase 6: Deterministic Chatbot**: Local cosine-similarity-based intent mapping using `sentence-transformers` linking natural language to state-aware constrained operations.

## Setup Instructions

### 1. Python Backend
Ensure you have Python 3.10+ installed.

```bash
# Create and activate a virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install spaCy English Model and Coreferee English resolver
python -m spacy download en_core_web_sm
python -m coreferee install en
```

### 2. React Frontend
The interactive simulator requires Node.js (v18+ recommended).

```bash
cd frontend
npm install
npm run dev
```

### 3. Running the Backend Server
```bash
# Add current directory to PYTHONPATH
export PYTHONPATH="." # On Windows Powershell: $env:PYTHONPATH="."

# Start the FastAPI Simulator Backend
uvicorn manual_to_uml.simulation.simulator_api:app --reload
```

## Running the Automated Test Suite
The project was built primarily with test-driven development. Run the comprehensive automated pipeline:

```bash
pytest tests/
```
*(Optionally define OPENAI_API_KEY environment variable to test live NLP extractions.)*

## Architecture Notes
The compilation pipeline operates sequentially:
`Text` -> `Preprocessor` -> `Coref` -> `LLM Extractor` -> `Symbolic Normalizer` -> `IBR Assembler` -> `Verification (Z3 & Structural)` -> `Simulator API` -> `React Frontend`
