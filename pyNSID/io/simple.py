# -*- coding: utf-8 -*-
"""
Lower-level and simpler NSID-specific HDF5 utilities that facilitate
higher-level data operations in model.py

Created on Tue Aug  3 21:14:25 2020

@author: Gerd Duscher, and Suhas Somnath
"""
from __future__ import division, print_function, absolute_import, unicode_literals
import sys
import h5py
import numpy as np
import dask.array as da

from sidpy.base.num_utils import contains_integers
from sidpy.base.string_utils import validate_single_string_arg, \
    clean_string_att
from sidpy.hdf.hdf_utils import get_auxiliary_datasets, link_h5_obj_as_alias, \
    get_attr, write_book_keeping_attrs, write_simple_attrs, copy_dataset, \
    validate_h5_objs_in_same_h5_file
from sidpy.hdf import hdf_utils as hut
from sidpy import Dimension

if sys.version_info.major == 3:
    unicode = str


def get_all_main(parent, verbose=False):
    """
    Simple function to recursively print the contents of an hdf5 group
    Parameters
    ----------
    parent : :class:`h5py.Group`
        HDF5 Group to search within
    verbose : bool, optional. Default = False
        If true, extra print statements (usually for debugging) are enabled
    Returns
    -------
    main_list : list of h5py.Dataset
        The datasets found in the file that meet the 'Main Data' criteria.
    """
    if not isinstance(parent, (h5py.Group, h5py.File)):
        raise TypeError('parent should be a h5py.File or h5py.Group object')

    from .nsi_data import NSIDataset

    main_list = list()

    def __check(name, obj):
        if verbose:
            print(name, obj)
        if isinstance(obj, h5py.Dataset):
            if verbose:
                print(name, 'is an HDF5 Dataset.')
            ismain = check_if_main(obj)
            if ismain:
                if verbose:
                    print(name, 'is a `Main` dataset.')
                main_list.append(NSIDataset(obj))

    if verbose:
        print('Checking the group {} for `Main` datasets.'.format(parent.name))
    parent.visititems(__check)

    return main_list


def find_dataset(h5_group, dset_name):
    """
    Uses visit() to find all datasets with the desired name
    Parameters
    ----------
    h5_group : :class:`h5py.Group`
        Group to search within for the Dataset
    dset_name : str
        Name of the dataset to search for
    Returns
    -------
    datasets : list
        List of [Name, object] pairs corresponding to datasets that match `ds_name`.
    """
    from .nsi_data import NSIDataset

    # print 'Finding all instances of', ds_name
    datasets = []

    for obj in hut.find_dataset(h5_group, dset_name):
        try:
            datasets.append(NSIDataset(obj))
        except TypeError:
            datasets.append(obj)

    return datasets


def validate_main_dset(h5_main, must_be_h5):
    """
    Checks to make sure that the provided object is a NSID main dataset
    Errors in parameters will result in Exceptions
    Parameters
    ----------
    h5_main : h5py.Dataset or numpy.ndarray or Dask.array.core.array
        object that represents the NSID main data
    must_be_h5 : bool
        Set to True if the expecting an h5py.Dataset object.
        Set to False if expecting a numpy.ndarray or Dask.array.core.array
    Returns
    -------
    """
    # Check that h5_main is a dataset
    if must_be_h5:
        if not isinstance(h5_main, h5py.Dataset):
            raise TypeError('{} is not an HDF5 Dataset object.'.format(h5_main))
    else:
        if not isinstance(h5_main, (np.ndarray, da.core.Array)):
            raise TypeError('raw_data should either be a np.ndarray or a '
                            'da.core.Array')

    # Check dimensionality
    if len(h5_main.shape) != len(h5_main.dims):
        raise ValueError('Main data does not have full set of dimensional '
                         'scales. Provided object has shape: {} but only {} '
                         'dimensional scales'
                         ''.format(h5_main.shape, len(h5_main.dims)))


