# Base dependencies are shared by the test and runtime stages.
FROM mcr.microsoft.com/playwright/python:v1.57.0-noble AS base
WORKDIR /service
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY app ./app

# Fail the image build if any contract/restart regression test fails.
FROM base AS verify
COPY tests ./tests
RUN python -m pip install --no-cache-dir pytest && python -m pytest -q tests

# The published service does not contain the pytest dependency.
FROM base AS runtime
COPY --from=verify /service/app /service/app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=10000 REQUIRE_DURABLE_STORAGE=1
EXPOSE 10000
USER pwuser
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]

