"""Read an ASCII OpenFOAM case without OpenFOAM.

empty_patch_polygons() returns what PythonCreate.H passes to mesh_func for a
2D case: one polygon per face of the first empty patch, in patch order, the
face's points in face order, and the face's owner cell. read_internal_field()
returns the cell values of a volScalarField or volVectorField.
"""
from pathlib import Path
import re

import numpy as np

_FLOAT = r"[+\-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+\-]?\d+)?"


def _body(text):
    """Text after the FoamFile header, with comments removed."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    match = re.search(r"FoamFile\s*\{[^}]*\}", text)
    if not match:
        raise ValueError("no FoamFile header")
    return text[match.end():]


def _header_format(text):
    match = re.search(r"format\s+(\w+)\s*;", text)
    return match.group(1) if match else None


def _counted_list(text, start=0):
    """(count, inner text, end) of the first 'N ( ... )' list at or after start."""
    match = re.compile(r"(\d+)\s*\(").search(text, start)
    if not match:
        raise ValueError("no counted list")
    depth, index = 1, match.end()
    while depth:
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        index += 1
    return int(match.group(1)), text[match.end():index - 1], index


def _read(path):
    text = Path(path).read_text()
    if _header_format(text) != "ascii":
        raise ValueError(f"{path}: only ASCII files are supported")
    return _body(text)


def read_points(path):
    count, inner, _ = _counted_list(_read(path))
    values = np.array(re.findall(_FLOAT, inner), dtype=float)
    if values.size != 3 * count:
        raise ValueError(f"{path}: expected {count} points")
    return values.reshape(count, 3)


def read_labels(path):
    count, inner, _ = _counted_list(_read(path))
    values = np.array(inner.split(), dtype=np.int64)
    if values.size != count:
        raise ValueError(f"{path}: expected {count} labels")
    return values


def read_faces(path):
    """(sizes, flat point labels) of a faceList written as n(a b c ...)."""
    count, inner, _ = _counted_list(_read(path))
    faces = re.findall(r"(\d+)\s*\(([^()]*)\)", inner)
    if len(faces) != count:
        raise ValueError(f"{path}: expected {count} faces")
    sizes = np.array([int(n) for n, _ in faces], dtype=np.int64)
    labels = np.array(" ".join(body for _, body in faces).split(), dtype=np.int64)
    if labels.size != sizes.sum():
        raise ValueError(f"{path}: face sizes do not match the labels")
    return sizes, labels


def read_boundary(path):
    """[{'name', 'type', 'nFaces', 'startFace'}] in file order."""
    count, inner, _ = _counted_list(_read(path))
    patches = []
    for name, entries in re.findall(r"([A-Za-z0-9_.:\-]+)\s*\{([^{}]*)\}", inner):
        fields = dict(re.findall(r"(\w+)\s+([^;]+);", entries))
        patches.append({"name": name, "type": fields["type"].strip(),
                        "nFaces": int(fields["nFaces"]), "startFace": int(fields["startFace"])})
    if len(patches) != count:
        raise ValueError(f"{path}: expected {count} patches")
    return patches


def empty_patch_polygons(polymesh):
    """(points, offsets, cells) for the first empty patch, as in PythonCreate.H; None if none."""
    polymesh = Path(polymesh)
    patch = next((p for p in read_boundary(polymesh / "boundary") if p["type"] == "empty"), None)
    if patch is None:
        return None
    sizes, labels = read_faces(polymesh / "faces")
    owner = read_labels(polymesh / "owner")
    points = read_points(polymesh / "points")
    starts = np.concatenate([[0], np.cumsum(sizes)])
    first, last = patch["startFace"], patch["startFace"] + patch["nFaces"]
    if last > sizes.size or last > owner.size:
        raise ValueError("empty patch runs past the face list")
    face_labels = labels[starts[first]:starts[last]]
    offsets = starts[first:last + 1] - starts[first]
    return points[face_labels], offsets.astype(np.int64), owner[first:last].astype(np.int64)


def read_internal_field(path, cells):
    """Cell values of a volScalarField (cells,) or volVectorField (cells, 3)."""
    body = _read(path)
    match = re.search(r"internalField\s+(uniform|nonuniform)\s+", body)
    if not match:
        raise ValueError(f"{path}: no internalField")
    rest = body[match.end():]
    vector = re.search(r"class\s+volVectorField", Path(path).read_text()) is not None
    width = 3 if vector else 1
    if match.group(1) == "uniform":
        value = re.match(r"\(?\s*([^;)]*)\)?\s*;", rest).group(1)
        numbers = np.array(re.findall(_FLOAT, value), dtype=float)
        if numbers.size != width:
            raise ValueError(f"{path}: bad uniform value")
        values = np.tile(numbers, (cells, 1))
    else:
        count, inner, _ = _counted_list(rest)
        if count != cells:
            raise ValueError(f"{path}: {count} values for {cells} cells")
        numbers = np.array(re.findall(_FLOAT, inner), dtype=float)
        if numbers.size != width * cells:
            raise ValueError(f"{path}: expected {width * cells} numbers")
        values = numbers.reshape(cells, width)
    return values if vector else values[:, 0]
