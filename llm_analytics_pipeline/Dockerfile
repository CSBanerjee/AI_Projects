# ============================================================
# Dockerfile
# ============================================================
# PURPOSE:
#   Packages the entire pipeline into a self-contained
#   image that runs identically on any machine.
#
# Base image: official Python 3.11 slim
# "slim" = has Python but not unnecessary OS tools
# keeps the image small
# ============================================================

FROM python:3.11-slim

# Set working directory inside the container
# All commands below run from here
WORKDIR /app

# Copy requirements first — before copying your code
# WHY: Docker caches each layer. If requirements don't
# change, Docker reuses the cached install layer and
# skips reinstalling. Makes rebuilds much faster.
COPY requirements.txt .

# Install dependencies inside the container
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project into the container
COPY . .

# Create directories the pipeline writes to
RUN mkdir -p /app/logs /app/output

# The command Docker runs when the container starts
CMD ["python", "main.py"]