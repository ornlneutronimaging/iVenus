#!/usr/bin/env python3
"""
Unit tests for backend data loading.
"""
import param

# package imports
from imars3d.backend.dataio.data import (
    _extract_rotation_angles,
    _forgiving_reader,
    _get_filelist_by_dir,
    _load_by_file_list,
    _load_images,
    Foldernames,
    load_data,
    save_checkpoint,
    save_data,
    extract_rotation_angle_from_filename,
    extract_rotation_angle_from_tiff_metadata,
)


# third party imports
import astropy.io.fits as fits
import numpy as np
import pytest
import tifffile

# standard imports
from copy import deepcopy
from functools import partial
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock


@pytest.fixture(scope="function")
def data_fixture(tmpdir):
    # dummy tiff image data
    data = np.ones((3, 3))
    #
    # TIFF files
    # -- valid tiff with generic name, no metadata
    generic_tiff = tmpdir / "generic_tiff_dir" / "generic.tiff"
    generic_tiff.parent.mkdir()
    tifffile.imwrite(str(generic_tiff), data)
    # -- valid tiff with good name for angle extraction, no metadata
    good_tiff = tmpdir / "good_tiff_dir" / "20191030_expname_0080_010_020_1960.tiff"
    good_tiff.parent.mkdir()
    tifffile.imwrite(str(good_tiff), data)
    # -- valid tiff with generic name, but has metadata
    ex_tags = [
        (65039, "s", 0, "RotationActual:0.1", True),
    ]
    metadata_tiff = tmpdir / "metadata_tiff_dir" / "metadata.tiff"
    metadata_tiff.parent.mkdir()
    tifffile.imwrite(str(metadata_tiff), data, extratags=ex_tags)
    # Fits files
    generic_fits = tmpdir / "generic_fits_dir" / "generic.fits"
    generic_fits.parent.mkdir()
    hdu = fits.PrimaryHDU(data)
    hdu.writeto(str(generic_fits))
    # return the tmp files
    return generic_tiff, good_tiff, metadata_tiff, generic_fits


def test_Foldernames(tmpdir):
    class TestFoldernames(param.Parameterized):
        f = Foldernames(doc="input folders")

    # test wrong input
    with pytest.raises(ValueError) as e:
        TestFoldernames(f=open(tmpdir / "temp.txt", "w"))

    assert str(e.value) == "Foldernames parameter 'TestFoldernames.f' only take str or pathlib.Path types"
    # test single directory
    tf = TestFoldernames(f=str(tmpdir))
    assert tf.f == str(tmpdir)
    tf = TestFoldernames(f=str(tmpdir))
    assert tf.f == str(tmpdir)
    # test multiple directories
    dir1, dir2 = tmpdir / "dir1", tmpdir / "dir2"
    dir1.mkdir()
    dir2.mkdir()
    tf = TestFoldernames(f=[str(dir1), str(dir2)])
    assert tf.f == [str(dir1), str(dir2)]
    tf = TestFoldernames(f=[dir1, dir2])
    assert tf.f == [str(dir1), str(dir2)]


