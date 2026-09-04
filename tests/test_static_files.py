import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app, STATIC_DIR, TEMPLATES_DIR


@pytest.mark.asyncio
async def test_static_css_file_served(client: AsyncClient):
    """Verify that GET /static/css/style.css returns HTTP 200 with text/css."""
    response = await client.get("/static/css/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers.get("content-type", "")
    assert len(response.text) > 1000
    assert ":root" in response.text or "body" in response.text


@pytest.mark.asyncio
async def test_static_js_file_served(client: AsyncClient):
    """Verify that GET /static/js/main.js returns HTTP 200 with javascript content type."""
    response = await client.get("/static/js/main.js")
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "")
    assert len(response.text) > 500


@pytest.mark.asyncio
async def test_static_images_served(client: AsyncClient):
    """Verify that all sample JPG images are accessible and return image/jpeg."""
    for img_name in ["sample-morning.jpg", "sample-resilience.jpg", "sample-growth.jpg"]:
        response = await client.get(f"/static/images/{img_name}")
        assert response.status_code == 200, f"Failed to serve /static/images/{img_name}"
        assert "image/jpeg" in response.headers.get("content-type", "")
        assert len(response.content) > 10000


@pytest.mark.asyncio
async def test_static_nonexistent_returns_404(client: AsyncClient):
    """Verify that requesting a nonexistent static asset correctly returns 404."""
    response = await client.get("/static/css/nonexistent_file.css")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_home_page_rendered_static_links(client: AsyncClient):
    """Verify that the home page renders static CSS, JS, and image URLs properly."""
    response = await client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "/static/css/style.css" in html
    assert "/static/js/main.js" in html
    assert "/static/images/sample-morning.jpg" in html
    assert "/static/images/sample-resilience.jpg" in html
    assert "/static/images/sample-growth.jpg" in html


@pytest.mark.asyncio
async def test_sample_email_rendered_static_links(client: AsyncClient):
    """Verify that the sample email page renders static CSS, JS, and image URLs properly."""
    response = await client.get("/sample-email")
    assert response.status_code == 200
    html = response.text
    assert "/static/css/style.css" in html
    assert "/static/js/main.js" in html
    assert "/static/images/sample-morning.jpg" in html


@pytest.mark.asyncio
async def test_all_pages_include_css_stylesheet(client: AsyncClient):
    """Verify that all HTML template endpoints include the static CSS stylesheet."""
    endpoints = [
        "/",
        "/features",
        "/how-it-works",
        "/sample-email",
        "/about",
        "/verify",
        "/success",
        "/preferences",
        "/unsubscribe",
    ]
    for endpoint in endpoints:
        response = await client.get(endpoint)
        assert response.status_code == 200, f"Failed on endpoint {endpoint}"
        assert "/static/css/style.css" in response.text, f"CSS stylesheet missing on {endpoint}"


@pytest.mark.asyncio
async def test_static_directory_paths_validity():
    """Verify that STATIC_DIR and TEMPLATES_DIR are resolved to existing directories."""
    assert STATIC_DIR.exists(), f"STATIC_DIR does not exist: {STATIC_DIR}"
    assert STATIC_DIR.is_dir(), f"STATIC_DIR is not a directory: {STATIC_DIR}"
    assert (STATIC_DIR / "css" / "style.css").exists(), "style.css missing in STATIC_DIR/css"
    assert (STATIC_DIR / "js" / "main.js").exists(), "main.js missing in STATIC_DIR/js"
    assert TEMPLATES_DIR.exists(), f"TEMPLATES_DIR does not exist: {TEMPLATES_DIR}"
    assert (TEMPLATES_DIR / "base.html").exists(), "base.html missing in TEMPLATES_DIR"


@pytest.mark.asyncio
async def test_https_proxy_headers_support():
    """Verify that ProxyHeadersMiddleware processes X-Forwarded-Proto https headers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"x-forwarded-proto": "https", "x-forwarded-for": "20.119.0.1"}
    ) as https_client:
        response = await https_client.get("/")
        assert response.status_code == 200
        # When x-forwarded-proto is https, url_for generates https:// URL
        assert "https://" in response.text
        assert "https://test/static/css/style.css" in response.text or "/static/css/style.css" in response.text
