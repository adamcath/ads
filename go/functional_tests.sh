#!/usr/bin/env bash
#
# Install ads from source and run functional tests. These will dump some
# temp files in your FS and start and stop processes, so they are slightly
# more brittle than the unit tests.

cd "$(dirname "${BASH_SOURCE[0]}")"

set -o errexit

# so that `go install` knows what to do
export GOPATH="$(pwd)"

# so that the tests can find the go ads binary
export PATH="$(pwd)"/bin:$PATH

# so that the thing compiles
./fetch_deps.sh

go install ads
cd ..
source tests/bash/All.sh
