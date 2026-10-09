"""Application setup and HTTP routes for the Product API.

This module creates the Flask application, connects it to the database, and
defines all endpoints used to create, read, update, and delete products.
"""

import os
from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify, request, send_from_directory
from sqlalchemy.exc import IntegrityError

from models import Product, db


def create_app(test_config=None):
    """Create and configure a Flask application instance.

    Keeping application creation inside a function is known as the application
    factory pattern. It lets the production server and the test suite create
    separate application instances with different configuration values.

    Args:
        test_config: Optional settings that override the normal configuration.
            The test suite uses this to select an in-memory SQLite database.

    Returns:
        A fully configured Flask application.
    """

    # instance_relative_config=True gives Flask an instance folder intended for
    # local runtime data. The SQLite file is stored there instead of beside the
    # source files.
    app = Flask(__name__, instance_relative_config=True)

    # A fresh checkout does not contain the ignored instance folder, so create
    # it before SQLAlchemy attempts to open the database file inside it.
    os.makedirs(app.instance_path, exist_ok=True)

    default_database = os.path.join(app.instance_path, "products.db")

    # DATABASE_URL can be used to select another database without editing the
    # source. If it is not provided, the application uses the local SQLite file.
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL", f"sqlite:///{default_database}"
        ),
        # Flask-SQLAlchemy's legacy event system is not needed and would add
        # unnecessary overhead.
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # A newly created database receives one product so the browser page and
        # API immediately have something useful to display.
        SEED_SAMPLE_PRODUCT=True,
    )

    # Tests supply their own database configuration here. Using update keeps
    # the normal defaults while replacing only the requested values.
    if test_config:
        app.config.update(test_config)

    # Connect the shared SQLAlchemy object from models.py to this Flask app.
    db.init_app(app)

    # Database operations need an application context. create_all() creates
    # missing tables but leaves existing tables and data untouched.
    with app.app_context():
        db.create_all()

        # Tests can disable seeding to start each case from a completely empty
        # database. Normal application instances keep this setting enabled.
        if app.config["SEED_SAMPLE_PRODUCT"]:
            seed_sample_product()

    @app.get("/")
    def index():
        """Serve the small browser interface from the project directory."""

        # app.root_path points to the folder containing app.py. Keeping the HTML
        # there makes this example easy to find and avoids a separate frontend
        # build process.
        return send_from_directory(app.root_path, "index.html")

    @app.get("/api/products")
    def list_products():
        """Return every product ordered by its database ID."""

        # scalars() unwraps SQLAlchemy row objects into Product instances.
        products = db.session.execute(
            db.select(Product).order_by(Product.id)
        ).scalars()

        # jsonify converts the list of dictionaries into a JSON response and
        # sets the correct application/json content type.
        return jsonify([product.to_dict() for product in products])

    @app.get("/api/products/<int:product_id>")
    def get_product(product_id):
        """Return one product or a JSON 404 response when it does not exist."""

        # get_or_404 performs a primary-key lookup and stops the request with a
        # 404 error if no matching row exists.
        product = db.get_or_404(Product, product_id)
        return jsonify(product.to_dict())

    @app.post("/api/products")
    def create_product():
        """Validate a JSON request and insert a new product."""

        # silent=True makes invalid or missing JSON return None. This allows the
        # API to send its own consistent error message instead of an HTML page.
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Pyynnön rungon pitää olla JSON-olio."}), 400

        # Validate everything before constructing a model or changing the
        # database session. All field errors are returned in one response.
        errors = validate_product(data)
        if errors:
            return jsonify({"errors": errors}), 400

        # Decimal is used for money to avoid binary floating-point rounding.
        # Optional strings are normalized so blank values become database NULL.
        product = Product(
            name=data["name"].strip(),
            description=clean_optional_string(data.get("description")),
            price=Decimal(str(data["price"])),
            stock=data.get("stock", 0),
            sku=clean_optional_string(data.get("sku")),
        )
        db.session.add(product)

        try:
            # Committing writes the pending INSERT to SQLite and populates the
            # generated product ID on the model instance.
            db.session.commit()
        except IntegrityError:
            # The most likely constraint violation is a duplicate SKU. A failed
            # SQLAlchemy session must be rolled back before it can be reused.
            db.session.rollback()
            return jsonify({"error": "SKU on jo käytössä."}), 409

        # HTTP 201 Created indicates that a new resource was successfully made.
        return jsonify(product.to_dict()), 201

    @app.route("/api/products/<int:product_id>", methods=["PUT", "PATCH"])
    def update_product(product_id):
        """Update an existing product using PUT or PATCH."""

        product = db.get_or_404(Product, product_id)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Pyynnön rungon pitää olla JSON-olio."}), 400

        # PATCH is a partial update, so it does not require name and price.
        # PUT expects those required fields, although omitted optional fields
        # retain their current values in this compact API.
        partial = request.method == "PATCH"
        errors = validate_product(data, partial=partial)
        if errors:
            return jsonify({"errors": errors}), 400

        # Only assign fields included by the client. This is what allows PATCH
        # to change one property without overwriting the remaining properties.
        if "name" in data:
            product.name = data["name"].strip()
        if "description" in data:
            product.description = clean_optional_string(data["description"])
        if "price" in data:
            product.price = Decimal(str(data["price"]))
        if "stock" in data:
            product.stock = data["stock"]
        if "sku" in data:
            product.sku = clean_optional_string(data["sku"])

        try:
            db.session.commit()
        except IntegrityError:
            # Return a conflict instead of exposing a low-level database error.
            db.session.rollback()
            return jsonify({"error": "SKU on jo käytössä."}), 409

        return jsonify(product.to_dict())

    @app.delete("/api/products/<int:product_id>")
    def delete_product(product_id):
        """Delete one product and return an empty success response."""

        product = db.get_or_404(Product, product_id)
        db.session.delete(product)
        db.session.commit()

        # A successful DELETE commonly uses 204 No Content, which must not have
        # a JSON response body.
        return "", 204

    @app.errorhandler(404)
    def not_found(_error):
        """Convert all application 404 errors into a consistent JSON format."""

        return jsonify({"error": "Resurssia ei löytynyt."}), 404

    return app