@mock.patch("imars3d.backend.dataio.data._extract_rotation_angles")
@mock.patch("imars3d.backend.dataio.data._get_filelist_by_dir")
@mock.patch("imars3d.backend.dataio.data._load_by_file_list")
def test_load_data(
    mock__load_by_file_list: MagicMock, mock__get_filelist_by_dir: MagicMock, mock__extract_rotation_angles: MagicMock
):
    mock__load_by_file_list.return_value = (np.array([1.0]), np.array([2.0]), np.array([3.0]))
    mock__get_filelist_by_dir.return_value = ("1", "2", "3")
    mock__extract_rotation_angles.return_value = np.array([4.0])
    # error_0: incorrect input argument types
    with pytest.raises(ValueError):
        load_data(ct_files=1, ob_files=[], dc_files=[])
        load_data(ct_dir=1, ob_files=[])
        load_data(ct_files=[], ob_dir="/tmp")
        load_data(ct_files=[], ob_files=[], dc_files=[], ct_fnmatch=1)
        load_data(ct_files=[], ob_files=[], dc_files=[], ob_fnmatch=1)
        load_data(ct_files=[], ob_files=[], dc_files=[], dc_fnmatch=1)
        load_data(ct_files=[], ob_files=[], dc_files=[], max_workers="x")
        load_data(ct_dir=1, ob_dir="/tmp", dc_dir="/tmp")
        load_data(ct_dir="/tmp", ob_dir=1, dc_dir="/tmp")
    # error_1: out of bounds value
    with pytest.raises(ValueError):
        load_data(ct_files=[], ob_files=[], dc_files=[], max_workers=-1)
    # error_3: no valid signature found
    with pytest.raises(ValueError):
        load_data(ct_fnmatch=1)
    # case_0: load ct from directory, ob and dc from files
    rst = load_data(ct_dir="/tmp", ob_files=["3", "4"], dc_files=["5", "6"])
    np.testing.assert_almost_equal(np.array(rst).flatten(), np.arange(1, 5, dtype=float))
    # case_1: load data from file list
    rst = load_data(ct_files=["1", "2"], ob_files=["3", "4"], dc_files=["5", "6"])
    np.testing.assert_almost_equal(np.array(rst).flatten(), np.arange(1, 5, dtype=float))
    # case_2: load data from given directory
    rst = load_data(ct_dir="/tmp", ob_dir="/tmp", dc_dir="/tmp")
    np.testing.assert_almost_equal(np.array(rst).flatten(), np.arange(1, 5, dtype=float))


def test_forgiving_reader():
    # correct usage
    goodReader = lambda x: x
    assert _forgiving_reader(filename="test", reader=goodReader) == "test"
    # incorrect usage, but bypass the exception
    badReader = lambda x: x / 0
    assert _forgiving_reader(filename="test", reader=badReader) is None


def test_load_images(data_fixture):
    generic_tiff, good_tiff, metadata_tiff, generic_fits = list(map(str, data_fixture))
    func = partial(_load_images, desc="test", max_workers=2, tqdm_class=None)
    # error_0 case: unsupported file format
    incorrect_filelist = ["file1.bad", "file2.bad"]
    with pytest.raises(ValueError):
        rst = func(filelist=incorrect_filelist)
    # case_0: tiff
    tiff_filelist = [generic_tiff, good_tiff, metadata_tiff]
    rst = func(filelist=tiff_filelist)
    assert rst.shape == (3, 3, 3)
    # case_1: fits
    fits_filelist = [generic_fits, generic_fits]
    rst = func(filelist=fits_filelist)
    assert rst.shape == (2, 3, 3)


@mock.patch("imars3d.backend.dataio.data._load_images", return_value="a")
def test_load_by_file_list(_load_images):
    # error_0: ct empty
    with pytest.raises(ValueError):
        _load_by_file_list(ct_files=[], ob_files=[])
    # error_1: ob empty
    with pytest.raises(ValueError):
        _load_by_file_list(ct_files=["dummy"], ob_files=[])
    # case_0: load all three
    rst = _load_by_file_list(ct_files=["a.tiff"], ob_files=["a.tiff"], dc_files=["a.tiff"])
    assert rst == ("a", "a", "a")
    # case_1: load only ct and ob
    rst = _load_by_file_list(ct_files=["a.tiff"], ob_files=["a.tiff"])
    assert rst == ("a", "a", None)


def test_extract_rotation_angles(data_fixture):
    generic_tiff, good_tiff, metadata_tiff, generic_fits = list(map(str, data_fixture))
    # error_0: empty list
    with pytest.raises(ValueError):
        _extract_rotation_angles([])
    # error_1: unsupported file format for extracting from metadata
    with pytest.raises(ValueError):
        _extract_rotation_angles(["dummy.dummier", "dummy.dummier"])
    # case_0: extract from filename
    rst = _extract_rotation_angles([good_tiff, good_tiff])
    ref = np.array([10.02, 10.02])
    np.testing.assert_array_almost_equal(rst, ref)
    # case_1: extract from metadata
    rst = _extract_rotation_angles([metadata_tiff] * 3)
    ref = np.array([0.1, 0.1, 0.1])
    np.testing.assert_array_almost_equal(rst, ref)
    # case_2: mixed file types
    rst = _extract_rotation_angles([good_tiff, metadata_tiff, generic_tiff, generic_fits])
    ref = np.array([10.02, 0.1, np.nan, np.nan])
    np.testing.assert_array_equal(rst, ref)
    # case_3: all files without extractable angles
    rst = _extract_rotation_angles([generic_tiff, generic_fits])
    assert rst is None


