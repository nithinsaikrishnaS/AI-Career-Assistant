# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the current directory contents into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright system dependencies and Chromium browser
RUN python -m playwright install-deps && python -m playwright install chromium

# Download the spaCy model
RUN python -m spacy download en_core_web_sm

# Copy the rest of the application code
COPY . .

# 🛡️ 10/10 Security: Non-root execution
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
