#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
readonly here="$(pwd)"

###############################################################################
# Helpers
###############################################################################

source "$here"/BashUnit.sh

readonly test_tmp="$(mktemp -d /tmp/ads-test.XXX)"
copy_project_to_tmp_and_go() {
    local project_dir="$1"
    project_tmp="$(mktemp -d "$test_tmp"/"$(basename "$project_dir")".XXX)"
    if [[ "$(ls "$project_dir")" ]]; then
        cp -R "$project_dir"/* "$project_tmp"
    fi
    cd "$project_tmp"
}

readonly test_dir="$here"/../..
go_test_project() {
    local name="$(basename "$1")"
    copy_project_to_tmp_and_go "$test_dir"/resources/"$name"
}

# Temporarily sets your ads profile to the value of stdin
set_ads_profile() {
    export ADS_PROFILE_HOME="$test_tmp"
    cat > "$test_tmp/.ads_profile.yml"
}

###############################################################################
# setup and teardown
###############################################################################

readonly regex_to_kill_between_tests="service.sh"

setup() {
    assert_not_running "$regex_to_kill_between_tests"
    set_ads_profile << EOF
# empty default profile"
EOF
}

teardown() {
    procs_to_kill="$(pgrep -f "$regex_to_kill_between_tests" || true)"
    echo "$procs_to_kill" | xargs kill -9 &> /dev/null || true
}

###############################################################################
# main()
###############################################################################

run_tests