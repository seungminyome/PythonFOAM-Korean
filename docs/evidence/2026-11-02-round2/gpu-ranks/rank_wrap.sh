#!/bin/bash
# Per-rank wrapper under mpirun: records the rank's wrapper pid and the solver's pid, and gives each rank its own
# log (rank 0: log.PODFoam).
r=${OMPI_COMM_WORLD_RANK:-${PMI_RANK:-${PMIX_RANK:-${SLURM_PROCID:-unknown}}}}
f=$CASE/rank-$r.txt
if [[ $r == 0 ]]; then log=$CASE/log.PODFoam; else log=$CASE/log.rank$r; fi
"$@" > "$log" 2>&1 &
solver=$!
echo "rank=$r pid=$$ solver_pid=$solver host=$(hostname) start=$(date -u +%FT%T.%NZ)" > "$f"
wait "$solver"; status=$?
echo "exit=$status end=$(date -u +%FT%T.%NZ)" >> "$f"
exit $status
