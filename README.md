# Flask Product API

A simple REST API built with Flask. Products are stored in a local SQLite
database.

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer
- Git Bash (included with [Git for Windows](https://gitforwindows.org/))

You can check that Python is installed by opening Git Bash and running:

```bash
python --version
```

If Windows cannot find Python, install it from
[python.org](https://www.python.org/downloads/windows/) and enable the
**Add Python to PATH** option during installation.

## Setup on Windows

Open Git Bash and move into the downloaded project folder. Git Bash uses paths
such as `/c/Users/YourName/...` for folders located on the Windows `C:` drive.
Replace the path below with the actual project location on your computer:

```bash
cd /c/path/to/FlaskAPI
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate the virtual environment:

```bash
source .venv/Scripts/activate
```

When the environment is active, `(.venv)` appears at the beginning of the
Git Bash prompt.

Install the project dependencies:

```bash
python -m pip install -r requirements.txt
```

## Start the application

Make sure the virtual environment is active, then run:

```bash
flask --app app run --debug
```

The API starts at:

```text
http://127.0.0.1:5000
```

Open that address in a web browser to view the simple product list page. The
page fetches its data from the product API automatically.

The SQLite database is created automatically at `instance/products.db` when
the application starts. If the product table is empty, the application also
adds one example product automatically. Existing products are never replaced.

Stop the application by pressing `Ctrl+C` in Git Bash. To leave the virtual
environment, run:

```bash
deactivate
```

## Product endpoint

Products are fetched from this path:

```text
GET http://127.0.0.1:5000/api/products
```

You can open that address in a browser or fetch the products from Git Bash:

```bash
curl http://127.0.0.1:5000/api/products
```

The response is a JSON array. A new database contains one automatically created
example product:

```json
[
  {
    "id": 1,
    "name": "Example product",
    "description": "This product was created automatically for demonstration.",
    "price": 9.99,
    "stock": 10,
    "sku": "EXAMPLE-001",
    "created_at": "...",
    "updated_at": "..."
  }
]
```

## API routes

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/products` | Get all products |
| `GET` | `/api/products/<id>` | Get one product |
| `POST` | `/api/products` | Create a product |
| `PUT` or `PATCH` | `/api/products/<id>` | Update a product |
| `DELETE` | `/api/products/<id>` | Delete a product |

Example product JSON:

```json
{
  "name": "Coffee mug",
  "description": "White porcelain mug",
  "price": 12.90,
  "stock": 15,
  "sku": "MUG-001"
}
```

Example: create a product from Git Bash:

```bash
curl -X POST http://127.0.0.1:5000/api/products \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Coffee mug",
    "description": "White porcelain mug",
    "price": 12.90,
    "stock": 15,
    "sku": "MUG-001"
  }'
```

## Run the tests

With the virtual environment active, run:

```bash
python -m pytest
```
