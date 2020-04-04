#!/usr/bin/env bash
# pass import - Password Store Extension (https://www.passwordstore.org/)
# Copyright (C) 2017-2019 Alexandre PUJOL <alexandre@pujol.io>.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# This file should be sourced by all test-scripts
#
# This scripts sets the following:
#   $PASS	Full path to password-store script to test
#   $GPG	Name of gpg executable
#   $KEY{1..5}	GPG key ids of testing keys
#   $TESTS_HOME	This folder
#

# shellcheck disable=SC1091,SC2230

# Project directory
TESTS_HOME="$(pwd)"
PROJECT_HOME="$(dirname "$TESTS_HOME")"


# Databases settings
export MASTERPASSWORD="correct horse battery staple"
export ENCRYPTED_DB="$TESTS_HOME/database"
export DB="$TESTS_HOME/assets/db"


# Check dependencies
_die() { echo "${@}" && exit 1; }
PASS="$(which pass)"; GPG="$(which gpg)"; GIT=true
[[ -e "$PASS" ]] || _die "Could not find pass command"
[[ -e "$GPG" ]] || _die "Could not find gpg command"
_pass() { "$PASS" "${@}"; }


# sharness config
export SHARNESS_TEST_DIRECTORY="$TESTS_HOME"
export SHARNESS_TEST_SRCDIR="$PROJECT_HOME"
source ./sharness
export TMP="/tmp/pass-import/bash"
export PYTHONPATH="$PROJECT_HOME:$PYTHONPATH"
[[ -z "$CI" ]] || test_set_prereq CI


#  Prepare pass config vars
unset PASSWORD_STORE_DIR
unset PASSWORD_STORE_KEY
unset PASSWORD_STORE_GIT
unset PASSWORD_STORE_GPG_OPTS
unset PASSWORD_STORE_X_SELECTION
unset PASSWORD_STORE_CLIP_TIME
unset PASSWORD_STORE_UMASK
unset PASSWORD_STORE_GENERATED_LENGTH
unset PASSWORD_STORE_CHARACTER_SET
unset PASSWORD_STORE_CHARACTER_SET_NO_SYMBOLS
unset PASSWORD_STORE_ENABLE_EXTENSIONS
unset PASSWORD_STORE_EXTENSIONS_DIR
unset PASSWORD_STORE_SIGNING_KEY
unset GNUPGHOME
unset EDITOR

export PASSWORD_STORE_ENABLE_EXTENSIONS=true
export PASSWORD_STORE_EXTENSIONS_DIR="$PROJECT_HOME"


# GnuPG config
unset GPG_AGENT_INFO
export GNUPGHOME="$TESTS_HOME/assets/gnupg/"
export KEY1="D4C78DB7920E1E27F5416B81CC9DB947CF90C77B"
export KEY2="70BD448330ACF0653645B8F2B4DDBFF0D774A374"
export KEY3="62EBE74BE834C2EC71E6414595C4B715EB7D54A8"
export KEY4="9378267629F989A0E96677B7976DD3D6E4691410"
export KEY5="4D2AFBDE67C60F5999D143AFA6E073D439E5020C"
chmod 700 "$GNUPGHOME"


# Test helpers

_in() { [[ $1 =~ (^|[[:space:]])$2($|[[:space:]]) ]] && return 0 || return 1; }

test_cleanup() {
	rm -rf "$TMP"
	mkdir -p "$TMP"
}

test_init() {
	export testname="$1"
	export PASSWORD_STORE_DIR="$TMP/${testname}-store"
	export GIT_DIR="$PASSWORD_STORE_DIR/.git"
	export GIT_WORK_TREE="$PASSWORD_STORE_DIR"
	pass init "$KEY1"
	if $GIT; then
		git config --global user.email "Pass-Automated-Testing-Suite@zx2c4.com"
		git config --global user.name "Pass Automated Testing Suite"
		pass git init
	fi
}