def validate_anc_h5_dsets(h5_inds, h5_vals, main_shape, is_spectroscopic=True):
    """
    Checks ancillary HDF5 datasets against shape of a main dataset.
    Errors in parameters will result in Exceptions
    Parameters
    ----------
    h5_inds : h5py.Dataset
        HDF5 dataset corresponding to the ancillary Indices dataset
    h5_vals : h5py.Dataset
        HDF5 dataset corresponding to the ancillary Values dataset
    main_shape : array-like
        Shape of the main dataset expressed as a tuple or similar
    is_spectroscopic : bool, Optional. Default = True
        set to True if ``dims`` correspond to Spectroscopic Dimensions.
        False otherwise.
    """
    if not isinstance(h5_inds, h5py.Dataset):
        raise TypeError('h5_inds must be a h5py.Dataset object')
    if not isinstance(h5_vals, h5py.Dataset):
        raise TypeError('h5_vals must be a h5py.Dataset object')
    if h5_inds.shape != h5_vals.shape:
        raise ValueError('h5_inds: {} and h5_vals: {} should be of the same '
                         'shape'.format(h5_inds.shape, h5_vals.shape))
    if isinstance(main_shape, (list, tuple)):
        if not contains_integers(main_shape, min_val=1) or \
                len(main_shape) != 2:
            raise ValueError("'main_shape' must be a valid HDF5 dataset shape")
    else:
        raise TypeError('main_shape should be of the following types:'
                        'h5py.Dataset, tuple, or list. {} provided'
                        ''.format(type(main_shape)))

    if h5_inds.shape[is_spectroscopic] != main_shape[is_spectroscopic]:
        raise ValueError('index {} in shape of h5_inds: {} and main_data: {} '
                         'should be equal'.format(int(is_spectroscopic),
                                                  h5_inds.shape, main_shape))


def validate_dims_against_main(main_shape, dims, is_spectroscopic=True):
    """
    Checks Dimension objects against a given shape for main datasets.
    Errors in parameters will result in Exceptions
    Parameters
    ----------
    main_shape : array-like
        Tuple or list with the shape of the main data
    dims : iterable
        List of Dimension objects
    is_spectroscopic : bool, Optional. Default = True
        set to True if ``dims`` correspond to Spectroscopic Dimensions.
        False otherwise.
    """
    if not isinstance(main_shape, (list, tuple)):
        raise TypeError('main_shape should be a list or tuple. Provided object'
                        ' was of type: {}'.format(type(main_shape)))
    if len(main_shape) != 2:
        raise ValueError('"main_shape" should be of length 2')
    contains_integers(main_shape, min_val=1)

    if isinstance(dims, Dimension):
        dims = [dims]
    elif not isinstance(dims, (list, tuple)):
        raise TypeError('"dims" must be a list or tuple of nsid.Dimension '
                        'objects. Provided object was of type: {}'
                        ''.format(type(dims)))
    if not all([isinstance(obj, Dimension) for obj in dims]):
        raise TypeError('One or more objects in "dims" was not nsid.Dimension')

    if is_spectroscopic:
        main_dim = 1
        dim_category = 'Spectroscopic'
    else:
        main_dim = 0
        dim_category = 'Position'

    # TODO: This is where the dimension type will need to be taken into account
    lhs = main_shape[main_dim]
    rhs = np.product([len(x.values) for x in dims])
    if lhs != rhs:
        raise ValueError(dim_category +
                         ' dimensions in main data of size: {} do not match '
                         'with product of values in provided Dimension objects'
                         ': {}'.format(lhs, rhs))


