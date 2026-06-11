#!/bin/bash
set -e

echo "=== 🧹 [4/5] Running System & Docker Cleanup ==="

# مسح مخلفات الـ Cache بتاعة الديجانجو والبايثون
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -delete

# تنظيف صور وكاش الدوكر القديمة
docker system prune -f

echo "✨ Workspace is super clean now!"