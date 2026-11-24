ARG ASTRO_RUNTIME_IMAGE=python:3.12-slim
FROM ${ASTRO_RUNTIME_IMAGE}
USER root
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOST=0.0.0.0 PORT=8000 ASTRO_DATA=/var/lib/astro
WORKDIR /opt/astro
COPY requirements.txt scripts/check_dependencies.py ./
RUN (python check_dependencies.py || python -m pip install --disable-pip-version-check --no-cache-dir --only-binary=:all: -r requirements.txt) \
    && python check_dependencies.py && python -m pip check
COPY astro ./astro
COPY image_lab ./image_lab
COPY static ./static
COPY templates ./templates
RUN useradd -U -u 11576 observer && install -d -o observer -g observer /var/lib/astro
USER observer
EXPOSE 8000
CMD ["python", "-B", "-m", "astro"]
