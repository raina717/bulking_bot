FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create a data directory for persistent storage
RUN mkdir -p /app/data

# Environment variables for the data files
ENV PROFILE_FILE=/app/data/profile.json
ENV LOG_FILE=/app/data/logs.json

CMD ["python", "bot.py"]
