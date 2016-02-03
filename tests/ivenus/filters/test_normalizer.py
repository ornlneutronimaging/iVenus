#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, numpy as np
from ivenus import io
from ivenus.filters import normalizer

def test_average():
    dir = os.path.dirname(__file__)
    pattern = os.path.join(dir, "..", "..", "iVenus_data_set", "turbine", "*DF*.fits")
    ic = io.imageCollection(pattern, name="Dark Field")
    a = normalizer.average(ic)
    return


def test_normalize():
    dir = os.path.dirname(__file__)
    datadir = os.path.join(dir, "..", "..", "iVenus_data_set", "turbine")
    # dark field
    pattern = os.path.join(datadir, "*DF*.fits")
    dfs = io.imageCollection(pattern, name="Dark Field")
    # open beam
    pattern = os.path.join(datadir, "*DF*.fits")
    obs = io.imageCollection(pattern, name="Open Beam")
    # ct
    angles = np.arange(0, 52, 8.5)
    ct_series = io.ImageFileSeries(
        os.path.join(datadir, "*CT*_%.3f_*.fits"),
        identifiers = angles,
        name = "CT",
    )
    # output
    normalized_ct = io.ImageFileSeries(
        "normalized_%.3f.npy", identifiers=angles, 
        decimal_mark_replacement=".", mode="w", name="Normalized"
        )
    normalizer.normalize(ct_series, dfs, obs, "work", normalized_ct)
    return
    

def main():
    test_average()
    test_normalize()
    return

if __name__ == '__main__': main()

# End of file