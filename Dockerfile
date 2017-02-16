# Development
FROM ubuntu:16.04

# Install environment
RUN apt-get update -y
RUN apt-get install -y sudo
RUN apt-get install -y git
RUN apt-get install -y wget
RUN apt-get install -y python3.5
RUN apt-get install -y python3-pip
RUN apt-get install -y python-setuptools
RUN pip install virtualenv
RUN virtualenv test