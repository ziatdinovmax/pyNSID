from __future__ import division, print_function, unicode_literals, absolute_import
import unittest
import sys
sys.path.append("../pyNSID/")

class TestImport(unittest.TestCase):

    def test_basic(self):
        import pyNSID as nsid
        print(nsid.__version__)
        self.assertTrue(True)

class TestWritingUtilities(unittest.TestCase):

    def test_create_empty_dataset(self):
        from pyNSID.io.hdf_io import create_empty_dataset
        import h5py
        from os import remove

        h5_f = h5py.File('test.h5', 'w')
        h5_group = h5_f.create_group('MyGroup')
        shape = (10,10,100)
        dataset_name = 'test_dataset'
        empty_dset = create_empty_dataset(shape, h5_group, dataset_name)

        assert type(empty_dset)==h5py._hl.dataset.Dataset, "Output is not a h5py dataset"
        assert empty_dset.shape == shape, "Output shape is {} but should be {}".format(empty_dset.shape, shape)

        #close file, delete
        h5_f.close()
        remove('test.h5')

    def test_create_nsid_dataset(self):
        from pyNSID.io.hdf_io import write_nsid_dataset
        import h5py
        import sidpy as sid
        import numpy as np

        h5_f = h5py.File('test.h5', 'w')
        h5_group = h5_f.create_group('MyGroup')
        shape = (10,10,32)
        data = np.random.randn(10,10,32)
        data_set = sid.Dataset.from_array(data[:,:,:], name='Image')

        data_set.set_dimension(0, sid.Dimension(np.arange(data_set.shape[0]),
                                                name='x', units='um', quantity='Length',
                                                dimension_type='spatial'))
        data_set.set_dimension(1, sid.Dimension(np.linspace(-2, 2, num=data_set.shape[1], endpoint=True),
                                                'y', units='um', quantity='Length',
                                                dimension_type='spatial'))
        data_set.set_dimension(2, sid.Dimension(np.sin(np.linspace(0, 2 * np.pi, num=data_set.shape[2])),
                                                'bias'))

        data_set.units = 'nm'
        data_set.source = 'CypherEast2'
        data_set.quantity = 'Excaliburs'
        h5_dset = write_nsid_dataset(data_set, h5_group, main_data_name='test2', verbose=True)

        assert type(h5_dset) == h5py._hl.dataset.Dataset, "Output is not a h5py dataset"
        assert h5_dset.shape == shape, "Output shape is {} but should be {}".format(h5_dset.shape, shape)

        for ind in range(len(sid.hdf_utils.get_attr(h5_dset, 'DIMENSION_LABELS'))):
            assert sid.hdf_utils.get_attr(h5_dset, 'DIMENSION_LABELS')[ind] == [data_set.dim_0.name,
                        data_set.dim_1.name, data_set.dim_2.name][ind], \
                "Dimension name not correctly written, should be {} but is {} in file".format([data_set.dim_0.name,
                        data_set.dim_1.name, data_set.dim_2.name][ind], sid.hdf_utils.get_attr(h5_dset, 'DIMENSION_LABELS')[ind])
        assert sid.hdf_utils.get_attr(h5_dset, 'quantity') == data_set.quantity, \
            "Quantity attribute not correctly written, should be {} but is {} in file".format(data_set.quantity, sid.hdf_utils.get_attr(h5_dset, 'quantity'))

        assert sid.hdf_utils.get_attr(h5_dset, 'source') == data_set.source, \
            "Source attribute not correctly written, should be {} but is {} in file".format(data_set.source,
                                                                                              sid.hdf_utils.get_attr(
                                                                                                  h5_dset, 'source'))
        assert sid.hdf_utils.get_attr(h5_dset, 'units') == data_set.units, \
            "Source attribute not correctly written, should be {} but is {} in file".format(data_set.units,
                                                                                            sid.hdf_utils.get_attr(
                                                                                                h5_dset, 'units'))


    def test_write_results(self):
        from pyNSID.io.hdf_io import write_results
        import h5py
        import sidpy as sid
        import numpy as np

        h5_f = h5py.File('test.h5', 'w')
        h5_group = h5_f.create_group('MyGroup')
        shape = (5, 15, 16)
        data = np.random.randn(shape[0], shape[1], shape[2])
        data_set = sid.Dataset.from_array(data[:, :, :], name='Image')
        write_results(h5_group, dataset=data_set, attributes=None, process_name='TestProcess')