def check_if_main(h5_main, verbose=False):
    """
    Checks the input dataset to see if it has all the necessary
    features to be considered a Main dataset.  This means it is
    dataset has dimensions of correct size and has the following attributes:
    * quantity
    * units
    * main_data_name
    * data_type
    * modality
    * source
    In addition, the shapes of the ancillary matrices should match with that of
    h5_main
    Parameters
    ----------
    h5_main : HDF5 Dataset
        Dataset of interest
    verbose : Boolean (Optional. Default = False)
        Whether or not to print statements
    Returns
    -------
    success : Boolean
        True if all tests pass
    """
    try:
        validate_main_dset(h5_main, True)
    except Exception as exep:
        if verbose:
            print(exep)
        return False

    # h5_name = h5_main.name.split('/')[-1]
    h5_group = h5_main.parent

    # success = True

    # Check for Datasets
    
    attrs_names = ['dimension_type', 'name', 'nsid_version', 'quantity', 'units', ]
    attr_success = []
    length_success = []
    dset_success = []
    # Check for Validity of Dimensional Scales
    for i, dimension in enumerate(h5_main.dims):
        # check for all required attributes
        h5_dim_dset = h5_group[dimension.label]
        attr_success.append(np.all([att in h5_dim_dset.attrs for att in attrs_names]))
        dset_success.append(np.all([attr_success, isinstance(h5_dim_dset, h5py.Dataset)]))
        # dimensional scale has to be 1D
        if len(h5_dim_dset.shape) == 1:
            # and of the same length as the shape of the dataset
            length_success.append(h5_main.shape[i] == h5_dim_dset.shape[0])
        else:
            length_success.append(False)
    # We have the list now and can get error messages according to which dataset is bad or not.
    if np.all([np.all(attr_success), np.all(length_success), np.all(dset_success)]):
        if verbose:
            print('Dimensions: All Attributes: ', np.all(attr_success))
            print('Dimensions: All Correct Length: ', np.all(length_success))
            print('Dimensions: All h5 Datasets: ', np.all(dset_success))
    else:
        print('length of dimension scale {length_success.index(False)} is wrong')
        print('attributes in dimension scale {attr_success.index(False)} are wrong')
        print('dimension scale {dset_success.index(False)} is not a dataset')
        return False

    # Check for all required attributes in dataset
    main_attrs_names = ['quantity', 'units', 'main_data_name', 'data_type', 'modality', 'source']
    main_attr_success = np.all([att in h5_main.attrs for att in main_attrs_names])
    if verbose:
        print('All Attributes in dataset: ', main_attr_success)
    if not main_attr_success:
        if verbose:
            print('{} does not have the mandatory attributes'.format(h5_main.name))
        return False

    for attr_name in main_attrs_names:
        val = get_attr(h5_main, attr_name)
        if not isinstance(val, (str, unicode)):
            if verbose:
                print('Attribute {} of {} found to be {}. Expected a string'.format(attr_name, h5_main.name, val))
            return False

    return main_attr_success


def link_as_main(h5_main, dim_dict):
    """
    Attaches datasets as h5 Dimensional Scales to  `h5_main`
    Parameters
    ----------
    h5_main : h5py.Dataset
        N-dimensional Dataset which will have the references added as h5 Dimensional Scales
    dim_dict: dictionary with dimensional oreder as key and items are datasets to be used as h5 Dimensional Scales 

    Returns
    -------
    pyNSID.NSIDataset
        NSIDataset version of h5_main now that it is a NSID Main dataset
    """
    if not isinstance(h5_main, h5py.Dataset):
        raise TypeError('h5_main should be a h5py.Dataset object')

    h5_parent_group = h5_main.parent
    main_shape = h5_main.shape
    ######################
    # Validate Dimensions
    ######################
    # An N dimensional dataset should have N items in the dimension dictionary
    if len(dim_dict) != len(main_shape):
        raise ValueError('Incorrect number of dimensions: {} provided to support main data, of shape: {}'
                         .format(len(dim_dict), main_shape))
    if set(range(len(main_shape))) != set(dim_dict.keys()):
        raise KeyError('')
    
    # dimensions_correct = []
    dim_names = []
    for index, dim_exp_size in enumerate(main_shape):
        this_dim = dim_dict[index]
        if isinstance(this_dim, h5py.Dataset):
            error_message = validate_dimensions(this_dim, main_shape[index])
            if len(error_message) > 0:
                raise TypeError('Dimension {} has the following error_message:\n'.format(index), error_message)
            else:
                # if this_dim.name not in dim_names:
                if this_dim.name not in dim_names:  # names must be unique
                    dim_names.append(this_dim.name)
                else:
                    raise TypeError('All dimension names must be unique, found {} twice'.format(this_dim.name))
                if this_dim.file != h5_parent_group.file:
                    this_dim = copy_dataset(this_dim, h5_parent_group, verbose=False)
        else: 
            raise TypeError('Items in dictionary must all  be h5py.Datasets !')

    ################
    # Attach Scales
    ################
    for i, this_dim_dset in dim_dict.items():
        this_dim_dset.make_scale(this_dim_dset.attrs['name'])
        h5_main.dims[int(i)].label = this_dim_dset.attrs['name']
        h5_main.dims[int(i)].attach_scale(this_dim_dset)
        
    from .nsi_data import NSIDataset
    try:
        # If all other conditions are satisfied
        return NSIDataset(h5_main)
    except TypeError:
        # If some other conditions are yet to be satisfied
        return h5_main


