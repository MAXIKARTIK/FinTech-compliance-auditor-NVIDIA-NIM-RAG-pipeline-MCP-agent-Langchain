"""Multi-tenant isolation (R2): a query for company A must never return B's chunks."""

from app.services.retriever import build_where, retrieve

class FakeEmbeddings:
    def embed_query(self, text):
        return [0.0, 0.0, 0.0]

    def embed_documents(self, docs):
        return [[0.0, 0.0, 0.0] for _ in docs]

class FakeCollection:
    def __init__(self):
        self.rows = []

    def upsert(self, ids, documents, metadatas):
        for i, d, m in zip(ids, documents, metadatas):
            self.rows.append((i, d, m))

    def _match(self, meta, where):
        for cond in where["$and"]:
            (field, spec), = cond.items()
            if meta.get(field) != spec["$eq"]:
                return False
        return True

    def query(self, query_embeddings=None, n_results=10, where=None, **kwargs):
        matched = [(i, d) for i, d, m in self.rows if self._match(m, where)][:n_results]
        return {"ids": [[i for i, _ in matched]], "documents": [[d for _, d in matched]]}

def test_cross_tenant_isolation():
    col = FakeCollection()
    col.upsert(["AAA-10-K-2023-FY-0"], ["Apple risk factors text"],
               [{"ticker": "AAA", "filing_type": "10-K", "fiscal_year": 2023, "fiscal_quarter": "FY"}])
    col.upsert(["BBB-10-K-2023-FY-0"], ["Beta corp risk factors text"],
               [{"ticker": "BBB", "filing_type": "10-K", "fiscal_year": 2023, "fiscal_quarter": "FY"}])
    a = retrieve(ticker="AAA", filing_type="10-K", fiscal_year=2023, fiscal_quarter="FY",
                 query="risk", collection=col, embeddings=FakeEmbeddings())
    assert len(a) == 1
    assert all(c["chunk_id"].startswith("AAA") for c in a)
    assert not any("BBB" in c["chunk_id"] for c in a)

def test_build_where_includes_all_tenant_keys():
    where = build_where("AAA", "10-Q", 2023, "Q1")
    fields = {list(c.keys())[0] for c in where["$and"]}
    assert fields == {"ticker", "filing_type", "fiscal_year", "fiscal_quarter"}
