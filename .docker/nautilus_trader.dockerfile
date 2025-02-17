FROM python:3.10-slim as base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=1.1.13 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/opt/pysetup"
ENV PATH="$POETRY_HOME/bin:$PATH"
WORKDIR $PYSETUP_PATH

FROM base as builder

# Install build deps
RUN apt-get update && apt-get install -y gcc curl

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Install package requirements (split step and with --no-root to enable caching)
COPY poetry.lock pyproject.toml build.py ./
RUN poetry install --no-root --no-dev

# Build nautilus_trader
COPY nautilus_trader ./nautilus_trader
COPY README.md ./
RUN poetry install --no-dev
RUN poetry build -f wheel
RUN python -m pip install ./dist/*whl --force
RUN find /usr/local/lib/python3.10/site-packages -name "*.pyc" -exec rm -f {} \;

# Final application image
FROM base as application
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY examples ./examples
