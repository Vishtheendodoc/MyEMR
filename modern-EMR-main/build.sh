#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Create instance directory if it doesn't exist
mkdir -p instance

# Initialize database and populate sample data
python3 populate_sample_data.py
