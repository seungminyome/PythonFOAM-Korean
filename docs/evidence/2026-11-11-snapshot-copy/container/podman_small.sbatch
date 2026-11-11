#!/bin/bash
#SBATCH --job-name=podman-small
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/small/docker/%x-%j.out
# Builds branch pr/podfoam-snapshot-copy in the image and runs PODFoam's shipped case;
# (the e2e script runs the PR bodies' Docker lines) with rootless Podman (static build, one UID mapped: no /etc/subuid entry here).
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
M=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/small/modules/PODFoam
podman run --rm $pol -v $M:/mods:ro docker.io/romitmaulik1/pythonfoam_docker bash -c '
  id; git clone --depth 1 -b pr/podfoam-snapshot-copy https://github.com/seungminyome/PythonFOAM.git /tmp/PythonFOAM 2>&1 | tail -1
  git -C /tmp/PythonFOAM rev-parse HEAD
  source /opt/openfoam8/etc/bashrc
  PY=$(command -v python3); $PY -c "import sys,numpy; print(\"python\", sys.version.split()[0], \"numpy\", numpy.__version__)"
  export PYTHON_INCLUDE_PATH=$($PY -c "import sysconfig; print(sysconfig.get_path(\"include\"))")
  export NUMPY_INCLUDE_PATH=$($PY -c "import numpy; print(numpy.get_include())")
  export PYTHON_LIB_PATH=$($PY -c "import sysconfig; print(sysconfig.get_config_var(\"LIBDIR\"))")
  export PYTHON_LIB_NAME=lpython$($PY -c "import sysconfig; print(sysconfig.get_config_var(\"LDVERSION\"))")
  export FOAM_USER_APPBIN=/tmp/bin; mkdir -p /tmp/bin
  for s in PODFoam PODFoam_Debug APMOSFoam AEFoam; do
    (cd /tmp/PythonFOAM/Solver_Examples/$s && wmake > /tmp/log.build-$s 2>&1) && echo "BUILD $s ok" || { echo "BUILD $s FAILED"; grep -n -i error /tmp/log.build-$s | head -5; }
  done
  c=/tmp/case; cp -rL /tmp/PythonFOAM/Solver_Examples/PODFoam/Run_Case $c; rm -f $c/0/uniform/time
  sed -i "s/^startFrom .*/startFrom startTime;/; s/^endTime .*/endTime 1.5e-4;/" $c/system/controlDict
  cp /mods/module-recording.py $c/python_module.py
  cd $c && blockMesh > log.blockMesh 2>&1 && MPLBACKEND=Agg /tmp/bin/PODFoam > log.PODFoam 2>&1; echo "PODFoam exit $? steps $(grep -c "^Courant Number mean" log.PODFoam)"
  $PY -c "
import numpy as np, glob
n=e=0
for f in sorted(glob.glob(\"snapshots-*.npz\")):
    z=np.load(f)
    for k in \"uvw\":
        n+=1; e+=bool(np.array_equal(z[k][:,0], z[k][:,1]))
print(\"matrices\", n, \"first two columns equal in\", e)"
' > $T/out-small.txt 2>&1
rc=$?; cat $T/out-small.txt | cut -c1-200; cp $T/out-small.txt $SLURM_SUBMIT_DIR/podman-small-$SLURM_JOB_ID.txt
echo "exit: $rc"
echo "end $(date -Is)"
chmod -R u+rwx $T 2>/dev/null; rm -rf $T 2>/dev/null