def get_source_dataset(h5_group):
    """
    Find the name of the source dataset used to create the input `h5_group`,
    so long as the source dataset is in the same HDF5 file
    Parameters
    ----------
    h5_group : :class:`h5py.Group`
        Child group whose source dataset will be returned
    Returns
    -------
    h5_source : NSIDataset object
        Main dataset from which this group was generated
    """
    if not isinstance(h5_group, h5py.Group):
        raise TypeError('h5_group should be a h5py.Group object')

    h5_parent_group = h5_group.parent
    group_name = h5_group.name.split('/')[-1]
    # What if the group name was not formatted according to Pycroscopy rules?
    name_split = group_name.split('-')
    if len(name_split) != 2:
        raise ValueError("The provided group's name could not be split by '-' as expected in "
                         "SourceDataset-ProcessName_000")
    h5_source = h5_parent_group[name_split[0]]

    if not isinstance(h5_source, h5py.Dataset):
        raise ValueError('Source object was not a dataset!')

    from .nsi_data import NSIDataset

    return NSIDataset(h5_source)


def copy_main_attributes(h5_main, h5_new):
    """
    Copies the units and quantity name from one dataset to another
    Parameters
    ----------
    h5_main : h5py.Dataset
        Dataset containing the target attributes
    h5_new : h5py.Dataset
        Dataset to which the target attributes are to be copied
    """
    for param, param_name in zip([h5_main, h5_new], ['h5_main', 'h5_new']):
        if not isinstance(param, h5py.Dataset):
            raise TypeError(param_name + ' should be a h5py.Dataset object')

    for att_name in ['quantity', 'units']:
        if att_name not in h5_main.attrs:
            raise KeyError('Attribute: {} does not exist in {}'.format(att_name, h5_main))
        val = get_attr(h5_main, att_name)
        h5_new.attrs[att_name] = clean_string_att(val)


def copy_region_refs(h5_source, h5_target):
    """
    Check the input dataset for plot groups, copy them if they exist
    Also make references in the Spectroscopic Values and Indices tables
    Parameters
    ----------
    h5_source : HDF5 Dataset
            source dataset to copy references from
    h5_target : HDF5 Dataset
            target dataset the references from h5_source are copied to
    """
    '''
    Check both h5_source and h5_target to ensure that are Main
    '''
    # TODO: Move this vestige to pycroscopy. Use copy_all_region_refs instead
    are_main = all([check_if_main(h5_source), check_if_main(h5_target)])
    if not all([isinstance(h5_source, h5py.Dataset), isinstance(h5_target, h5py.Dataset)]):
        raise TypeError('Inputs to copy_region_refs must be HDF5 Datasets')

    # It is OK if objects are in different files

    for key in h5_source.attrs.keys():
        if not isinstance(h5_source.attrs[key], h5py.RegionReference):
            continue

        if are_main:  # TODO: Region Reference copy not implemented
            # for dim in h5_source_inds.dims:
            # ref_inds = simple_region_ref_copy(h5_source, h5_target, key)

            # else:
            '''
            Spectroscopic dimensions are different.
            Do the dimension reducing copy.
            '''
            # ref_inds = copy_reg_ref_reduced_dim(h5_source, h5_target, h5_source_inds, h5_spec_inds, key)

            '''
            Create references for Spectroscopic Indices and Values
            Set the end-point of each hyperslab in the position dimension to the number of
            rows in the index array
            '''
            """
            ref_inds[:, 1, 0][ref_inds[:, 1, 0] > h5_spec_inds.shape[0]] = h5_spec_inds.shape[0] - 1
            spec_inds_ref = create_region_reference(h5_spec_inds, ref_inds)
            h5_spec_inds.attrs[key] = spec_inds_ref
            spec_vals_ref = create_region_reference(h5_spec_vals, ref_inds)
            h5_spec_vals.attrs[key] = spec_vals_ref
            """

        else:
            '''
            If not main datasets, then only simple copy can be used.
            '''
            simple_region_ref_copy(h5_source, h5_target, key)


