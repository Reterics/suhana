FROM python:3.12-slim

# Set workdir
WORKDIR /app

# Copy files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the server
CMD ["uvicorn", "engine.api_server:app", "--host", "0.0.0.0", "--port", "8000"]