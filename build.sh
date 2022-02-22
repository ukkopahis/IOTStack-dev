#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

__dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

virtualenv -q "${__dir}/.virtualenv"
source "${__dir}/.virtualenv/bin/activate"
pip3 -q install -r "${__dir}/requirements.txt" --disable-pip-version-check --no-input
"${__dir}"/scripts/template.py --prog $(basename "$0") "$@"
