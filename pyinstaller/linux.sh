#!/bin/bash

# clone and cd into repo
git clone https://github.com/unconv/gpt-autopilot.git
cd gpt-autopilot

# run pyinstaller
pyinstaller gpt-autopilot.py

# add system_message to package
cp system_message dist/gpt-autopilot/

# get distro identifier
distro=$(lsb_release -sd | tr ' ' '-')

# make zip package
cd dist/
mkdir -p ../../zip/; 
zip -r "../../zip/gpt-autopilot-$distro.zip" gpt-autopilot

# remove git repo
cd ../../; rm -rf gpt-autopilot/
