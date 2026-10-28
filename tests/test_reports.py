from tests.conftest import login


def test_csv_export(client):
    login(client, "admin@test.local")
    response = client.get("/admin/reports/export.csv")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert b"Reference,Title" in response.data
