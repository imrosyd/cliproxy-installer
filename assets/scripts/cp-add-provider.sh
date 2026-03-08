#!/bin/bash
if ! command -v python3 &> /dev/null; then
    echo -e "\033[0;31m[ERROR] Python3 is not installed. Please install it to use cp-add-provider.\033[0m"
    exit 1
fi
python3 "$HOME/.cliproxyapi/scripts/cp-add-provider.py"
