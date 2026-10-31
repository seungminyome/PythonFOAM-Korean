"""Stage the three cases from Run_Case without touching it. Every edit must find its text."""
from pathlib import Path
import os
import re
import shutil
import sys

if len(sys.argv) != 3:
    sys.exit(f'usage: {sys.argv[0]} POD_SOURCE_DIRECTORY OUTPUT_DIRECTORY')
source, output = map(Path, sys.argv[1:])


def replaced(path, *pairs):
    text = path.read_text()
    for old, new in pairs:
        assert old in text, (path, old)
        text = text.replace(old, new)
    path.write_text(text)


def substituted(pattern, new, text):
    text, count = re.subn(pattern, new, text)
    assert count, pattern
    return text


for name in ('baseline-pimple', 'fixed-pimple', 'fixed-pod'):
    case = output / name
    for directory in ('0', 'constant', 'system'):
        shutil.copytree(source / 'Run_Case' / directory, case / directory)
    # Remove restart metadata only from the newly staged copies.
    if (case / '0/uniform/time').exists():
        (case / '0/uniform/time').unlink()
    # openfoam.org reads momentumTransport, openfoam.com turbulenceProperties.
    transport = case / 'constant/momentumTransport'
    turbulence = transport.read_text()
    turbulence = substituted(r'(LES\s*\{)', r'\1\n    LESModel Smagorinsky;', turbulence)
    if name != 'baseline-pimple':
        turbulence = substituted(r'simulationType\s+LES;', 'simulationType laminar;', turbulence)
        replaced(case / '0/U', ('uniform (1e-8 0 0)', 'uniform (32.2 0 0)'))
        replaced(case / 'system/fvSchemes',
                 ('default         backward;', 'default         Euler;'),
                 ('div(phi,U)      Gauss linear;', 'div(phi,U)      Gauss upwind;'),
                 ('Gauss linear corrected', 'Gauss linear limited 0.5'),
                 ('default         corrected;', 'default         limited 0.5;'))
        replaced(case / 'system/fvSolution',
                 ('nNonOrthogonalCorrectors 0;', 'nNonOrthogonalCorrectors 2;'),
                 ('smoother        GaussSeidel;', 'smoother        DICGaussSeidel;'))
    transport.write_text(turbulence)
    if (case / 'constant/turbulenceProperties').exists():
        (case / 'constant/turbulenceProperties').unlink()
    (case / 'constant/turbulenceProperties').write_text(
        turbulence.replace('object      momentumTransport;', 'object      turbulenceProperties;'))
    dt, end = ('1e-5', '1e-4') if name == 'baseline-pimple' else ('1e-7', '1e-6')
    control = '''FoamFile
{
    version 2.0;
    format ascii;
    class dictionary;
    object controlDict;
}
application SOLVER;
startFrom startTime;
startTime 0;
stopAt endTime;
endTime END;
deltaT DT;
writeControl timeStep;
writeInterval 1;
purgeWrite 0;
writeFormat ascii;
writePrecision 12;
writeCompression off;
timeFormat general;
timePrecision 10;
runTimeModifiable false;
adjustTimeStep no;
maxCo 1;
podSvdInterval 10;
functions {}
libs ("libincompressibleTurbulenceModels.so");
'''
    if not os.environ.get('WM_PROJECT_VERSION', 'v').startswith('v'):
        control = control.replace('libs ("libincompressibleTurbulenceModels.so");\n', '')
    (case / 'system/controlDict').write_text(control.replace('SOLVER', 'PODFoam' if name == 'fixed-pod' else 'pimpleFoam').replace('END', end).replace('DT', dt))
    if name == 'fixed-pod':
        shutil.copy2(source / 'validation/python_module.py', case / 'python_module.py')
