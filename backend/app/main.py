from fastapi import FastAPI, UploadFile, File
from app.services.vcf_parser import VariantAnnotationEngine
from app.services.graph_engine import KnowledgeGraphService

app = FastAPI(title="PharmaGen Clinical API")

@app.post("/api/v1/analyze")
# Handles VCF upload, annotates variants with clinical evidence, and returns JSON results
async def analyze_patient_vcf(file: UploadFile = File(...)):
    contents = await file.read()
    raw_variants = VariantAnnotationEngine.parse_vcf_stream(contents)
    
    annotated = []
    for v in raw_variants:
        matches = VariantAnnotationEngine.match_clinical_evidence(v["gene"], v["mutation"])
        annotated.append({"variant_info": v, "clinical_matches": matches})
        
    return {
        "status": "success",
        "variants_count": len(raw_variants),
        "annotated_results": annotated
    }