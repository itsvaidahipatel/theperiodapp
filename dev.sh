#!/bin/bash

# Simple alias script - just calls start.sh
# This provides a shorter command: ./dev.sh

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
exec "$DIR/start.sh"
