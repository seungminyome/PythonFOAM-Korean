# sourced inside the image, after VER is set
case $VER in
  v2106) RC=/usr/lib/openfoam/openfoam2106/etc/bashrc;;
  v2212) RC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
  v2012) RC=/usr/lib/openfoam/openfoam2012/etc/bashrc;;
  8) RC=/opt/openfoam8/etc/bashrc;;
esac
set --
source "$RC" >/dev/null 2>&1 || true
PY=/gscratch/syome/conda/s4f/bin/python3
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:$LD_LIBRARY_PATH
export PYTHON_INCLUDE_PATH=$($PY -c 'import sysconfig; print(sysconfig.get_path("include"))')
export NUMPY_INCLUDE_PATH=$($PY -c 'import numpy; print(numpy.get_include())')
export PYTHON_LIB_PATH=$($PY -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')
export PYTHON_LIB_NAME=lpython$($PY -c 'import sysconfig; print(sysconfig.get_config_var("LDVERSION"))')
export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
