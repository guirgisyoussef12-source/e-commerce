#!/bin/bash
set -e

echo "=== 🧪 [1/5] Running Project Boundary Value Tests ==="

# 1) Docker شغال؟
if ! docker info > /dev/null 2>&1; then
    echo "⚠️  Docker is not running. Start Docker Desktop and try again."
    exit 2
fi

# 2) container الـ web شغال؟ لو لأ شغّله
if ! docker-compose ps --status running --services | grep -qx web; then
    echo "🔌 Starting containers..."
    docker-compose up -d
fi

# 3) شغّل الـ tests
if docker-compose exec -T web python manage.py test; then
    echo "✅ All Boundary Tests Passed Successfully!"
else
    echo "❌ Tests failed.."
    exit 1
fi