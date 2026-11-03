# Timing helper, not part of what the README asks: records each typed command, its exit status and seconds.
step() { # step NAME command...
  local name=$1; shift
  local t0=$(date +%s)
  echo "=== [$name] $(date -Is) \$ $*"
  "$@" 2>&1 | tee "$LOGS/$name.log"
  local st=${PIPESTATUS[0]}
  local t1=$(date +%s)
  printf '%s\t%s\t%s\t%s\n' "$name" "$st" "$((t1-t0))" "$*" >> "$LOGS/steps.tsv"
  echo "=== [$name] exit $st, $((t1-t0)) s"
  return $st
}