def test_extract_rotation_angle_from_filename():
    # Test cases for extract_rotation_angle_from_filename
    assert extract_rotation_angle_from_filename("20191030_sample_0070_300_440_0520.tiff") == 300.44
    assert extract_rotation_angle_from_filename("20191030_sample_0071_301_441_0521.tif") == 301.441
    assert extract_rotation_angle_from_filename("20191030_sample_0072_302_442_0522.fits") == 302.442
    assert extract_rotation_angle_from_filename("generic_file.tiff") is None


def test_extract_rotation_angle_from_tiff_metadata(tmpdir):
    # Create a TIFF file with rotation angle in metadata
    data = np.ones((3, 3))
    filename = str(tmpdir / "metadata.tiff")
    tifffile.imwrite(filename, data, extratags=[(65039, "s", 0, "RotationActual:0.5", True)])

    assert extract_rotation_angle_from_tiff_metadata(filename) == 0.5
    assert extract_rotation_angle_from_tiff_metadata("non_existent_file.tiff") is None


@pytest.fixture(scope="module")
def ext_tags():
    return {
        "ct": [
            (65026, "s", 0, "ManufacturerStr:Test", True),
            (65027, "s", 0, "ExposureTime:70.000000", True),
            (65068, "s", 0, "MotSlitHR.RBV:10.000000", True),
            (65070, "s", 0, "MotSlitHL.RBV:20.000000", True),
            (65066, "s", 0, "MotSlitVT.RBV:10.000000", True),
            (65068, "s", 0, "MotSlitHR.RBV:10.000000", True),
        ],
        "dc": [(65026, "s", 0, "ManufacturerStr:Test", True), (65027, "s", 0, "ExposureTime:70.000000", True)],
        "ct_alt": [
            (65026, "s", 0, "ManufacturerStr:Test", True),
            (65027, "s", 0, "ExposureTime:71.000000", True),
            (65068, "s", 0, "MotSlitHR.RBV:11.000000", True),
            (65070, "s", 0, "MotSlitHL.RBV:21.000000", True),
            (65066, "s", 0, "MotSlitVT.RBV:11.000000", True),
            (65068, "s", 0, "MotSlitHR.RBV:11.000000", True),
        ],
    }


@pytest.fixture(scope="function")
def tiff_with_metadata(tmpdir, ext_tags):
    # create testing tiff images
    data = np.ones((3, 3))
    # write testing data
    ct = tmpdir / "ct_dir" / "test_ct.tiff"
    ct.parent.mkdir()
    tifffile.imwrite(str(ct), data, extratags=ext_tags["ct"])
    ob = tmpdir / "ob_dir" / "test_ob.tiff"
    ob.parent.mkdir()
    tifffile.imwrite(str(ob), data, extratags=ext_tags["ct"])
    dc = tmpdir / "dc_dir" / "test_dc.tiff"
    dc.parent.mkdir()
    tifffile.imwrite(str(dc), data, extratags=ext_tags["dc"])
    ct_alt = tmpdir / "ct_alt_dir" / "test_ct_alt.tiff"
    ct_alt.parent.mkdir()
    tifffile.imwrite(str(ct_alt), data, extratags=ext_tags["ct_alt"])
    return ct, ob, dc, ct_alt


