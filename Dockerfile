FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies come first. This layer changes only when the dependency list in pyproject.toml changes,
# so editing the code or the static files does not install the packages again.
# The pip cache is kept between builds, so packages that did not change are not downloaded again.
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -c "import tomllib, subprocess, sys; deps = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; subprocess.check_call([sys.executable, '-m', 'pip', 'install', *deps])"

# Only the project itself is rebuilt when the code or the static files change.
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps .

EXPOSE 8000

CMD ["uvicorn", "zaban.main:app", "--host", "0.0.0.0", "--port", "8000"]
