# E-Commerce App

A backend-focused e-commerce web app built with Django and PostgreSQL. Users can browse products, fill a cart, and pay through Stripe Checkout (test mode). The project ships with a Dockerfile, a Docker Compose setup, and a GitHub Actions pipeline that lints, tests, and builds the image.

## Features

- User sign up, login, and logout
- Product list with search, category filter, and pagination
- Shopping cart with stock checks (you cannot add more than what is in stock)
- Stripe Checkout payment flow, confirmed both on the success page and by a signed webhook
- Safe stock handling: database row locks (`select_for_update`) inside atomic transactions, so two buyers cannot take the last item
- Duplicate-payment protection: each order stores its Stripe session ID in a unique column
- Order history with payment status (`pending`, `paid`, `failed`, `refunded`)
- Django admin for managing products, categories, and orders
- `/health/` endpoint for health checks

## Tech Stack

| Area | Tools |
| --- | --- |
| Backend | Python 3.12, Django 6 |
| Database | PostgreSQL 15 |
| Payments | Stripe Checkout + webhooks |
| Static files | WhiteNoise |
| Server | Gunicorn |
| Containers | Docker (multi-stage build, non-root user), Docker Compose |
| CI | GitHub Actions: Ruff lint, tests on PostgreSQL, Docker image pushed to GHCR |

## Quick Start with Docker

**1. Create a `.env` file** in the project root:

```dotenv
DEBUG=True
SECRET_KEY=put-a-long-random-string-here
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=ecommerce
DB_USER=postgres
DB_PASSWORD=choose-a-password

STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

`DB_HOST` and `DB_PORT` are set by `docker-compose.yml`, so you do not need them here. Never commit `.env`.

**2. Start everything:**

```bash
docker compose up --build
```

On startup the web container runs migrations, collects static files, and starts Gunicorn.

**3. Create an admin user** (in a second terminal):

```bash
docker compose exec web python manage.py createsuperuser
```

**4. Open the app:**

- Store: <http://localhost:8000>
- Admin: <http://localhost:8000/admin/> (add categories and products here first)
- Health check: <http://localhost:8000/health/>

## Run Without Docker

You need Python 3.12 and a running PostgreSQL server.

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file like the one above, but set `DB_HOST=localhost` and `DB_PORT=5432`. Then:

```bash
python manage.py migrate
python manage.py runserver
```

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `SECRET_KEY` | Yes | Django secret key. Use a long random value. |
| `DEBUG` | No | `True` for local work. Defaults to `False`. |
| `ALLOWED_HOSTS` | No | Comma-separated hosts. Defaults to `127.0.0.1,localhost`. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Yes | PostgreSQL credentials. |
| `DB_HOST`, `DB_PORT` | No | Default to `localhost` and `5432`. |
| `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY` | Yes | From the [Stripe dashboard](https://dashboard.stripe.com/apikeys). Use test keys. |
| `STRIPE_WEBHOOK_SECRET` | For webhooks | Printed by `stripe listen` (see below). |

## Testing Stripe Locally

1. Use your Stripe **test** keys in `.env`.
2. Install the [Stripe CLI](https://docs.stripe.com/stripe-cli) and forward webhooks to the app:

   ```bash
   stripe listen --forward-to localhost:8000/stripe/webhook/
   ```

3. Copy the `whsec_...` value it prints into `STRIPE_WEBHOOK_SECRET` and restart the web container.
4. Pay with the test card `4242 4242 4242 4242`, any future expiry date, and any CVC.

## Tests and Linting

The test suite covers boundary values for stock, cart quantity, product price, and checkout.

```bash
# Inside Docker
docker compose exec web python manage.py test

# Without PostgreSQL (uses SQLite)
python manage.py test --settings=ecommerce.test_settings

# Lint
pip install -r requirements-dev.txt
ruff check .
```

## CI Pipeline

`.github/workflows/ci.yml` runs on every push and pull request to `main`:

1. **lint**: Ruff
2. **test**: `manage.py test` against a PostgreSQL service container
3. **build**: builds the Docker image and, on pushes to `main`, publishes it to GitHub Container Registry

## Project Structure

```
.
├── accounts/        # sign up, login, logout
├── store/           # products, cart, checkout, orders, Stripe webhook
├── ecommerce/       # project settings, URLs, WSGI
├── scripts/         # helper shell scripts
├── dockerfile       # multi-stage build, runs as a non-root user
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## Main Routes

| Route | Purpose |
| --- | --- |
| `/products/` | Product list, search, filter |
| `/cart/` | View and edit the cart |
| `/checkout/` | Start a Stripe Checkout session |
| `/checkout/success/` | Confirm payment and finalize the order |
| `/orders/` | Order history |
| `/stripe/webhook/` | Stripe webhook receiver |
| `/accounts/login/`, `/accounts/sign_up/` | Authentication |
| `/health/` | Health check |

## Known Limitations

- Uploaded product images are served by Django only when `DEBUG=True`. For production, serve `/media/` from a reverse proxy (such as Nginx) or object storage.
- Stripe runs in test mode only.

## Author

Built by Guirgis, a software engineering student focused on DevOps and platform engineering.

- GitHub: [guirgisyoussef12-source](https://github.com/guirgisyoussef12-source)
- LinkedIn: [guirgis-youssef](https://www.linkedin.com/in/guirgis-youssef-2542ba305)