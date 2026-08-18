from fastapi.testclient import TestClient

from app.config import SAMPLE_VCF_PATH
from app.main import app
from app.services.vcf_parser import VariantAnnotationEngine

client = TestClient(app)

SAMPLE_VCF = open(SAMPLE_VCF_PATH, "rb").read()


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_analyze_sample_vcf():
    resp = client.post(
        "/api/v1/analyze",
        files={"file": ("patient_sample.vcf", SAMPLE_VCF)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["variants_count"] == 3
    assert len(data["annotated_results"]) == 3

    for item in data["annotated_results"]:
        assert item["clinical_matches"], "expected at least one evidence match"


def test_analyze_sample_vcf_has_known_evidence():
    resp = client.post(
        "/api/v1/analyze",
        files={"file": ("patient_sample.vcf", SAMPLE_VCF)},
    )
    data = resp.json()
    braf = next(i for i in data["annotated_results"] if i["variant_info"]["gene"] == "BRAF")
    assert braf["variant_info"]["mutation"] == "V600E"
    assert any(m["therapy"] == "Vemurafenib" for m in braf["clinical_matches"])


def test_analyze_empty_file_rejected():
    resp = client.post("/api/v1/analyze", files={"file": ("empty.vcf", b"")})
    assert resp.status_code == 400


def test_analyze_garbage_rejected():
    resp = client.post("/api/v1/analyze", files={"file": ("junk.vcf", b"not a vcf file at all")})
    assert resp.status_code == 400


def test_report_returns_pdf():
    resp = client.post(
        "/api/v1/report",
        files={"file": ("patient_sample.vcf", SAMPLE_VCF)},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_graph_returns_html():
    resp = client.post(
        "/api/v1/graph",
        files={"file": ("patient_sample.vcf", SAMPLE_VCF)},
    )
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "vis-network" in resp.text or "<html" in resp.text.lower()


def test_parse_snpeff_ann_info():
    vcf_line = "7\t140453136\trs121913364\tA\tT\t.\tPASS\tANN=G|missense_variant|MODERATE|BRAF|ENSG00000157764|transcript|NM_004333.6|protein_coding|6/18|c.1799T>A|p.V600E|1798|1799|600|+|"
    variants = VariantAnnotationEngine.parse_vcf_stream(vcf_line.encode())
    assert variants[0]["gene"] == "BRAF"
    assert variants[0]["mutation"] == "V600E"


def test_parse_hgvsp_fallback():
    vcf_line = "7\t140453136\trs121913364\tA\tT\t.\tPASS\tHGVSp=p.V600E"
    variants = VariantAnnotationEngine.parse_vcf_stream(vcf_line.encode())
    assert variants[0]["mutation"] == "V600E"


def test_parse_ref_alt_fallback():
    vcf_line = "7\t140453136\trs121913364\tA\tT\t.\tPASS\t."
    variants = VariantAnnotationEngine.parse_vcf_stream(vcf_line.encode())
    assert variants[0]["mutation"] == "A>T"


def test_normalized_mutation_matches_kb():
    matches = VariantAnnotationEngine.match_clinical_evidence("BRAF", "p.V600E")
    assert any(m["therapy"] == "Vemurafenib" for m in matches)