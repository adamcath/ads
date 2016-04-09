#!/usr/bin/env bash
#
# Install ads from source and run functional tests. These will dump some
# temp files in your FS and start and stop processes, so they are slightly
# more brittle than the unit tests.

cd "$(dirname "${BASH_SOURCE[0]}")"

pip install -e .
source tests/bash/FunctionalTest.sh