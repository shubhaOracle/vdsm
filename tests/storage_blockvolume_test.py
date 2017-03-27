#
# Copyright 2015-2016 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

from contextlib import contextmanager

from vdsm.config import config
from vdsm.constants import MEGAB
from vdsm.constants import GIB
from vdsm.storage import constants as sc
from vdsm.storage import exception as se

from monkeypatch import MonkeyPatch
from storagetestlib import fake_env
from storagetestlib import qemu_pattern_write
from storagetestlib import make_qemu_chain
from storage import blockVolume
from storage.blockVolume import BlockVolume
from testlib import make_config
from testlib import make_uuid
from testlib import permutations, expandPermutations
from testlib import VdsmTestCase as TestCaseBase
from testValidation import slowtest

CONFIG = make_config([('irs', 'volume_utilization_chunk_mb', '1024')])
GIB_IN_SECTORS = GIB // sc.BLOCK_SIZE


@expandPermutations
class BlockVolumeSizeTests(TestCaseBase):

    @permutations([
        # (preallocate, capacity in sectors, initial size in sectors),
        #   allocation size in MB
        # Preallocate, capacity 2048 sectors, No initial size.
        #      Expected 1 Mb allocated
        [(sc.PREALLOCATED_VOL, 2048, None), 1],
        # Preallocate, capacity 2049 sectors, No initial size.
        #      Expected 2 Mb allocated
        [(sc.PREALLOCATED_VOL, 2049, None), 2],
        # Preallocate, capacity 2097152 sectors, No initial size.
        #      Expected 1024 Mb allocated
        [(sc.PREALLOCATED_VOL, 2097152, None), 1024],
        # Sparse, capacity 9999 sectors, No initial size.
        #      Expected 1024 Mb allocated
        [(sc.SPARSE_VOL, 9999, None),
         config.getint("irs", "volume_utilization_chunk_mb")],
        # Sparse, capacity 8388608 sectors, initial size 1860.
        #      Expected 1 Mb allocated
        [(sc.SPARSE_VOL, 8388608, 1860), 1],
        # Sparse, capacity 8388608 sectors, initial size 1870.
        #      Expected 2 Mb allocated
        [(sc.SPARSE_VOL, 8388608, 1870), 2],
        # Sparse, capacity 2097152 sectors, initial size 2359296.
        #      Expected 1268 Mb allocated
        [(sc.SPARSE_VOL, GIB_IN_SECTORS,
          BlockVolume.max_size(GIB, sc.COW_FORMAT) // sc.BLOCK_SIZE),
         1268],
    ])
    def test_block_volume_size(self, args, result):
        size = BlockVolume.calculate_volume_alloc_size(*args)
        self.assertEqual(size, result)

    @permutations(
        # preallocate
        [[sc.PREALLOCATED_VOL],
         [sc.SPARSE_VOL],
         ])
    def test_fail_invalid_block_volume_size(self, preallocate):
        with self.assertRaises(se.InvalidParameterException):
            max_size = BlockVolume.max_size(GIB, sc.COW_FORMAT)
            max_size_blk = max_size // sc.BLOCK_SIZE
            BlockVolume.calculate_volume_alloc_size(preallocate,
                                                    GIB_IN_SECTORS,
                                                    max_size_blk + 1)


class TestBlockVolumeManifest(TestCaseBase):

    @contextmanager
    def make_volume(self, size, storage_type='block', format=sc.RAW_FORMAT):
        img_id = make_uuid()
        vol_id = make_uuid()
        # TODO fix make_volume helper to create the qcow image when needed
        with fake_env(storage_type) as env:
            if format == sc.RAW_FORMAT:
                env.make_volume(size, img_id, vol_id, vol_format=format)
                vol = env.sd_manifest.produceVolume(img_id, vol_id)
                yield vol
            else:
                chain = make_qemu_chain(env, size, format, 1)
                yield chain[0]

    def test_max_size_raw(self):
        # # verify that max size equals to virtual size.
        self.assertEqual(BlockVolume.max_size(1 * GIB, sc.RAW_FORMAT),
                         1 * GIB)

    def test_max_size_cow(self):
        # verify that max size equals to virtual size with estimated cow
        # overhead, aligned to vg extent size.
        self.assertEqual(BlockVolume.max_size(10 * GIB, sc.COW_FORMAT),
                         11811160064)

    def test_optimal_size_raw(self):
        # verify optimal size equals to virtual size.
        with self.make_volume(size=GIB) as vol:
            self.assertEqual(vol.optimal_size(), 1073741824)

    @MonkeyPatch(blockVolume, 'config', CONFIG)
    def test_optimal_size_cow_empty(self):
        # verify optimal size equals to actual size + one chunk.
        with self.make_volume(size=GIB, format=sc.COW_FORMAT) as vol:
            self.assertEqual(vol.optimal_size(), 1074003968)

    @slowtest
    @MonkeyPatch(blockVolume, 'config', CONFIG)
    def test_optimal_size_cow_not_empty(self):
        # verify that optimal size is limited to max size.
        with self.make_volume(size=GIB, format=sc.COW_FORMAT) as vol:
            qemu_pattern_write(path=vol.volumePath,
                               format=sc.fmt2str(vol.getFormat()),
                               len=200 * MEGAB)
            max_size = vol.max_size(GIB, vol.getFormat())
            self.assertEqual(vol.optimal_size(), max_size)
