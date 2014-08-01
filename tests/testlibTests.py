#
# Copyright 2014 Red Hat, Inc.
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

from testlib import AssertingLock
from testlib import VdsmTestCase


class AssertNotRaisesTests(VdsmTestCase):

    def test_contextmanager_fail(self):
        with self.assertRaises(self.failureException):
            with self.assertNotRaises():
                raise Exception("test failure")

    def test_contextmanager_pass(self):
        with self.assertNotRaises():
            pass

    def test_inline_fail(self):
        def func():
            raise Exception("test failure")
        with self.assertRaises(self.failureException):
            self.assertNotRaises(func)

    def test_inline_pass(self):
        def func():
            pass
        self.assertNotRaises(func)


class AssertingLockTests(VdsmTestCase):

    def test_free(self):
        lock = AssertingLock()
        with lock:
            pass

    def test_locked(self):
        lock = AssertingLock()
        with self.assertRaises(AssertionError):
            with lock:
                with lock:
                    pass
