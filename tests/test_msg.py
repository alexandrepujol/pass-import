#!/usr/bin/env python3
# pass import - Password Store Extension (https://www.passwordstore.org/)
# Copyright (C) 2017-2019 Alexandre PUJOL <alexandre@pujol.io>.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import pass_import
import tests


class TestConfig(tests.Test):
    """Test the Config class."""

    def setUp(self):
        """Initialse a config object."""
        self.conf = pass_import.Config(0, False)

    def test_readconfig(self):
        """Testing: read configuration file."""
        args = {'separator': '6', 'config': tests.assets + 'config.yml'}
        conf = pass_import.Config()
        conf.readconfig(args)

        ref = {
            'separator': '6',
            'delimiter': ',',
            'cleans': {' ': '6'},
            'protocols': [],
            'invalids': ['<', '>', ':', '"', '/', '\\', '|', '?', '*', '\x00'],
            'config': tests.assets + 'config.yml'
        }
        self.assertEqual(conf, ref)

    def test_showentry(self):
        """Testing: show a password entry."""
        conf = pass_import.Config(2, False)
        entry = {
            'path': 'Social/mastodon.social',
            'password': 'EaP:bCmLZliqa|]WR/#HZP',
            'login': 'roddhjav',
            'group': 'Social'
        }
        ref = ('\x1b[1m\x1b[95m  .  \x1b[0m\x1b[35mPath: \x1b[0mSocial/mastodo'
               'n.social\n\x1b[1m\x1b[95m  .  \x1b[0m\x1b[35mData: \x1b[0mEaP:'
               'bCmLZliqa|]WR/#HZP\n           login: roddhjav')
        with tests.captured() as (out, err):
            conf.show(entry)
            message = out.getvalue().strip()
        self.assertEqual(err.getvalue().strip(), '')
        self.assertEqual(message, ref)

    def test_debug(self):
        """Testing: debug message."""
        conf = pass_import.Config(3, False)
        with tests.captured() as (out, err):
            conf.debug('pass', 'debug message')
            message = out.getvalue().strip()
        self.assertEqual(err.getvalue().strip(), '')
        self.assertEqual(message, ('\x1b[1m\x1b[95m  .  \x1b[0m\x1b[35m'
                                   'pass: \x1b[0mdebug message'))

    def test_verbose_simple(self):
        """Testing: message verbose simple."""
        with tests.captured() as (out, err):
            self.conf.verbose('pass', 'verbose message')
            message = out.getvalue().strip()
        self.assertEqual(err.getvalue().strip(), '')
        self.assertEqual(message, '')

    def test_verbose(self):
        """Testing: message verbose."""
        conf = pass_import.Config(1, False)
        with tests.captured() as (out, err):
            conf.verbose('pass', 'verbose msg')
            message = out.getvalue().strip()
        self.assertEqual(err.getvalue().strip(), '')
        self.assertEqual(message, ('\x1b[1m\x1b[95m  .  \x1b[0m\x1b[35m'
                                   'pass: \x1b[0mverbose msg'))

        with tests.captured() as (out, err):
            conf.verbose('pass')
            message = out.getvalue().strip()
        self.assertEqual(err.getvalue().strip(), '')
        self.assertEqual(message, ('\x1b[1m\x1b[95m  .  \x1b[0m\x1b[35mpass'
                                   '\x1b[0m'))

    def test_message(self):
        """Testing: classic message message."""
        with tests.captured() as (out, err):
            self.conf.message('classic message')
            message = out.getvalue().strip()
        self.assertEqual(err.getvalue().strip(), '')
        self.assertEqual(message, '\x1b[1m  .  \x1b[0mclassic message')

        conf = pass_import.Config(True, True)
        with tests.captured() as (out, err):
            conf.message('classic message')
            message = out.getvalue().strip()
        self.assertEqual(err.getvalue().strip(), '')
        self.assertEqual(message, '')

    def test_echo(self):
        """Testing: small echo."""
        with tests.captured() as (out, err):
            self.conf.echo('smal echo')
            message = out.getvalue().strip()
        self.assertEqual(err.getvalue().strip(), '')
        self.assertEqual(message, 'smal echo')

    def test_success(self):
        """Testing: success message."""
        with tests.captured() as (out, err):
            self.conf.success('success message')
            message = out.getvalue().strip()
        self.assertEqual(err.getvalue().strip(), '')
        self.assertEqual(message, ('\x1b[1m\x1b[92m (*) \x1b[0m\x1b[32m'
                                   'success message\x1b[0m'))

    def test_warning(self):
        """Testing: warning message."""
        with tests.captured() as (out, err):
            self.conf.warning('warning message')
            message = out.getvalue().strip()
        self.assertEqual(err.getvalue().strip(), '')
        self.assertEqual(message, ('\x1b[1m\x1b[93m  w  \x1b[0m\x1b[33m'
                                   'warning message\x1b[0m'))

    def test_error(self):
        """Testing: error message."""
        with tests.captured() as (out, err):
            self.conf.error('error message')
            message = err.getvalue().strip()
        self.assertEqual(out.getvalue().strip(), '')
        self.assertEqual(message, ('\x1b[1m\x1b[91m [x] \x1b[0m\x1b[1m'
                                   'Error: \x1b[0merror message'))

    def test_die(self):
        """Testing: die message."""
        with tests.captured() as (out, err):
            with self.assertRaises(SystemExit) as cm:
                self.conf.die('critical error')
            message = err.getvalue().strip()
            self.assertEqual(cm.exception.code, 1)
        self.assertEqual(out.getvalue().strip(), '')
        self.assertEqual(message, ('\x1b[1m\x1b[91m [x] \x1b[0m\x1b[1m'
                                   'Error: \x1b[0mcritical error'))
