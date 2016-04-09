#!/usr/bin/env bash
#
# Run ads unit tests and check for adequate coverage.

set -o errexit

echo '#################################################'
echo '# Running unit tests'
echo '#################################################'

coverage run --source=ads,tests --branch -m unittest discover tests/unit/ -v

echo
echo '#################################################'
echo '# Coverage report'
echo '#################################################'

coverage html -d build/coverage

if ! coverage report --fail-under=30; then
    echo 'FAILED: Coverage too low' 2>&1
    exit 2
fi
echo 'Coverage OK. HTML report in build/coverage/index.html'