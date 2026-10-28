import io

from tests.conftest import login


def test_attachment_extension_validation(client):
    login(client, "reporter@test.local")
    data = {"title": "Bad file", "description": "x", "category": "Other", "building": "D", "room_location": "1", "priority": "Low", "image": (io.BytesIO(b"not-image"), "bad.txt")}
    response = client.post("/reporter/complaints/new", data=data, content_type="multipart/form-data")
    assert b"Images only" in response.data


def test_attachment_size_validation(client):
    login(client, "reporter@test.local")
    data = {"title": "Big file", "description": "x", "category": "Other", "building": "D", "room_location": "1", "priority": "Low", "image": (io.BytesIO(b"x" * (6 * 1024 * 1024)), "big.jpg")}
    response = client.post("/reporter/complaints/new", data=data, content_type="multipart/form-data")
    assert response.status_code in (400, 413)
