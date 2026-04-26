FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if required by fpdf2 or other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install dependencies
COPY Requirements.txt .
RUN pip install --no-cache-dir -r Requirements.txt

# Copy all project files into the container
COPY . .

# Expose the port that the application will run on
EXPOSE 8000

# Run the FastAPI server via Uvicorn
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
