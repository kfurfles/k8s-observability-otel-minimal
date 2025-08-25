FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/app.py .

# Expose port
EXPOSE 3333

# Run the application
ENTRYPOINT ["python3", "app.py"]
