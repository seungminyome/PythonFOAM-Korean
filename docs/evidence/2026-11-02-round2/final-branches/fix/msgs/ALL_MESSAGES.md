#### 5b3e5a32188c399e850c3e177547efcd85c04c75 (tree e469c24)

```
PODFoam: NumPy owns each snapshot; calls into Python are checked

The snapshot handed to snapshot_func was a view of a C++ buffer that the next
step overwrites; the shipped module keeps the first snapshot of each window
that way and reads the second step's values twice. Each snapshot is now an
array NumPy owns, filled from U after a finite check of U and p. A failed
import, missing function, exception or SystemExit stops the run with the
traceback. svd_func must return float64 modes, shape (3*cells, 1 or more),
finite, the same count on all ranks. For a user: mode files are dimensionless
zeroGradient fields; podTruncation (controlDict, default 5) caps the modes
written, and more columns give one warning; the case folder comes first on
sys.path; Py_FinalizeEx at exit waits for non-daemon threads; a changed cell
count stops the run; a write step with no snapshot since the last SVD now
collects one (the earlier code ran svd_func at every write step).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### d686a64dbec54a7cf82dc3852c406775a9144adc (tree e117ab7)

```
PODFoam_Debug, APMOSFoam, AEFoam: NumPy owns each snapshot too

The three solvers pass PyArray_SimpleNewFromData over the reused C++ buffer
input_vals, so a view the module keeps reads the next step's values (their
shipped modules keep the first snapshot of each window that way, and the first
two snapshot columns, rows for AEFoam, come out equal). PyArray_SimpleNew plus
a copy of the buffer gives Python an owning array; a failed allocation stops
the run with a message. Nothing else in the three solvers changes.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### aaf80a66fd6c9eeac7d309f8d513f8685f4d0275 (tree 49403a6)

```
PODFoam: setRootCaseLists.H; floating-point traps off around Python

setRootCaseLists.H replaces the hand-written argList, so PODFoam parses its
arguments like pimpleFoam and gets the same signal handlers, including the
floating-point traps that the earlier argList(..., initialise=false) skipped.
NumPy's import overflows on purpose while probing machine limits, so the traps
are off around initialization, every call into Python and finalization:
PythonCompat.H gives sigFpe::ignore on openfoam.com and a small class on
openfoam.org, which has none; pending flags are cleared before the traps return.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### d01af1ab303d7b01fd5d134e5dc34601e7f75ad7 (tree e76d557)

```
PODFoam: optional podSvdInterval in controlDict

At its default of 0 nothing changes: a write step runs the SVD if snapshots
have been collected since the last SVD, and collects one otherwise. Above 0,
every step collects a snapshot and the SVD runs every podSvdInterval
snapshots, also on steps that write nothing else, which then hold only the
POD fields. A negative value stops the run with a message. Each step now
prints a Time = line with its deltaT; the timing lines stay.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### a7501b1ff420aed940995ba5db579b5d51264b52 (tree 46cc275)

```
pEqn: on openfoam.com select pFinal only on the final corrector

On openfoam.com a plain pEqn.solve() takes the pFinal solver throughout the
last outer iteration; with nOuterCorrectors 1, as in Run_Case, that is every
pressure corrector. pimpleFoam there solves with
mesh.solver(p.select(pimple.finalInnerIter())), the p solver until the final
corrector and pFinal there, and PODFoam now makes the same call, so its U and p
agree with pimpleFoam's on v2012, v2106 and v2212. On openfoam.org the call
stays plain, as in pimpleFoam there, and OpenFOAM 8 results do not change.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### 8376b00d9706b6b0f5a1e959ac7c8ef82800f74e (tree 1476ca1)

```
PODFoam: bridge validation

validation/run.sh builds PODFoam into a fresh directory under validation/runs/
and runs ten steps of a stabilised copy of Run_Case with pimpleFoam and with
PODFoam, where a minimal python_module.py keeps the ten snapshots and returns
five SVD modes per component. verify.py checks the snapshots against the
written U, the returned modes against the written fields, and U and p against
pimpleFoam. A failed step names its log. The README lists what a module must
provide and what changes in PODFoam with the commits before this one.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### 8954b2544d0f669d0079f6138eec6983944cf4d5 (tree e2dd9e2)

```
README: PODFoam snapshot fix and validation

The four solvers this series touches build on v2012, v2106, v2212 and 8, and
the README says so without widening the list for the other examples. Under
PODFoam in Contents, a pointer names the validation, what a module must provide
and the versions it passes on. The prep_env.sh sentence says its source line
must point at the bashrc of the OpenFOAM version in use, and the requirements
are given per solver: the solvers need Python 3 with numpy and their headers,
the shipped modules also matplotlib, and mpi4py or tensorflow.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### 371adbab9c8b006069a92c9501431a187c4cc207 (tree ce40f50)

```
PODFoam: optional analysis_func and mesh_func hooks

A python_module.py may define two more functions. mesh_func runs once before
the first step with copies of the cell centres, volumes, solution directions
and one polygon per cell (a face of the first empty patch, or a plane slice of
a 3D mesh). analysis_func runs after every step with the time index, snapshot
count, residuals, Courant and continuity numbers and copies of U and p. They
change neither U nor p; with analysis_func the POD step collects a snapshot at
every step. In parallel the master alone calls them. HOOKS.md has the contract.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### e05643e3dbec0c3f70eddcf22a8b885e97faf4e3 (tree 84dcac8)

```
PODFoam llm_demo: an observer asking a local vision-language model

python_module.py is an example module for the two hooks. At chosen steps it
draws |U| and p, asks a vision-language model served by a local llama-server
about them, and records the answer with the arrays; model output never goes
back into the solver. Each request runs in a forked worker with a deadline, so
a slow or dead server cannot hold the solver past it. run_demo.sh runs five
synchronous or five asynchronous cases against a resident server; verify_demo.py
and verify_async.py check that the written fields equal those of the run with
no request. The unit tests need neither a solver nor a model.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### 6e41943cffab1008480546e0b5c8d7195dceefe4 (tree 7d017e8)

```
PODFoam llm_demo/hpc: the GPU path

These scripts run the asynchronous suite with Gemma 4 12B on a Slurm GPU node.
setup_12b.sh fetches the pinned weights and llama.cpp and checks their SHA-256,
build_llama_cuda.sh builds llama.cpp where the prebuilt binaries need a newer
glibc, start_server.sh and stop_server.sh run the server and check that the pid
they handle is a llama-server, and async_v2.slurm runs the suite with OpenFOAM
in an Apptainer image. Everything specific to a site comes from the environment.
The runtime lives beside the repository and the job output under llm_demo/,
which its .gitignore covers.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### 24e9df6f5640594e2dbbd9a817231717fe8310ef (tree 251f965)

```
README: PODFoam hooks and the observer example

Under PODFoam in Contents, after the validation pointer, one line names
HOOKS.md with the two optional functions, which change neither U nor p (with
analysis_func the POD step collects a snapshot at every step), and llm_demo/,
the example module that asks a local vision-language model about the running
solver.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

