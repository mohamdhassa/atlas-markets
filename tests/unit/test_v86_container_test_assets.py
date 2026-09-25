from pathlib import Path


def test_docker_image_includes_test_referenced_assets():
    dockerfile = Path("Dockerfile").read_text()
    assert "COPY README.md /app/README.md" in dockerfile
    assert "COPY docs /app/docs" in dockerfile
    assert "COPY ops /app/ops" in dockerfile
