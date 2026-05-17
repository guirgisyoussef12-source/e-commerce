# Python base image
FROM python:3.12

# منع ملفات pyc
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# مجلد الشغل داخل الكونتينر
WORKDIR /app

# تثبيت dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# نسخ المشروع
COPY . /app/

# تشغيل السيرفر
CMD ["gunicorn", "ecommerce.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]