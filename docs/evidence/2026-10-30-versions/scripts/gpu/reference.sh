#!/bin/bash
# The reference-run lines of hpc/README.md, from the repository root; "module load apptainer" added for this cluster's compute nodes.
G=/cluster/medbow/gscratch/syome/github_repos; B=$G/pod-versions-20261030/pr/refix/gpu-b
cd $B/PythonFOAM || exit 1
module load apptainer
export POD_LLM_RUNTIME=$G/PythonFOAM/llm-runtime-12b PYTHON=/gscratch/syome/conda/s4f/bin/python3
image=/cluster/medbow/gscratch/syome/s4f/of2212.sif
export OPENFOAM_BASHRC=/usr/lib/openfoam/openfoam2212/etc/bashrc POD_OPENFOAM_VERSION=v2212
apptainer exec --bind /cluster/medbow/gscratch $image bash -c 'source "$OPENFOAM_BASHRC"
    export LD_LIBRARY_PATH=$(dirname "$PYTHON")/../lib:$LD_LIBRARY_PATH
    cd Solver_Examples/PODFoam && ./validation/run_v2106.sh'
echo "reference exit $?"
