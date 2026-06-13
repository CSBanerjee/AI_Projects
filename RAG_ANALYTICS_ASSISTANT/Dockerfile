FROM python:3.11-slim

WORKDIR /app

# install uv for fast dependency installation
# uv is 10-100x faster than pip for installing packages
RUN pip install uv

COPY requirements.txt .

# --system installs into the system Python — correct for Docker
# inside Docker there is no virtual environment so packages go directly
# into the system Python. The --system flag tells uv to do this.
RUN uv pip install --system -r requirements.txt

COPY . .

# create required folders if they do not exist
RUN mkdir -p /app/logs /app/chroma_db

# ingest documents first to populate ChromaDB, then start the API server
# ingest.py must run before api_server.py so ChromaDB has chunks to search
CMD ["sh", "-c", "python ingest.py && python api_server.py"]