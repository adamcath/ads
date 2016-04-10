#!/usr/bin/env bash

set -o errexit
set -o pipefail
set -o nounset

cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ -d dist ]]; then
    echo "Please delete $(pwd)/dist" >&2
    exit 1
fi

if ! pandoc -v &> /dev/null; then
    echo "Please install pandoc (brew install pandoc)" >&2
    exit 1
fi

if ! rst-lint -h &> /dev/null; then
    echo "Please install rst-lint (pip install restructuredtext_lint)" >&2
    exit 1
fi

if ! twine -h &> /dev/null; then
    echo "Please install twine (pip install twine)" >&2
    exit 1
fi

echo
echo "### Generating RST from Markdown"
pandoc --from=markdown --to=rst --output=build/README.rst README.md

echo
echo "### Checking RST for compatibility with PyPI (this is non-trivial)"
rst-lint build/README.rst

echo
echo "### Preparing distribution"
python setup.py bdist_wheel

echo
echo "### Uploading to PyPI (it may ask for your credentials)"
twine upload dist/*