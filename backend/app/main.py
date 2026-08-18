import io

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

from app.config import MAX_UPLOAD_BYTES
from app.services.pdf_generator import PDFReportService
from app.services.vcf_parser import VariantAnnotationEngine
from app.services.graph_engine import KnowledgeGraphService

app = FastAPI(title="PharmaGen Clinical API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _annotate_vcf(file_bytes: bytes) -> dict:
    if not file_bytes or not file_bytes.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).")

    raw_variants = VariantAnnotationEngine.parse_vcf_stream(file_bytes)
    if not raw_variants:
        raise HTTPException(status_code=400, detail="No valid VCF variants found in the uploaded file.")

    annotated = [
        {
            "variant_info": v,
            "clinical_matches": VariantAnnotationEngine.match_clinical_evidence(v["gene"], v["mutation"]),
        }
        for v in raw_variants
    ]
    return {"status": "success", "variants_count": len(raw_variants), "annotated_results": annotated}


def _results_to_dataframe(annotated_results: list) -> pd.DataFrame:
    rows = []
    for item in annotated_results:
        v = item["variant_info"]
        for m in item["clinical_matches"]:
            rows.append({
                "Gene": v["gene"],
                "Mutation": v["mutation"],
                "Disease": m["disease"],
                "Targeted Drug": m["therapy"],
                "Evidence Level": m["evidence_tier"],
            })
    return pd.DataFrame(rows)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "pharmagen-backend"}


@app.post("/api/v1/analyze")
# Handles VCF upload, annotates variants with clinical evidence, and returns JSON results
async def analyze_patient_vcf(file: UploadFile = File(...)):
    contents = await file.read()
    return _annotate_vcf(contents)


@app.post("/api/v1/report")
# Generates a downloadable PDF clinical report for the uploaded VCF
async def generate_patient_report(file: UploadFile = File(...)):
    contents = await file.read()
    result = _annotate_vcf(contents)
    df = _results_to_dataframe(result["annotated_results"])
    pdf_bytes = PDFReportService.create_clinical_pdf(df)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="pharmagen_clinical_report.pdf"'},
    )


@app.post("/api/v1/graph")
# Returns a self-contained HTML knowledge graph for the uploaded VCF
async def generate_patient_graph(file: UploadFile = File(...)):
    contents = await file.read()
    result = _annotate_vcf(contents)

    graph_html = KnowledgeGraphService.generate_interactive_html(result["annotated_results"])
    return HTMLResponse(content=graph_html)
