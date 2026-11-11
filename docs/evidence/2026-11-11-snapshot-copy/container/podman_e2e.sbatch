#!/bin/bash
#SBATCH --job-name=podman-e2e
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/small/docker/%x-%j.out
# Runs the PR bodies' Docker lines with rootless Podman (static build, one UID mapped: no /etc/subuid entry here).
# Inside the container the user is root (uid 0), as with `docker run`.
P=/gscratch/syome/tools/podman-static/podman-linux-amd64
T=/tmp/syome-podman-$SLURM_JOB_ID; mkdir -p $T/run $T/conf; chmod 700 $T/run
export PATH=$P/usr/local/bin:$PATH XDG_RUNTIME_DIR=$T/run
cat > $T/conf/storage.conf <<C
[storage]
driver = "overlay"
graphroot = "$T/storage"
rootless_storage_path = "$T/storage"
runroot = "$T/runroot"
[storage.options.overlay]
mount_program = "$P/usr/local/bin/fuse-overlayfs"
ignore_chown_errors = "true"
C
cat > $T/conf/containers.conf <<C
[engine]
helper_binaries_dir = ["$P/usr/local/lib/podman"]
conmon_path = ["$P/usr/local/lib/podman/conmon"]
runtime = "crun"
no_pivot_root = true
cgroup_manager = "cgroupfs"
events_logger = "file"
[engine.runtimes]
crun = ["$P/usr/local/bin/crun"]
[containers]
cgroups = "disabled"
netns = "host"
C
export CONTAINERS_STORAGE_CONF=$T/conf/storage.conf CONTAINERS_CONF=$T/conf/containers.conf CONTAINERS_REGISTRIES_CONF=$P/etc/containers/registries.conf
echo "host $(hostname) start $(date -Is)"; df -hT /dev/shm /tmp | tail -2; podman --version
pol="--signature-policy $P/etc/containers/policy.json"
podman pull $pol docker.io/romitmaulik1/pythonfoam_docker 2>&1 | tail -3
podman images --digests 2>&1 | head -3
for B in "$@"; do
  echo "===== branch $B"
  podman run --rm $pol docker.io/romitmaulik1/pythonfoam_docker bash -c "
    id; git clone --depth 1 -b $B https://github.com/seungminyome/PythonFOAM.git /tmp/PythonFOAM 2>&1 | tail -1
    git -C /tmp/PythonFOAM rev-parse HEAD
    source /opt/openfoam8/etc/bashrc
    cd /tmp/PythonFOAM/Solver_Examples/PODFoam
    ./validation/run.sh" > $T/out-${B##*/}.txt 2>&1
  rc=$?; head -3 $T/out-${B##*/}.txt; grep -E '"status"|agreement|^PASS|^FAIL' $T/out-${B##*/}.txt; cp $T/out-${B##*/}.txt $SLURM_SUBMIT_DIR/podman-e2e-$SLURM_JOB_ID-${B##*/}.txt
  echo "exit of branch $B: $rc"
done
echo "end $(date -Is)"
chmod -R u+rwx $T 2>/dev/null; rm -rf $T 2>/dev/null
