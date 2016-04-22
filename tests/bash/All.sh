#!/usr/bin/env bash

set -o errexit

cd "$(dirname "${BASH_SOURCE[0]}")"

./Basics.sh
./Edit.sh
./Help.sh
./Logs.sh
./ObscureProjectLayouts.sh
./Selectors.sh
