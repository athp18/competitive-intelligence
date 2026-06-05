from core.dedup import canonicalize_url, content_hash


def test_strip_utm():
    url = "https://example.com/article?utm_source=twitter&utm_medium=social&id=123"
    canonical = canonicalize_url(url)
    assert "utm_source" not in canonical
    assert "id=123" in canonical


def test_canonicalize_removes_fragment():
    url = "https://example.com/post#comments"
    assert "#" not in canonicalize_url(url)


def test_content_hash_stable():
    h1 = content_hash("Title", "https://example.com/article")
    h2 = content_hash("Title", "https://example.com/article")
    assert h1 == h2


def test_content_hash_strips_utm():
    h1 = content_hash("Title", "https://example.com/article")
    h2 = content_hash("Title", "https://example.com/article?utm_source=x")
    assert h1 == h2


def test_content_hash_different_titles():
    h1 = content_hash("Title A", "https://example.com/article")
    h2 = content_hash("Title B", "https://example.com/article")
    assert h1 != h2