def test_get_filelist_by_dir(tiff_with_metadata):
    ct, ob, dc, ct_alt = list(map(str, tiff_with_metadata))
    ct_dir = Path(ct).parent
    ob_dir = Path(ob).parent
    dc_dir = Path(dc).parent
    ct_alt_dir = Path(ct_alt).parent
    # error_0: ct_dir does not exists
    with pytest.raises(ValueError):
        _get_filelist_by_dir(ct_dir="dummy", ob_dir="/tmp", dc_dir="/tmp")
    # error_1: ob_dir does not exists
    with pytest.raises(ValueError):
        _get_filelist_by_dir(ct_dir="/tmp", ob_dir="dummy", dc_dir="/tmp")
    # case_0: load all three
    rst = _get_filelist_by_dir(
        ct_dir=ct_dir,
        ob_dir=ob_dir,
        dc_dir=dc_dir,
        ct_fnmatch="*.tiff",
        ob_fnmatch="*.tiff",
        dc_fnmatch="*.tiff",
    )
    assert rst == ([ct], [ob], [dc])
    # case_1: load ct and ob, skipping dc
    rst = _get_filelist_by_dir(
        ct_dir=ct_dir,
        ob_dir=ob_dir,
        ct_fnmatch="*.tiff",
        ob_fnmatch="*.tiff",
        dc_fnmatch="*.tiff",
    )
    assert rst == ([ct], [ob], [])
    # case_2: load ct, and detect ob and dc from metadata
    rst = _get_filelist_by_dir(
        ct_dir=ct_dir,
        ob_dir=ob_dir,
        dc_dir=dc_dir,
        ct_fnmatch="*.tiff",
        ob_fnmatch=None,
        dc_fnmatch=None,
    )
    assert rst == ([ct], [ob], [dc])
    # case_3: load ct, and detect ob from metadata
    rst = _get_filelist_by_dir(
        ct_dir=ct_dir,
        ob_dir=ob_dir,
        ct_fnmatch="*.tiff",
        ob_fnmatch=None,
    )
    assert rst == ([ct], [ob], [])
    # case_4: load ct_alt, and find no match ob
    rst = _get_filelist_by_dir(
        ct_dir=ct_alt_dir,
        ob_dir=ob_dir,
        ct_fnmatch="*.tiff",
        ob_fnmatch=None,
    )
    assert rst == ([ct_alt], [], [])
    # case_5: did not find any match for ct
    rst = _get_filelist_by_dir(
        ct_dir=ct_dir,
        ob_dir=ob_dir,
        ct_fnmatch="*.not_exist",
        ob_fnmatch=None,
    )
    assert rst == ([], [], [])


def test_get_filelist_by_dirs(tmpdir, caplog, ext_tags, tiff_with_metadata):
    ct, ob_1, dc_1, ct_alt = tiff_with_metadata
    ct_dir = ct.parent
    ct_alt_dir = ct_alt.parent
    # additional open-beam and dark-field files
    data = np.ones((3, 3))
    ob_2 = tmpdir / "ob_dir_2" / "test_ob.tiff"
    ob_2.parent.mkdir()
    tifffile.imwrite(str(ob_2), data, extratags=ext_tags["ct"])
    ob_dir = [ob_1.parent, ob_2.parent]
    dc_2 = tmpdir / "dc_dir_2" / "test_dc.tiff"
    dc_2.parent.mkdir()
    tifffile.imwrite(str(dc_2), data, extratags=ext_tags["dc"])
    dc_dir = [dc_1.parent, dc_2.parent]
    # convert the golden data to string for ease of comparison
    ct, ct_alt, ob_1, ob_2, dc_1, dc_2 = [str(x) for x in (ct, ct_alt, ob_1, ob_2, dc_1, dc_2)]
    common = dict(
        ct_dir=ct_dir, ob_dir=ob_dir, dc_dir=dc_dir, ct_fnmatch="*.tiff", ob_fnmatch="*.tiff", dc_fnmatch="*.tiff"
    )
    # corner case, open-beam directory is not a valid entry
    with pytest.raises(ValueError) as e:
        kwargs = deepcopy(common)
        kwargs["ob_dir"] = open(ct, "r")
        _get_filelist_by_dir(**kwargs)
    assert "ob_dir must be either a string or a list of strings" == str(e.value)
    # corner case, dark-field directory is not a valid entry
    with pytest.raises(ValueError) as e:
        kwargs = deepcopy(common)
        kwargs["dc_dir"] = open(ct, "r")
        _get_filelist_by_dir(**kwargs)
    assert "dc_dir must be either a string or a list of strings" == str(e.value)
    # corner case, dark-field directory doesn't exist
    kwargs = deepcopy(common)
    kwargs["dc_dir"].append(Path("/tmp/tHIs_dOEs_nOt_EXIsT"))
    caplog.clear()
    rst = _get_filelist_by_dir(**kwargs)
    assert "/tmp/tHIs_dOEs_nOt_EXIsT does not exist, ignoring" in caplog.text
    assert rst == ([ct], [ob_1, ob_2], [dc_1, dc_2])
    # case_0: load all three
    rst = _get_filelist_by_dir(**common)
    assert rst == ([ct], [ob_1, ob_2], [dc_1, dc_2])
    # case_1: load ct and ob, skipping dc
    kwargs = deepcopy(common)
    del kwargs["dc_dir"]
    rst = _get_filelist_by_dir(**kwargs)
    assert rst == ([ct], [ob_1, ob_2], [])
    # case_2: load ct, and detect ob and dc from metadata
    kwargs = deepcopy(common)
    kwargs.update(dict(ob_fnmatch=None, dc_fnmatch=None))
    rst = _get_filelist_by_dir(**kwargs)
    assert rst == ([ct], [ob_1, ob_2], [dc_1, dc_2])
    # case_3: load ct, and detect ob from metadata
    caplog.clear()
    rst = _get_filelist_by_dir(
        ct_dir=ct_dir,
        ob_dir=ob_dir,
        ct_fnmatch="*.tiff",
        ob_fnmatch=None,
    )
    assert "dc_dir is None, ignoring" in caplog.text
    assert rst == ([ct], [ob_1, ob_2], [])
    # case_4: load ct_alt, and find no match ob
    rst = _get_filelist_by_dir(
        ct_dir=ct_alt_dir,
        ob_dir=ob_dir,
        ct_fnmatch="*.tiff",
        ob_fnmatch=None,
    )
    assert rst == ([ct_alt], [], [])
    # case_5: did not find any match for ct
    rst = _get_filelist_by_dir(
        ct_dir=ct_dir,
        ob_dir=ob_dir,
        ct_fnmatch="*.not_exist",
        ob_fnmatch=None,
    )
    assert rst == ([], [], [])


