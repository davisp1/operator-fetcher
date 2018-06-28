FROM ubuntu:16.04

LABEL license="Apache License, Version 2.0"
LABEL copyright="CS Systèmes d'Information"
LABEL maintainer="contact@ikats.org"
LABEL version="0.8.0"

# Install dependencies
RUN apt-get update \
 && apt-get install -y \
    git \
    python3 \
    python3-git \
    python3-yaml \
    python3-pip \
    python3-dev \
    build-essential \
 && easy_install3 pip \
 && rm -rf /var/lib/apt/lists/*
RUN pip3 install psycopg2-binary

# Adding assets
RUN mkdir -p /app/op /app/fetch-op /app/local app/fam
ADD assets/main.py /app/
ADD assets/catalog.py /app/
ADD assets/families.json /app/
ADD assets/repo-list.yml /app/

VOLUME /app/op
VOLUME /app/local
VOLUME /app/fam

# Do git clone no matter the validity of the certificate
ENV GIT_SSL_NO_VERIFY true

# Starting component
WORKDIR /app
CMD python3 ./main.py
