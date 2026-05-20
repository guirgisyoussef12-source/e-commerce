# E-Commerce App

Built with Django and PostgreSQL to practice backend development.
Users can browse products, manage a cart, and place orders.

## Features
- User registration and authentication
- Product browsing, search, and category filtering
- Shopping cart (add / remove items)
- Stock management — stock decrements automatically after checkout
- Order checkout with atomic transactions
- Order history

## Stack
- Python / Django
- PostgreSQL
- Docker

## Run with Docker
```bash
cp .env.example .env
docker-compose up --build
```

## Run locally
```bash
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

## Environment Variables
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432

## Running Tests
```bash
python manage.py test
```
