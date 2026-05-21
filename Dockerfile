FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    R_HOME=/usr/lib/R

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        git \
        r-base \
        r-base-dev \
        libcurl4-openssl-dev \
        libssl-dev \
        libxml2-dev \
    && rm -rf /var/lib/apt/lists/*

# CRAN may not ship ffanalytics for the distro R version; install from GitHub.
RUN Rscript -e '\
  install.packages("remotes", repos = "https://cloud.r-project.org"); \
  remotes::install_github( \
    "FantasyFootballAnalytics/ffanalytics", \
    upgrade = "never", \
    dependencies = TRUE \
  ) \
'

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY config.py .
COPY db/ db/
COPY api/ api/
COPY espn/ espn/
COPY jobs/ jobs/
COPY rag/ rag/
COPY draft/ draft/
COPY ui/ ui/
COPY scripts/ scripts/

RUN chmod +x scripts/docker-entrypoint-api.sh scripts/docker-entrypoint-ui.sh \
    scripts/docker-entrypoint-espn-scrape.sh

EXPOSE 8000 8501
