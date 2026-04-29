# Builder image for ankhlan.github.io — TeX Live (subset) + Python + deps.
# Built and pushed to ghcr.io/<owner>/<repo>-builder by .github/workflows/build-image.yml
# Used by .github/workflows/build.yml as the job container.

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# TeX Live (latex-extra covers AMS, standalone, microtype, hyperref...),
# Pictures package brings TikZ + PGF, dvisvgm, fonts, plus git/python so
# the build script and commit-back step run inside the same container.
RUN apt-get update && apt-get install -y --no-install-recommends \
      texlive-latex-base \
      texlive-latex-recommended \
      texlive-latex-extra \
      texlive-pictures \
      texlive-fonts-recommended \
      texlive-science \
      dvisvgm \
      python3 \
      python3-pip \
      python3-venv \
      git \
      ca-certificates \
      && rm -rf /var/lib/apt/lists/*

# Python deps. Pinning happens upstream in requirements.txt.
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Sanity check: every binary the build pipeline reaches for must be on PATH.
RUN latex --version    | head -1 \
    && dvisvgm --version | head -1 \
    && python3 --version \
    && python3 -c "import yaml, jinja2, markdown_it; print('python deps ok')"

WORKDIR /workspace
