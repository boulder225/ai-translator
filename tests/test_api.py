from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from translator.api import app, translation_jobs


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_pdf_content():
    """Create sample PDF content."""
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 0\ntrailer\n<< /Root 1 0 R >>\n%%EOF"


@pytest.fixture
def sample_txt_file(tmp_path):
    """Create a sample text file."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("First paragraph.\n\nSecond paragraph.", encoding="utf-8")
    return file_path


def test_api_root(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_list_glossaries(client):
    """Test glossary listing endpoint."""
    response = client.get("/api/glossaries")
    assert response.status_code == 200
    data = response.json()
    assert "glossaries" in data
    assert isinstance(data["glossaries"], list)


def test_start_translation_creates_job(client, sample_txt_file):
    """Test that starting a translation creates a job with correct file."""
    # Clear any existing jobs
    translation_jobs.clear()
    
    with open(sample_txt_file, "rb") as f:
        file_content = f.read()
        file_hash = hashlib.md5(file_content).hexdigest()
    
    response = client.post(
        "/api/translate",
        files={"file": ("test.txt", file_content, "text/plain")},
        data={
            "source_lang": "fr",
            "target_lang": "en",
            "skip_memory": "true",
        },
    )
    
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert "status" in data
    assert data["status"] == "pending"
    
    job_id = data["job_id"]
    assert job_id in translation_jobs
    
    # Verify job has correct file hash
    job = translation_jobs[job_id]
    assert job["file_hash"] == file_hash
    assert job["source_lang"] == "fr"
    assert job["target_lang"] == "en"
    assert Path(job["input_path"]).exists()


def test_translation_job_isolation(client, tmp_path):
    """Test that each translation job uses isolated files."""
    translation_jobs.clear()
    
    # Create two different files
    file1 = tmp_path / "file1.txt"
    file1.write_text("Content from file 1", encoding="utf-8")
    
    file2 = tmp_path / "file2.txt"
    file2.write_text("Content from file 2", encoding="utf-8")
    
    # Start first translation
    with open(file1, "rb") as f:
        content1 = f.read()
        hash1 = hashlib.md5(content1).hexdigest()
    
    response1 = client.post(
        "/api/translate",
        files={"file": ("file1.txt", content1, "text/plain")},
        data={"source_lang": "fr", "target_lang": "en", "skip_memory": "true"},
    )
    assert response1.status_code == 202
    job_id1 = response1.json()["job_id"]
    
    # Start second translation
    with open(file2, "rb") as f:
        content2 = f.read()
        hash2 = hashlib.md5(content2).hexdigest()
    
    response2 = client.post(
        "/api/translate",
        files={"file": ("file2.txt", content2, "text/plain")},
        data={"source_lang": "fr", "target_lang": "en", "skip_memory": "true"},
    )
    assert response2.status_code == 202
    job_id2 = response2.json()["job_id"]
    
    # Verify jobs are different and have correct hashes
    assert job_id1 != job_id2
    assert translation_jobs[job_id1]["file_hash"] == hash1
    assert translation_jobs[job_id2]["file_hash"] == hash2
    assert translation_jobs[job_id1]["file_hash"] != translation_jobs[job_id2]["file_hash"]


def test_get_translation_status(client, sample_txt_file):
    """Test getting translation status."""
    translation_jobs.clear()
    
    with open(sample_txt_file, "rb") as f:
        file_content = f.read()
    
    # Start translation
    response = client.post(
        "/api/translate",
        files={"file": ("test.txt", file_content, "text/plain")},
        data={"source_lang": "fr", "target_lang": "en", "skip_memory": "true"},
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    
    # Get status
    status_response = client.get(f"/api/translate/{job_id}/status")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["job_id"] == job_id
    assert "status" in status_data


def test_get_nonexistent_job_status(client):
    """Test getting status for non-existent job."""
    response = client.get("/api/translate/nonexistent-id/status")
    assert response.status_code == 404


def test_cancel_translation(client, sample_txt_file):
    """Test cancelling a translation."""
    translation_jobs.clear()
    
    with open(sample_txt_file, "rb") as f:
        file_content = f.read()
    
    # Start translation
    response = client.post(
        "/api/translate",
        files={"file": ("test.txt", file_content, "text/plain")},
        data={"source_lang": "fr", "target_lang": "en", "skip_memory": "true"},
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    
    # Cancel translation
    cancel_response = client.post(f"/api/translate/{job_id}/cancel")
    assert cancel_response.status_code == 200
    
    # Verify job is marked as cancelled
    assert translation_jobs[job_id].get("cancelled", False) is True




