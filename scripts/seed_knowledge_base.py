#!/usr/bin/env python3
"""
TruthLens AI – Knowledge Base Seeder
Ingest custom trusted documents into ChromaDB from a JSONL file.

Usage:
  python scripts/seed_knowledge_base.py --input data/trusted_docs.jsonl

Each line of the JSONL file must be a JSON object:
  { "id": "doc_001", "text": "...", "source": "https://..." }
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure the backend package is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def main():
    parser = argparse.ArgumentParser(description="Seed TruthLens ChromaDB knowledge base")
    parser.add_argument("--input", required=True, help="Path to JSONL file")
    parser.add_argument("--clear", action="store_true", help="Clear existing collection first")
    args = parser.parse_args()

    from app.rag_pipeline import RagPipeline

    print("Initialising RAG pipeline…")
    pipeline = RagPipeline()

    if args.clear and pipeline._collection:
        count = pipeline._collection.count()
        pipeline._chroma_client.delete_collection(pipeline.COLLECTION_NAME)
        print(f"Cleared {count} existing documents.")
        # Re-init the collection
        pipeline._init_chroma()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    ingested = 0
    errors = 0

    with open(input_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
                doc_id = doc["id"]
                text = doc["text"]
                source = doc.get("source", "Unknown")

                if len(text) < 10:
                    print(f"  Line {line_no}: SKIP – text too short")
                    continue

                pipeline.ingest(doc_id=doc_id, text=text, source=source)
                ingested += 1
                if ingested % 100 == 0:
                    print(f"  Ingested {ingested} documents…")

            except (json.JSONDecodeError, KeyError) as e:
                print(f"  Line {line_no}: ERROR – {e}")
                errors += 1

    print(f"\n✅ Done. Ingested: {ingested} | Errors: {errors}")
    if pipeline._collection:
        print(f"   Collection total: {pipeline._collection.count()} documents")


if __name__ == "__main__":
    main()
