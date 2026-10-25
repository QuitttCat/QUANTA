#!/usr/bin/env bash

# Load DWAVE_API_TOKEN from /root/dwave/.env.
# This accepts whitespace around "=", for example:
# DWAVE_API_TOKEN= token-value

_dwave_env_file="${DWAVE_ENV_FILE:-/root/dwave/.env}"
_dwave_token_value=""
_dwave_token_line=""

if [[ ! -f "$_dwave_env_file" ]]; then
    echo "Error: D-Wave environment file not found: $_dwave_env_file" >&2
    return 1 2>/dev/null || exit 1
fi

while IFS= read -r _dwave_token_line || [[ -n "$_dwave_token_line" ]]; do
    _dwave_token_line="${_dwave_token_line%$'\r'}"
    if [[ "$_dwave_token_line" =~ ^[[:space:]]*(export[[:space:]]+)?DWAVE_API_TOKEN[[:space:]]*=(.*)$ ]]; then
        _dwave_token_value="${BASH_REMATCH[2]}"
        _dwave_token_value="${_dwave_token_value#"${_dwave_token_value%%[![:space:]]*}"}"
        _dwave_token_value="${_dwave_token_value%"${_dwave_token_value##*[![:space:]]}"}"

        if [[ ${#_dwave_token_value} -ge 2 ]]; then
            if [[ "${_dwave_token_value:0:1}" == '"' && "${_dwave_token_value: -1}" == '"' ]] || \
               [[ "${_dwave_token_value:0:1}" == "'" && "${_dwave_token_value: -1}" == "'" ]]; then
                _dwave_token_value="${_dwave_token_value:1:${#_dwave_token_value}-2}"
            fi
        fi
        break
    fi
done < "$_dwave_env_file"

if [[ -z "$_dwave_token_value" ]]; then
    echo "Error: DWAVE_API_TOKEN is missing from $_dwave_env_file" >&2
    unset _dwave_env_file _dwave_token_value _dwave_token_line
    return 1 2>/dev/null || exit 1
fi

export DWAVE_API_TOKEN="$_dwave_token_value"
unset _dwave_env_file _dwave_token_value _dwave_token_line
