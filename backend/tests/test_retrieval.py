"""Retrieval quality: hybrid search must put the right files on top."""


def test_jwt_query(demo_repo):
    sr = demo_repo.retriever.search("Where is JWT authentication implemented?", k=5)
    assert "app/auth/jwt.py" in sr.files


def test_invoice_query(demo_repo):
    sr = demo_repo.retriever.search("Where is the invoice calculation implemented?", k=5)
    assert "app/utils/invoice.py" in sr.files


def test_plural_stemming(demo_repo):
    sr = demo_repo.retriever.search("Where are tokens created?", k=5)
    assert "app/auth/jwt.py" in sr.files


def test_class_symbol_retrieval(demo_repo):
    sr = demo_repo.retriever.search("Which file defines the Product model?", k=5)
    assert "app/models/models.py" in sr.files


def test_route_chunk_wins_for_endpoint_queries(demo_repo):
    sr = demo_repo.retriever.search("Who handles POST /api/orders?", k=6)
    assert any(h.chunk["kind"] == "route" for h in sr.hits[:3])
