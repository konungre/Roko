"""Fixed numeric compatibility probes; expected values are independent test data."""
PROBES = (
    ('abs-negative', '!(absNumber -0.25)', 0.25),
    ('abs-zero', '!(absNumber 0.0)', 0.0),
    ('exp-zero', '!(expNum 0.0)', 1.0),
    ('exp-three', '!(expNum 3.0)', 20.085536923187668),
    ('sigmoid-zero', '!(sigmoidNum 0.0)', 0.5),
    ('sigmoid-low', '!(sigmoidNum -3.0)', 0.04742587317756678),
    ('sigmoid-high', '!(sigmoidNum 3.0)', 0.9525741268224334),
    ('positive-negative', '!(positivePart -1.0)', 0.0),
    ('positive-positive', '!(positivePart 0.75)', 0.75),
    ('scale-signed', '!(scaleArray (-0.1 0.0 0.1 0.012345) 10.0)', [-1.0,0.0,1.0,0.12345]),
    ('scale-empty', '!(scaleArray () 10.0)', []),
    ('clip-boundaries', '!(clipVector (-1.0 0.0 0.5 1.0 2.0) 0.0 1.0)', [0.0,0.0,0.5,1.0,1.0]),
    ('clip-empty', '!(clipVector () 0.0 1.0)', []),
    ('mean-indices', '!(meanAtIndices (0.2 0.4 0.6 0.8) (1 3))', 0.6),
    ('mean-empty', '!(meanAtIndices (0.2 0.4) ())', 0.0),
)
