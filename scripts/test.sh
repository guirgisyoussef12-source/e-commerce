#!/bin/bash
set -e

echo "=== 🧪 [1/5] Running Project Boundary Value Tests ==="

docker-compose exec -T web python manage.py test

echo " All Boundary Tests Passed Successfully!"