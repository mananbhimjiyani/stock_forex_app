FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["gunicorn", "stock_forex_app.wsgi:application", "--bind", "0.0.0.0:8000"]