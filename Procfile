release: python manage.py migrate
web: gunicorn ecommerce.wsgi:application --bind 0.0.0.0:$PORT --workers 3