def clean_optional_string(value):
    """Trim an optional string and convert an empty string into None."""

    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def seed_sample_product():
    """Insert one example product when the product table is empty.

    This function is safe to call every time the application starts. It checks
    for an existing row first, so it never adds duplicate example products and
    never changes data that is already present in the database.
    """

    # Selecting only the ID is enough to determine whether at least one product
    # exists and avoids loading a complete product row unnecessarily.
    existing_product_id = db.session.execute(
        db.select(Product.id).limit(1)
    ).scalar_one_or_none()

    if existing_product_id is not None:
        return

    sample_product = Product(
        name="Example product",
        description="This product was created automatically for demonstration.",
        price=Decimal("9.99"),
        stock=10,
        sku="EXAMPLE-001",
    )
    db.session.add(sample_product)
    db.session.commit()


def validate_product(data, partial=False):
    """Validate incoming product data and return field-specific errors.

    Args:
        data: The decoded JSON object supplied by the client.
        partial: When True, required fields may be omitted for a PATCH request.

    Returns:
        A dictionary of validation errors. An empty dictionary means that the
        supplied data is valid.
    """

    errors = {}

    # Reject misspelled or unsupported properties instead of silently ignoring
    # them. This makes client-side integration errors easier to notice.
    allowed_fields = {"name", "description", "price", "stock", "sku"}
    unknown_fields = sorted(set(data) - allowed_fields)
    if unknown_fields:
        errors["unknown_fields"] = (
            "Tuntemattomat kentät: " + ", ".join(unknown_fields)
        )

    # A complete POST or PUT payload needs a name and price. PATCH requests can
    # omit them because the existing values remain unchanged.
    required_fields = ("name", "price")
    if not partial:
        for field in required_fields:
            if field not in data:
                errors[field] = "Kenttä on pakollinen."

    # Names must contain visible characters and fit in the model's VARCHAR(120)
    # database column.
    if "name" in data:
        if not isinstance(data["name"], str) or not data["name"].strip():
            errors["name"] = "Nimen pitää olla ei-tyhjä merkkijono."
        elif len(data["name"].strip()) > 120:
            errors["name"] = "Nimi saa olla enintään 120 merkkiä."

    if "description" in data and data["description"] is not None:
        if not isinstance(data["description"], str):
            errors["description"] = "Kuvauksen pitää olla merkkijono tai null."

    if "price" in data:
        # bool is a subclass of int in Python, so it must be rejected explicitly
        # before numeric conversion.
        if isinstance(data["price"], bool):
            errors["price"] = "Hinnan pitää olla ei-negatiivinen luku."
        else:
            try:
                price = Decimal(str(data["price"]))

                # Reject negative values as well as NaN and infinity, which the
                # Decimal constructor otherwise accepts.
                if not price.is_finite() or price < 0:
                    raise ValueError

                # The database stores two decimal places, so reject extra
                # precision rather than rounding a client's value silently.
                if price.as_tuple().exponent < -2:
                    errors["price"] = "Hinnassa saa olla enintään kaksi desimaalia."
            except (InvalidOperation, ValueError):
                errors["price"] = "Hinnan pitää olla ei-negatiivinen luku."

    if "stock" in data:
        if (
            isinstance(data["stock"], bool)
            or not isinstance(data["stock"], int)
            or data["stock"] < 0
        ):
            errors["stock"] = "Varastosaldon pitää olla ei-negatiivinen kokonaisluku."

    if "sku" in data and data["sku"] is not None:
        # SKU is optional, but a supplied value must match the database column's
        # type and maximum length. Uniqueness is enforced by the database.
        if not isinstance(data["sku"], str):
            errors["sku"] = "SKU:n pitää olla merkkijono tai null."
        elif len(data["sku"].strip()) > 64:
            errors["sku"] = "SKU saa olla enintään 64 merkkiä."

    return errors


# WSGI servers and the `flask --app app` command look for this module-level
# variable. Calling the factory here creates the normal application instance.
app = create_app()


if __name__ == "__main__":
    # This block runs only when executing `python app.py` directly. The debug
    # server automatically reloads code and shows detailed local error pages;
    # it should not be used as a production web server.
    app.run(debug=True)
