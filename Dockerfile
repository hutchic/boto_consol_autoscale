FROM ubuntu:14.04

RUN apt-get update && apt-get install make python-pip gcc python-dev

WORKDIR /src
