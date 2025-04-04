# Pull the base image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Expose the port Django runs on
EXPOSE 8000

# Run the application
CMD ["gunicorn", "stock_forex_app.wsgi:application", "--bind", "0.0.0.0:8000"]