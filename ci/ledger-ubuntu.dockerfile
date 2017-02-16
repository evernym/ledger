# Development
FROM ubuntu:16.04

# Install environment
RUN apt-get update -y && apt-get install -y \
  # common stuff
    git \
    wget \
    python3.5 \
    python3-pip \
    python-setuptools \
    sudo
