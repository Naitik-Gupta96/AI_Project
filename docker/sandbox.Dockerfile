# Image for the KramaBench "python" tool. Each tool call runs in a fresh container from this
# image with no network, the data lake mounted read-only at /data, and memory/CPU limits
# (see src/ai_project/agents/tools.py).
FROM python:3.12-slim

RUN pip install --no-cache-dir \
        pandas==2.2.* numpy==2.* openpyxl==3.1.* xlrd==2.0.* pyarrow==17.* \
        scipy==1.14.* scikit-learn==1.5.* geopy==2.4.* \
    && useradd --create-home --uid 1000 runner

USER runner
WORKDIR /data
