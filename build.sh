#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

__dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

virtualenv -q "${__dir}/.virtualenv"
source "${__dir}/.virtualenv/bin/activate"
pip3 -qq install -r "${__dir}/requirements.txt"
"${__dir}"/scripts/template.py --prog $(basename "$0") "$@"
