FROM ubuntu:16.04

# Install dependencies
RUN apt-get update \
 && apt-get install -y \
    git \
    python3 \
    python3-git \
    python3-yaml \
 && rm -rf /var/lib/apt/lists/*

# Adding assets
RUN mkdir -p /app/op /app/fetch-op /app/local
ADD assets/main.py /app/
ADD assets/repo-list.yml /app/

VOLUME /app/op
VOLUME /app/local

# Starting component
WORKDIR /app
CMD python3 ./main.py
