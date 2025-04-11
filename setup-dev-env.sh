# source this script like so to install packages and setup your virtual env when developing:
# > source ./venv.sh

# NOTE: you do not need to use this script when deploying! see README for deploy process

mkdir -p venv
python3 -m venv venv
source venv/bin/activate
python3 -m pip install 'HAP-python[QRCode]'
