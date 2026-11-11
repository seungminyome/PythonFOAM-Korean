#!/bin/bash
#SBATCH --job-name=dockertry
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/small/docker/%x-%j.out
D=/gscratch/syome/tools/docker-rootless
export PATH=$D/docker:$D/docker-rootless-extras:$PATH
export XDG_RUNTIME_DIR=/tmp/syome-run-$SLURM_JOB_ID HOME_DOCKER=/tmp/syome-docker-$SLURM_JOB_ID
mkdir -p $XDG_RUNTIME_DIR $HOME_DOCKER; chmod 700 $XDG_RUNTIME_DIR
echo "host $(hostname) subuid: $(grep "^$USER:" /etc/subuid || echo none) userns: $(cat /proc/sys/user/max_user_namespaces)"
dockerd-rootless.sh --data-root $HOME_DOCKER/data --exec-root $HOME_DOCKER/exec > $HOME_DOCKER/dockerd.log 2>&1 &
PID=$!
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/docker.sock
for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done
if docker info > $HOME_DOCKER/info.txt 2>&1; then echo "DOCKERD UP"; grep -E "Server Version|Storage Driver|rootless|Cgroup" $HOME_DOCKER/info.txt
  docker run --rm hello-world 2>&1 | head -5
else echo "DOCKERD DID NOT START"; tail -25 $HOME_DOCKER/dockerd.log; fi
kill $PID 2>/dev/null; sleep 2; rm -rf $HOME_DOCKER $XDG_RUNTIME_DIR 2>/dev/null
