#!/bin/bash
#SBATCH --account=me5475
#SBATCH --partition=mb-a30,mb-l40s
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=01:30:00
#SBATCH --job-name=llama-build
#SBATCH --output=/gscratch/syome/github_repos/PythonFOAM/llm-runtime-12b/build-%j.log
set -euo pipefail
module load arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0
export POD_LLM_RUNTIME=/gscratch/syome/github_repos/PythonFOAM/llm-runtime-12b
export CMAKE_CUDA_ARCHITECTURES="80;89;90"
export BUILD_JOBS=16
export LDFLAGS="-L/apps/u/opt/gcc/14.2.0/cuda-toolkit/12.8.0/lib64/stubs"
rm -rf llama.cpp-build
cd "$POD_LLM_RUNTIME"; ls /usr/lib64/libcuda.so* 
mv llama-b11429-cuda llama-b11429-cuda.prebuilt-glibc238 2>/dev/null || true
bash /gscratch/syome/github_repos/PythonFOAM/Solver_Examples/PODFoam/llm_demo/hpc/build_llama_cuda.sh
