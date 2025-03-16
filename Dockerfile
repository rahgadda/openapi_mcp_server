FROM python:3.11-slim

# Install uv package manager
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy project files
COPY . .
RUN rm -rf images

# Install dependencies using uv
RUN uv sync

# Expose the port your application runs on (adjust if needed)
EXPOSE 8080

# Set environment to production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production

# Start the server
CMD ["uv", "run","openapi_mcp_server"]