#! /bin/bash
conda create -n data_talker python=3.10
conda activate taotie
# Install poetry
pip install poetry
poetry install