def validate_dimensions(this_dim, dim_shape):
    """
    Checks if the provided object is an h5 dataset.
    A valid dataset to be uses as dimension must be 1D not a compound data type but 'simple'.
    Such a dataset must have  ancillary attributes 'name', quantity', 'units', and 'dimension_type',
    which have to be of  types str, str, str, and bool respectively and not empty
    If it is not valid of dataset, Exceptions are raised.

    Parameters
    ----------
    this_dim : h5 dataset
        with non empty attributes 'name', quantity', 'units', and 'dimension_type'
    dim_shape : required length of dataset

    Returns
    -------
    error_message: string, empty if ok.
    """

    if not isinstance(this_dim, h5py.Dataset):
        error_message = 'this Dimension must be a h5 Dataset'
        return error_message

    error_message = ''
    # Is it 1D?
    if len(this_dim.shape) != 1:
        error_message += ' High dimensional datasets are not allowed as dimensions;\n'
    # Does this dataset have a "simple" dtype - no compound data type allowed!
    # is the shape matching with the main dataset?
    if len(this_dim) != dim_shape:
        error_message += ' Dimension has wrong length;\n'
    # Does it contain some ancillary attributes like 'name', quantity', 'units', and 'dimension_type'
    necessary_attributes = ['name', 'quantity', 'units', 'dimension_type']
    for key in necessary_attributes:
        if key not in this_dim.attrs:
            error_message += 'Missing {key} attribute in dimension;\n '.format(key)
        elif not isinstance(this_dim.attrs[key], str):
            error_message += '{} attribute in dimension should be string;\n '.format(key)

    return error_message


def validate_main_dimensions(main_shape, dim_dict, h5_parent_group):
    # Each item could either be a Dimension object or a HDF5 dataset
    # Collect the file within which these ancillary HDF5 objects are present if they are provided
    which_h5_file = {}
    # Also collect the names of the dimensions. We want them to be unique
    dim_names = []

    dimensions_correct = []
    for index, dim_exp_size in enumerate(main_shape):
        this_dim = dim_dict[index]
        if isinstance(this_dim, h5py.Dataset):
            error_message = validate_dimensions(this_dim, main_shape[index])

            # All these checks should live in a helper function for cleanliness

            if len(error_message) > 0:
                print('Dimension {} has the following error_message:\n'.format(index), error_message)

            else:
                if this_dim.name not in dim_names:  # names must be unique
                    dim_names.append(this_dim.name)
                else:
                    raise TypeError('All dimension names must be unique, found'
                                    ' {} twice'.format(this_dim.name))

                # are all datasets in the same file?
                if this_dim.file != h5_parent_group.file:
                    from .simple import copy_dataset

                    this_dim = copy_dataset(this_dim, h5_parent_group, verbose=True)

        elif isinstance(this_dim, Dimension):
            # is the shape matching with the main dataset?
            dimensions_correct.append(len(this_dim.values) == dim_exp_size)
            # Is there a HDF5 dataset with the same name already in the provided group
            # where this dataset will be created?
            if this_dim.name in h5_parent_group:
                # check if this object with the same name is a dataset and if it satisfies the above tests
                if isinstance(h5_parent_group[this_dim.name], h5py.Dataset):
                    print('needs more checking')
                    dimensions_correct[-1] = False
                else:
                    dimensions_correct[-1] = True
            # Otherwise, just append the dimension name for the uniqueness test
            elif this_dim.name not in dim_names:
                dim_names.append(this_dim.name)
            else:
                dimensions_correct[-1] = False
        else:
            raise TypeError('Values of dim_dict should either be h5py.Dataset '
                            'objects or Dimension. Object at index: {} was of '
                            'type: {}'.format(index, index))

        for dim in which_h5_file:
            if which_h5_file[dim] != h5_parent_group.file.filename:
                print('need to copy dimension', dim)
        for i, dim_name in enumerate(dim_names[:-1]):
            if dim_name in dim_names[i + 1:]:
                print(dim_name, ' is not unique')

    return dimensions_correct
