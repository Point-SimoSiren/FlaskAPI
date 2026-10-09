"""Automated tests for the Product API's main behavior and validation."""

import pytest

from app import create_app
from models import Product, db


@pytest.fixture()
def client():
    """Create an isolated API client backed by a temporary in-memory database."""

    # SQLite's in-memory mode prevents tests from reading or changing the real
    # instance/products.db file used when the application runs normally.
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            # CRUD tests need an empty database so their row counts remain
            # deterministic. Seeding itself is tested separately below.
            "SEED_SAMPLE_PRODUCT": False,
        }
    )

    # Flask's test client sends requests directly to the application without
    # starting a real network server.
    with app.test_client() as client:
        yield client

    # Remove the test schema after each test so no state can leak into the next
    # test case.
    with app.app_context():
        db.drop_all()


def test_product_crud(client):
    """Verify the complete create, list, update, and delete lifecycle."""

    # Start by creating a product and retain its generated ID for later calls.
    create_response = client.post(
        "/api/products",
        json={
            "name": "Kahvikuppi",
            "description": "Valkoinen posliinikuppi",
            "price": 12.90,
            "stock": 15,
            "sku": "KUPPI-001",
        },
    )
    assert create_response.status_code == 201
    product_id = create_response.get_json()["id"]

    # The newly created product should now appear in the collection endpoint.
    list_response = client.get("/api/products")
    assert list_response.status_code == 200
    assert len(list_response.get_json()) == 1

    # PATCH should update only stock and preserve all other product fields.
    update_response = client.patch(
        f"/api/products/{product_id}", json={"stock": 10}
    )
    assert update_response.status_code == 200
    assert update_response.get_json()["stock"] == 10

    # After deletion the endpoint returns 204, and fetching the same ID must
    # produce a 404 response.
    delete_response = client.delete(f"/api/products/{product_id}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/products/{product_id}").status_code == 404


def test_index_serves_product_page(client):
    """Verify that the root URL serves the browser product list."""

    response = client.get("/")
    assert response.status_code == 200
    assert response.content_type.startswith("text/html")
    assert b'<ul id="product-list"' in response.data


def test_empty_database_receives_sample_product():
    """Verify that application startup seeds exactly one example product."""

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SEED_SAMPLE_PRODUCT": True,
        }
    )

    with app.app_context():
        products = db.session.execute(db.select(Product)).scalars().all()

        assert len(products) == 1
        assert products[0].name == "Example product"
        assert products[0].sku == "EXAMPLE-001"

        db.drop_all()


# Running one test with several payloads keeps the validation cases concise
# while still reporting each invalid input as a separate pytest case.
@pytest.mark.parametrize(
    "payload, field",
    [
        ({"price": 10}, "name"),
        ({"name": "Tuote"}, "price"),
        ({"name": "Tuote", "price": -1}, "price"),
        ({"name": "Tuote", "price": 1, "stock": -1}, "stock"),
    ],
)
def test_product_validation(client, payload, field):
    """Verify that invalid product values return useful field errors."""

    response = client.post("/api/products", json=payload)
    assert response.status_code == 400
    assert field in response.get_json()["errors"]


def test_sku_must_be_unique(client):
    """Verify that two products cannot use the same SKU."""

    product = {"name": "Tuote", "price": 5.50, "sku": "ABC-123"}
    assert client.post("/api/products", json=product).status_code == 201
    response = client.post("/api/products", json=product)
    assert response.status_code == 409
