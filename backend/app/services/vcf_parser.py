import sqlite3
from contextlib import closing

from app.config import DB_PATH

def _normalize_mutation(mutation: str) -> str:
    """Normalizes mutation strings so HGVSp-style and bare amino-acid forms match
    the clinical KB (e.g. 'p.V600E', 'P.V600E' and 'V600E' all match 'V600E')."""
    value = mutation.upper().strip()
    for prefix in ("P.", "C.", "G.", "N.", "R."):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    if ":" in value:
        value = value.split(":", 1)[-1]
    return value

class VariantAnnotationEngine:
    @staticmethod
    # Parses raw VCF bytes into a list of variant dicts with chrom, pos, gene, and mutation
    def parse_vcf_stream(file_bytes: bytes):
        variants = []
        for line in file_bytes.decode("utf-8", errors="ignore").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split("\t")
            if len(parts) < 8:
                continue

            chrom, pos, var_id, ref, alt, qual, filter_status, info_raw = parts[:8]
            info_dict = {}
            for item in info_raw.split(";"):
                if "=" in item:
                    k, v = item.split("=", 1)
                    info_dict[k] = v

            gene = "UNKNOWN"
            mutation = None

            # 1. Custom PharmaGen keys (GENE=...;MUT=...)
            gene = info_dict.get("GENE") or info_dict.get("SYMBOL") or gene
            mutation = info_dict.get("MUT")

            # 2. Standard SnpEff ANN= field: ANN=allele|effect|impact|gene|...|hgvs_c|hgvs_p
            if not mutation and "ANN" in info_dict:
                ann_fields = info_dict["ANN"].split("|")
                if len(ann_fields) >= 4 and ann_fields[3]:
                    gene = ann_fields[3]
                if len(ann_fields) >= 11 and ann_fields[10]:
                    mutation = ann_fields[10]

            # 3. VEP CSQ= field: gene may be in 'SYMBOL=...' subfield or position 3
            if not mutation and "CSQ" in info_dict:
                csq_fields = info_dict["CSQ"].split("|")
                if len(csq_fields) >= 4 and csq_fields[3]:
                    gene = csq_fields[3]
                if len(csq_fields) >= 10 and csq_fields[10]:
                    mutation = csq_fields[10]

            # 4. HGVSp / HGVS_P keys
            if not mutation:
                mutation = info_dict.get("HGVSp") or info_dict.get("HGVS_P") or info_dict.get("HGVSP")

            # 5. Fallback: ref>alt
            if not mutation:
                mutation = f"{ref}>{alt}"

            variants.append({
                "chrom": chrom,
                "pos": pos,
                "id": var_id,
                "ref": ref,
                "alt": alt,
                "gene": gene.upper(),
                "mutation": _normalize_mutation(mutation)
            })
        return variants

    @staticmethod
    # Queries the SQLite clinical knowledge base for matching evidence by gene and mutation
    def match_clinical_evidence(gene: str, mutation: str):
        with closing(sqlite3.connect(DB_PATH)) as conn:
            cursor = conn.cursor()

            # 1. Dynamically inspect table columns to find the mutation column name
            cursor.execute("PRAGMA table_info(variant_evidence)")
            columns = [col[1].lower() for col in cursor.fetchall()]

            # Determine exact mutation column name used in SQLite table
            mut_col = "mutation"
            if "variant" in columns:
                mut_col = "variant"
            elif "alteration" in columns:
                mut_col = "alteration"

            # 2. Query matching BOTH gene and mutation first
            query = f"""
                SELECT DISTINCT disease, therapy, evidence_tier, source
                FROM variant_evidence
                WHERE UPPER(gene) = UPPER(?) AND UPPER({mut_col}) = UPPER(?)
            """
            cursor.execute(query, (gene, _normalize_mutation(mutation)))
            rows = cursor.fetchall()

            # 3. Fallback: Query by gene only if no exact mutation match is found
            if not rows:
                cursor.execute(
                    """
                    SELECT DISTINCT disease, therapy, evidence_tier, source
                    FROM variant_evidence
                    WHERE UPPER(gene) = UPPER(?)
                    LIMIT 10
                    """,
                    (gene,)
                )
                rows = cursor.fetchall()

        if not rows:
            return [{
                "disease": "No Direct Match",
                "therapy": "Standard Protocol",
                "evidence_tier": "Unclassified",
                "source": "N/A"
            }]

        # 4. Build records (DISTINCT already dedupes; keep order stable)
        return [
            {"disease": r[0], "therapy": r[1], "evidence_tier": r[2], "source": r[3]}
            for r in rows
        ]
