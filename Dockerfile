FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN groupadd --gid 10001 agent && useradd --uid 10001 --gid agent --create-home agent
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install '.[redis,mcp]'
USER agent
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["mtr-agent", "serve", "--host", "0.0.0.0", "--port", "8000"]
