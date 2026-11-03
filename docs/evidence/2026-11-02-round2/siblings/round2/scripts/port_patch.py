#!/usr/bin/env python3
"""Minimal 'Python-owned array' port of the fork's PythonComm.H change to one sibling's PythonComm.H.
Replaces the single PyArray_SimpleNewFromData line (view over the C++ buffer input_vals) by a NumPy-owned
array filled from the buffer. Everything else is left as upstream has it. Fails if the line is not found once.
Usage: port_patch.py PythonComm.H"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
text = p.read_text()
old = "    array_2d = PyArray_SimpleNewFromData(2, dim, NPY_DOUBLE, &input_vals[0]);\n"
new = ("    // r2/siblings port: NumPy owns the snapshot, so a view kept by Python cannot alias the next step\n"
       "    array_2d = PyArray_SimpleNew(2, dim, NPY_DOUBLE);\n"
       "    {\n"
       "        double* snap_data = static_cast<double*>(PyArray_DATA(reinterpret_cast<PyArrayObject*>(array_2d)));\n"
       "        const double* buf = &input_vals[0][0];\n"
       "        for (npy_intp i = 0; i < dim[0]*dim[1]; ++i) snap_data[i] = buf[i];\n"
       "    }\n")
assert text.count(old) == 1, (p, text.count(old))
p.write_text(text.replace(old, new))
print('patched', p)
