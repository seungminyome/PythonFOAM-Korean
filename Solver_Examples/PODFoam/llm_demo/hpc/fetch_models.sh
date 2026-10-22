#!/usr/bin/env bash
# Download the weights and projector of each model key given (see models.tsv)
# into POD_LLM_RUNTIME, at the pinned revision, and check their SHA-256.
# Files already present with the right hash are kept. Run it on the login node
# if compute nodes have no internet. Usage: fetch_models.sh e2b 12b 31b
# With FETCHED_LIST set, each file actually downloaded is appended to that list.
set -euo pipefail
runtime_dir="${POD_LLM_RUNTIME:?set POD_LLM_RUNTIME}"
table="$(dirname -- "${BASH_SOURCE[0]}")/models.tsv"
[[ $# -gt 0 ]] || { echo "usage: $0 KEY... (keys in $table)" >&2; exit 2; }
fetch() {   # repo revision file sha256 folder
    local target="$runtime_dir/$5/$3"
    mkdir -p "$runtime_dir/$5"
    if [[ -f $target ]] && echo "$4  $target" | sha256sum --check --status; then
        echo "ok   $5/$3"; return
    fi
    local auth=()
    [[ -n ${HF_TOKEN:-} ]] && auth=(-H "Authorization: Bearer $HF_TOKEN")
    echo "get  $5/$3"
    curl --fail --location --retry 3 --continue-at - "${auth[@]}" \
        "https://huggingface.co/$1/resolve/$2/$3" --output "$target.partial"
    echo "$4  $target.partial" | sha256sum --check --status || {
        echo "SHA-256 mismatch for $3; kept as $target.partial" >&2; exit 1; }
    mv "$target.partial" "$target"
    [[ -n ${FETCHED_LIST:-} ]] && echo "$target" >> "$FETCHED_LIST"
    return 0
}
for key in "$@"; do
    row=$(awk -F'\t' -v k="$key" '$1 == k' "$table")
    [[ -n $row ]] || { echo "unknown model key: $key" >&2; exit 2; }
    IFS=$'\t' read -r _ _ repo revision weights weights_sha projector projector_sha folder <<< "$row"
    fetch "$repo" "$revision" "$weights" "$weights_sha" "$folder"
    fetch "$repo" "$revision" "$projector" "$projector_sha" "$folder"
done
