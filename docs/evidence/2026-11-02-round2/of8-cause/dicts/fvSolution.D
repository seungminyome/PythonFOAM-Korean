/*--------------------------------*- C++ -*----------------------------------*\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  v1812                                 |
|   \\  /    A nd           | Web:      www.OpenFOAM.com                      |
|    \\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSolution;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solvers
{
    p
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-13;
        relTol          0;
        maxIter         20000;
    }

    "(U|k|epsilon|nuTilda|omega)"
    {
        solver          smoothSolver;
	    //preconditioner  DILU;
        smoother        symGaussSeidel;
        tolerance       1e-13;
        relTol          0;
        maxIter         20000;
    }

    pFinal
    {
        $p;
    }

    "(U|k|nuTilda)Final"
    {
        $U;
    }
}

SIMPLE
{
    nNonOrthogonalCorrectors 2;
    consistent      yes;

    residualControl
    {
        p               1e-3;
        U               1e-6;

//        "(k|nuTilda|epsilon|omega|f|v2)" 1e-5;
    }
}

PIMPLE
{
    nOuterCorrectors 1;
    nCorrectors     2;
    nNonOrthogonalCorrectors 2;
    pRefCell        1001;
    pRefValue       0;
}



// ************************************************************************* //

