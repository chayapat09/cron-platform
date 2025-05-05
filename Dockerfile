# Dockerfile

# 1. Use an official Python runtime as a parent image
# Using slim version for smaller size
FROM python:3.11-slim

# 2. Set environment variables
# Prevents Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED 1
# Set the Flask environment to production (can be overridden by compose)
ENV FLASK_ENV production
# Set the working directory in the container
WORKDIR /app

# 3. Install system dependencies if needed (e.g., for numpy or other libraries)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# 4. Install Python dependencies
# Copy only the requirements file first to leverage Docker cache
COPY requirements.txt .
# Use --no-cache-dir to reduce image size
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Copy the application code into the container
# Copy everything from the current directory (.) into the container's WORKDIR (/app)
# .dockerignore will prevent copying excluded files/folders
COPY . .

# 6. (Optional but Recommended) Create a non-root user to run the application
# RUN groupadd -r appuser && useradd --no-log-init -r -g appuser appuser
# USER appuser
# Note: If using a non-root user, ensure file permissions allow writing to /app/instance if needed by the app logic *within* the container (less relevant here as we mount)

# 7. Expose the port the app runs on (as defined in main.py -> app.run or waitress)
EXPOSE 8080

# 8. Define the command to run the application using
CMD ["python3", "app.py"]