import sqlite3
import os

DB_PATH = os.path.join("backend", "data", "raw", "clinical_kb.db")

class VariantAnnotationEngine:
    @staticmethod
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
            
            gene = info_dict.get("GENE", info_dict.get("SYMBOL", "UNKNOWN"))
            mutation = info_dict.get("MUT", info_dict.get("HGVSp", f"{ref}>{alt}"))
            
            variants.append({
                "chrom": chrom,
                "pos": pos,
                "gene": gene.upper(),
                "mutation": mutation.upper()
            })
        return variants

    @staticmethod
    def match_clinical_evidence(gene: str, mutation: str):
        conn = sqlite3.connect(DB_PATH)
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
        cursor.execute(query, (gene, mutation))
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

        conn.close()
        
        if not rows:
            return [{
                "disease": "No Direct Match",
                "therapy": "Standard Protocol",
                "evidence_tier": "Unclassified",
                "source": "N/A"
            }]
        
        # 4. Deduplicate matching records
        unique_matches = []
        seen = set()
        
        for r in rows:
            record_tuple = (r[0], r[1], r[2], r[3])
            if record_tuple not in seen:
                seen.add(record_tuple)
                unique_matches.append({
                    "disease": r[0],
                    "therapy": r[1],
                    "evidence_tier": r[2],
                    "source": r[3]
                })
        
        return unique_matches