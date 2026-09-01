"""Phase V2-1 LIVE verification - the product catalogue foundation.

Run AFTER applying migrations 006 and 006b in the Supabase SQL Editor
and creating the public 'product-images' bucket:

    python check_products.py

It verifies: pgvector is enabled, both tables exist, the match_products
search function works (using a synthetic test vector), the public bucket
exists, and cleans up its test rows. All green = Phase V2-1 complete.
"""
from __future__ import annotations

import sys

OK = "  [OK]  "
FAIL = "  [FAIL]"


def main() -> int:
    from app import create_app

    app = create_app()
    with app.app_context():
        from app.db import queries
        from app.db.supabase_client import get_supabase

        sb = get_supabase()
        print("HueFit v2 - product catalogue check")
        print("=" * 52)

        # 1) tables exist
        for t in ("catalog_clients", "products"):
            try:
                sb.table(t).select("*", count="exact").limit(0).execute()
                print(f"{OK} table '{t}' exists")
            except Exception as e:
                print(f"{FAIL} table '{t}' missing -> run migrations/006_products.sql")
                print(f"        ({type(e).__name__}: {str(e)[:110]})")
                return 1

        # 2) client upsert
        try:
            client = queries.get_or_create_client("v2-check")
            print(f"{OK} client row created ({client['id'][:8]}...)")
        except Exception as e:
            print(f"{FAIL} client creation failed: {e}")
            return 1

        # 3) product upsert WITH a synthetic 512-dim vector
        test_vec = [0.0] * 512
        test_vec[0] = 1.0
        try:
            prod = queries.upsert_product(
                client["id"],
                {
                    "title": "V2 CHECK - Test Maroon Saree",
                    "gender": "female",
                    "dress_type": "saree",
                    "culture": "tamil",
                    "occasions": ["festive"],
                    "dominant_hex": "#973922",
                    "hue_family": "maroon-red",
                    "tags": ["test"],
                    "price": 1.0,
                    "image_url": "https://example.com/test.jpg",
                    "embedding": test_vec,
                    "indexed_at": "now()",
                },
            )
            print(f"{OK} product row with 512-dim vector stored")
        except Exception as e:
            print(f"{FAIL} product insert failed (pgvector enabled?): {str(e)[:140]}")
            return 1

        # 4) vector search via match_products
        try:
            hits = queries.search_products_by_vector(
                test_vec, gender="female", culture="tamil", occasion="festive", limit=3
            )
            found = any(h["title"].startswith("V2 CHECK") for h in hits)
            if found and hits[0]["similarity"] > 0.99:
                print(f"{OK} match_products search works (similarity {hits[0]['similarity']:.3f})")
            else:
                print(f"{FAIL} search returned no/low  match -> run migrations/006b_match_products.sql")
                return 1
        except Exception as e:
            print(f"{FAIL} match_products missing -> run migrations/006b_match_products.sql")
            print(f"        ({type(e).__name__}: {str(e)[:110]})")
            return 1

        # 5) public bucket
        try:
            buckets = {b.name: b for b in sb.storage.list_buckets()}
            if "product-images" in buckets:
                pub = getattr(buckets["product-images"], "public", None)
                if pub:
                    print(f"{OK} bucket 'product-images' exists and is PUBLIC")
                else:
                    print(f"{FAIL} bucket 'product-images' exists but is PRIVATE -> toggle Public ON")
                    return 1
            else:
                try:
                    sb.storage.create_bucket("product-images", options={"public": True})
                    print(f"{OK} bucket 'product-images' created (public)")
                except Exception:
                    print(f"{FAIL} bucket 'product-images' missing -> create it: Storage -> New bucket -> Public ON")
                    return 1
        except Exception as e:
            print(f"{FAIL} storage check failed: {str(e)[:120]}")
            return 1

        # 6) cleanup test rows
        try:
            sb.table("products").delete().eq("client_id", client["id"]).execute()
            sb.table("catalog_clients").delete().eq("id", client["id"]).execute()
            print(f"{OK} test rows cleaned up")
        except Exception:
            print("  [WARN] cleanup incomplete (harmless - delete 'v2-check' client in dashboard)")

        print("=" * 52)
        print("All checks passed - Phase V2-1 complete! Next: V2-2 (CLIP + indexer).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