def test_save_data_fail():
    with pytest.raises(ValueError):
        save_data()


def check_savefiles(direc: Path, prefix: str, num_files: int = 3, has_omega=False):
    assert direc.exists()
    assert direc.is_dir()
    filepaths = [direc / item for item in direc.iterdir()]
    assert len(filepaths) == num_files
    for filepath in filepaths:
        print(filepath)
        assert filepath.is_file()
        if has_omega and filepath.name == "rot_angles.npy":
            continue
        assert filepath.suffix == ".tiff"
        # the names are zero-padded
        assert "_0000" in filepath.name
        # verify the file starts with the name
        assert filepath.name.startswith(prefix)


def create_fake_data():
    return np.zeros((3, 3, 3)) + 1.0


@pytest.mark.parametrize("name", ["junk", ""])  # gets default name
def test_save_data(name, tmpdir):
    data = create_fake_data()
    omegas = np.asarray([1.0, 2.0, 3.0])
    # run the code
    numfiles = 3
    if name:
        outputdir = save_data(data=data, outputbase=tmpdir, name=name, rot_angles=omegas)
        numfiles += 1
    else:
        outputdir = save_data(data=data, outputbase=tmpdir)
    print(outputdir)

    # check the result
    if name:
        prefix = name + "_"
    else:
        prefix = "save_data_"  # special name

    assert outputdir.name.startswith(prefix), str(outputdir.name)
    check_savefiles(outputdir, prefix, has_omega=bool(name), num_files=numfiles)


def test_save_data_subdir(tmpdir):
    name = "subdirtest"
    data = create_fake_data()
    # run the code
    outputdir = save_data(data=data, outputbase=tmpdir, name=name)
    assert outputdir.name.startswith(f"{name}_"), str(outputdir)
    # check the result
    check_savefiles(outputdir, "subdirtest_")


def test_save_checkpoint(tmpdir):
    name = "chktest"
    data = create_fake_data()

    # check without omegas
    subdir = tmpdir / "omegas_false"
    subdir.mkdir()
    outputdir = save_checkpoint(data=data, outputbase=subdir, name=name)
    assert outputdir.name.startswith(f"{name}_chkpt_"), str(outputdir)
    check_savefiles(outputdir, "chk", num_files=3)
    outputdir = save_checkpoint(data=data, outputbase=tmpdir, name=name)

    # check with omegas
    subdir = tmpdir / "omegas_true"
    subdir.mkdir()
    omegas = np.asarray([1.0, 2.0, 3.0])
    outputdir = save_checkpoint(data=data, outputbase=subdir, name=name, rot_angles=omegas)
    assert outputdir.name.startswith(f"{name}_chkpt_"), str(outputdir)
    check_savefiles(outputdir, "chk", num_files=4, has_omega=True)


if __name__ == "__main__":
    pytest.main([__file__])
