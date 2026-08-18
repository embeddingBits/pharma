import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "backend" / "data" / "raw"
DB_PATH = str(RAW_DATA_DIR / "clinical_kb.db")
SAMPLE_VCF_PATH = str(RAW_DATA_DIR / "patient_sample.vcf")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
