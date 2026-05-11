# E-Commerce App

I built this project to learn Django and practice backend development.
It's a simple e-commerce app where users can browse products,
search for them, and manage a shopping cart.

## What it does
- Register and log in
- Browse and search products
- Add and remove items from the cart

## Stack
- Python / Django
- PostgreSQL

## Run it locally

Clone the repo and install dependencies:
    pip install -r requirements.txt

Create a .env file:
    DB_NAME=yourdb
    DB_USER=youruser
    DB_PASSWORD=yourpassword
    DB_HOST=localhost
    DB_PORT=5432

Run migrations and start the server:
    python manage.py migrate
    python manage.py runserver