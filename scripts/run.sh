#!/bin/bash
set -e

echo "=== 🔌 [3/5] Starting Dockerized Environment ==="

# تشغيل الـ Containers بناءً على الـ Configuration بتاعتك
docker-compose up -d

echo "📊 Current Containers Status:"
docker-compose ps

echo "🌐 Django Web App is ready! Check it out at http://localhost:8000"