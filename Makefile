#!/bin/bash

run:
	python autoscale.py

install:
	pip install -r requirements.txt

clean:
	rm .env.json
