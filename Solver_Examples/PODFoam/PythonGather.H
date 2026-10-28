// Gather per-rank lists to the master rank in rank order, for the Python
// observer (analysis_func, mesh_func): in a parallel run the master gets the
// whole mesh and fields, concatenated by rank, and is the only rank that
// calls Python for the observer. In a serial run the list comes back as is.
// The POD snapshot/SVD path (snapshot_func, svd_func) stays per rank.
#ifndef PythonGather_H
#define PythonGather_H

template<class T>
Foam::List<T> pythonGatherToMaster(const Foam::List<T>& local)
{
    Foam::List<Foam::List<T>> all(Foam::Pstream::nProcs());
    all[Foam::Pstream::myProcNo()] = local;
    Foam::Pstream::gatherList(all);
    Foam::List<T> out;
    if (Foam::Pstream::master())
    {
        Foam::label n = 0;
        forAll(all, proci) n += all[proci].size();
        out.setSize(n);
        Foam::label k = 0;
        forAll(all, proci)
        {
            forAll(all[proci], i) out[k++] = all[proci][i];
        }
    }
    return out;
}

// Where each rank's cells start in the gathered (rank-ordered) cell list.
inline Foam::labelList pythonCellOffsets(const Foam::label nLocalCells)
{
    Foam::labelList counts(Foam::Pstream::nProcs(), 0);
    counts[Foam::Pstream::myProcNo()] = nLocalCells;
    Foam::Pstream::gatherList(counts);
    Foam::Pstream::scatterList(counts);   // every rank shifts its own cell labels
    Foam::labelList offsets(counts.size() + 1, 0);
    forAll(counts, proci) offsets[proci + 1] = offsets[proci] + counts[proci];
    return offsets;
}

#endif
