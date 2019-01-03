#!/usr/bin/env python3
# pass import - Password Store Extension (https://www.passwordstore.org/)
# Copyright (C) 2017 Alexandre PUJOL <alexandre@pujol.io>.
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

import os
import re
import io
import sys
import csv
import json
import glob
import shutil
import argparse
import importlib
import configparser
from subprocess import Popen, PIPE
from collections import OrderedDict, defaultdict

__version__ = '2.4'

TMP_ATTACHMENT_DIR = "tmp_attachment_files/"

importers = {
    '1password': ['OnePassword', 'https://1password.com/'],
    '1password4': ['OnePassword4', 'https://1password.com/'],
    '1password4pif': ['OnePassword4PIF', 'https://1password.com/'],
    'bitwarden': ['Bitwarden', 'https://bitwarden.com/'],
    'chrome': ['Chrome', 'https://support.google.com/chrome'],
    'chromesqlite': ['ChromeSQLite', 'https://support.google.com/chrome'],
    'dashlane': ['Dashlane', 'https://www.dashlane.com/'],
    'enpass': ['Enpass', 'https://www.enpass.io/'],
    'fpm': ['FigaroPM', 'http://fpm.sourceforge.net/'],
    'gorilla': ['Gorilla', 'https://github.com/zdia/gorilla/wiki'],
    'kedpm': ['FigaroPM', 'http://kedpm.sourceforge.net/'],
    'keepass': ['Keepass', 'https://www.keepass.info'],
    'keepasscsv': ['KeepassCSV', 'https://www.keepass.info'],
    'keepassx': ['KeepassX', 'https://www.keepassx.org/'],
    'keepassx2': ['KeepassX2', 'https://www.keepassx.org/'],
    'keepassxc': ['KeepassXC', 'https://keepassxc.org/'],
    'lastpass': ['Lastpass', 'https://www.lastpass.com/'],
    'networkmanager': ['NetworkManager', 'https://wiki.gnome.org/Projects/NetworkManager'],
    'passwordexporter': ['PasswordExporter', 'https://github.com/kspearrin/ff-password-exporter'],
    'pwsafe': ['Pwsafe', 'https://pwsafe.org/'],
    'revelation': ['Revelation', 'https://revelation.olasagasti.info/'],
    'roboform': ['Roboform', 'https://www.roboform.com/'],
    'upm': ['UPM', 'http://upm.sourceforge.net/'],
}


class PasswordStoreError(Exception):
    """Error in the execution of password store."""


class FormatError(Exception):
    """Password importer format (XML or CSV) not recognized."""


class Msg():
    """General class to manage output messages."""
    green = '\033[32m'
    yellow = '\033[33m'
    magenta = '\033[35m'
    Bred = '\033[1m\033[91m'
    Bgreen = '\033[1m\033[92m'
    Byellow = '\033[1m\033[93m'
    Bmagenta = '\033[1m\033[95m'
    Bold = '\033[1m'
    end = '\033[0m'

    def __init__(self, verbose=False, quiet=False):
        self.verb = verbose
        self.quiet = quiet
        if self.quiet:
            self.verb = False

    def verbose(self, title='', msg=''):
        if self.verb:
            print("%s  .  %s%s%s: %s%s" % (self.Bmagenta, self.end,
                                           self.magenta, title, self.end, msg))

    def message(self, msg=''):
        if not self.quiet:
            print("%s  .  %s%s" % (self.Bold, self.end, msg))

    def echo(self, msg=''):
        if not self.quiet:
            print("       %s" % msg)

    def success(self, msg=''):
        if not self.quiet:
            print("%s (*) %s%s%s%s" % (self.Bgreen, self.end,
                                       self.green, msg, self.end))

    def warning(self, msg=''):
        if not self.quiet:
            print("%s  w  %s%s%s%s" % (self.Byellow, self.end,
                                       self.yellow, msg, self.end))

    def error(self, msg=''):
        print("%s [x] %s%sError: %s%s" % (self.Bred, self.end,
                                          self.Bold, self.end, msg))

    def die(self, msg=''):
        self.error(msg)
        exit(1)


try:
    from defusedxml import ElementTree
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    msg = Msg()
    msg.die("""defusedxml is not present, you can install it with
     'sudo apt-get install python3-defusedxml', or
     'pip3 install defusedxml'""")


class PasswordStore():
    """Simple Password Store for python, only able to insert password.
    Supports all the environment variables.
    """

    def __init__(self):
        self._passbinary = shutil.which('pass')
        self._gpgbinary = shutil.which('gpg2') or shutil.which('gpg')
        self.env = dict(**os.environ)
        self._setenv('PASSWORD_STORE_DIR')
        self._setenv('PASSWORD_STORE_KEY')
        self._setenv('PASSWORD_STORE_GIT', 'GIT_DIR')
        self._setenv('PASSWORD_STORE_GPG_OPTS')
        self._setenv('PASSWORD_STORE_X_SELECTION', 'X_SELECTION')
        self._setenv('PASSWORD_STORE_CLIP_TIME', 'CLIP_TIME')
        self._setenv('PASSWORD_STORE_UMASK')
        self._setenv('PASSWORD_STORE_GENERATED_LENGHT', 'GENERATED_LENGTH')
        self._setenv('PASSWORD_STORE_CHARACTER_SET', 'CHARACTER_SET')
        self._setenv('PASSWORD_STORE_CHARACTER_SET_NO_SYMBOLS',
                     'CHARACTER_SET_NO_SYMBOLS')
        self._setenv('PASSWORD_STORE_ENABLE_EXTENSIONS')
        self._setenv('PASSWORD_STORE_EXTENSIONS_DIR', 'EXTENSIONS')
        self._setenv('PASSWORD_STORE_SIGNING_KEY')
        self._setenv('GNUPGHOME')

        if 'PASSWORD_STORE_DIR' not in self.env:
            raise PasswordStoreError("pass prefix unknown")
        self.prefix = self.env['PASSWORD_STORE_DIR']

    def _setenv(self, var, env=None):
        """Add var in the environment variables dictionary."""
        if env is None:
            env = var
        if env in os.environ:
            self.env[var] = os.environ[env]

    def _call(self, command, data=None):
        """Call to a command."""
        process = Popen(command, universal_newlines=True, env=self.env,
                        stdin=PIPE, stdout=PIPE, stderr=PIPE)  # nosec
        (stdout, stderr) = process.communicate(data)
        res = process.wait()
        return res, stdout, stderr

    def _pass(self, arg=None, data=None):
        """Call to password store."""
        command = [self._passbinary]
        if arg is not None:
            command.extend(arg)
        res, stdout, stderr = self._call(command, data)
        if res:
            raise PasswordStoreError("%s %s" % (stderr, stdout))
        return stdout

    def insert(self, path, data, force=False):
        """Multiline insertion into the password store."""
        if not force:
            if os.path.isfile(os.path.join(self.prefix, path + '.gpg')):
                raise PasswordStoreError(
                    "An entry already exists for %s." % path)
        arg = ['insert', '--multiline']
        arg.append(path)
        return self._pass(arg, data)

    def insert_binary(self, path, data, force=False):
        binary_list = [i for i in data.split("\n") if "binary" in i]
        new_path_list = []
        if binary_list:
            file_attachment_path = TMP_ATTACHMENT_DIR + path.split("/")[-1]
            for binary in binary_list:
                filename = binary.split(": ")[-1]
                new_path = path + "_attach/" + filename
                if not force:
                    if os.path.isfile(os.path.join(self.prefix, new_path + '.gpg')):
                        raise PasswordStoreError(
                            "An entry already exists for %s." % (new_path + '.gpg'))
                with open(file_attachment_path + "/" + filename, encoding="utf-8") as binaryfile:
                    data = binaryfile.read()
                arg = ['insert', '--multiline']
                arg.append(new_path)
                self._pass(arg, data)
                new_path_list.append(new_path)
            return new_path_list

    def exist(self):
        """Return True if the password store is initialized."""
        return os.path.isfile(os.path.join(self.prefix, '.gpg-id'))

    def is_valid_recipients(self):
        """Ensure the GPG keyring is usable."""
        with open(os.path.join(self.prefix, '.gpg-id'), 'r') as file:
            gpgids = file.read().split('\n')
            gpgids.pop()

        # All the public gpgids must be present in the keyring.
        cmd = [self._gpgbinary, '--list-keys']
        for gpgid in gpgids:
            res, _, _ = self._call(cmd + [gpgid])
            if res:
                return False

        # At least one private key must be present in the keyring.
        cmd = [self._gpgbinary, '--list-secret-keys']
        for gpgid in gpgids:
            res, _, _ = self._call(cmd + [gpgid])
            if res == 0:
                return True
        return False


class PasswordManager():
    """Common structure and methods for all password manager supported.

    Please read CONTRIBUTING.md for more details regarding data structure
    in pass-import.
    """
    keyslist = ['title', 'password', 'login',
                'url', 'comments', 'group', 'binary']

    def __init__(self, extra=False, separator='-'):
        self.data = []
        self.all = extra
        self.separator = str(separator)
        self.cleans = {" ": "_", "&": "and",
                       "@": "At", "'": "", "[": "", "]": "", "/": "-"}
        self.protocols = ['http://', 'https://']
        self.invalids = ['<', '>', ':', '"', '/', '\\', '|', '?', '*', '\0']

    @staticmethod
    def get(entry):
        """Return the content of an entry in a password-store format."""
        string = entry.pop('password', '') + '\n'
        for key, value in entry.items():
            if key == 'path':
                continue
            string += "%s: %s\n" % (key, value)
        return string

    @staticmethod
    def _replaces(caracters, string):
        """Global replace method."""
        for key in caracters:
            string = string.replace(key, caracters[key])
        return string

    def _clean_protocol(self, string):
        """Remove the protocol prefix in a string."""
        caracters = dict(zip(self.protocols, ['']*len(self.protocols)))
        return self._replaces(caracters, string)

    def _clean_group(self, string):
        """Remove invalids caracters in a group. Convert separator to os.sep."""
        caracters = dict(
            zip(self.invalids, [self.separator]*len(self.invalids)))
        caracters['/'] = os.sep
        caracters['\\'] = os.sep
        return self._replaces(caracters, string)

    def _convert(self, string):
        """Convert invalid caracters by the separator in a string."""
        caracters = dict(
            zip(self.invalids, [self.separator]*len(self.invalids)))
        return self._replaces(caracters, string)

    def _clean_cmdline(self, string):
        """Make the string more command line friendly."""
        return self._replaces(self.cleans, string.strip())

    def _duplicate_paths(self, clean, convert):
        """Create subfolders for duplicated paths."""
        duplicated = defaultdict(list)
        for idx, entry in enumerate(self.data):
            path = entry.get('path', '')
            duplicated[path].append(idx)

        for path in duplicated:
            if len(duplicated[path]) > 1:
                for idx in duplicated[path]:
                    entry = self.data[idx]
                    entry['path'] = self._create_path(
                        entry, path, clean, convert)

    def _duplicate_numerise(self):
        """Add number to the remaining duplicated path."""
        seen = []
        for entry in self.data:
            path = entry.get('path', '')
            if path in seen:
                ii = 1
                while path in seen:
                    if re.search('%s(\d+)$' % self.separator, path) is None:
                        path += self.separator + str(ii)
                    else:
                        path = path.replace(self.separator + str(ii),
                                            self.separator + str(ii + 1))
                        ii += 1
                seen.append(path)
                entry['path'] = path
            else:
                seen.append(path)

    def _create_path(self, entry, path, clean, convert):
        """Create path from title and group."""
        title = ''
        for key in ['title', 'login', 'url']:
            if key in entry:
                title = self._clean_protocol(entry[key])
                if clean:
                    title = self._clean_cmdline(title)
                if convert:
                    title = self._convert(title)
                path = os.path.join(path, title)
                break

        if title == '':
            path = os.path.join(path, 'notitle')
        entry.pop('title', '')
        return path

    def clean(self, clean, convert):
        """Clean parsed data in order to be imported to a store."""
        for entry in self.data:
            # Remove unused keys
            empty = [k for k, v in entry.items() if not v]
            for key in empty:
                entry.pop(key)

            path = self._clean_group(
                self._clean_protocol(entry.pop('group', '')))
            entry['path'] = self._create_path(entry, path, clean, convert)

        self._duplicate_paths(clean, convert)
        self._duplicate_numerise()


class PasswordManagerCSV(PasswordManager):
    fieldnames = None

    def _checkline(self, file):
        line = file.readline()
        if not line.startswith(self.format):
            raise FormatError()

    def _checkformat(self, fieldnames):
        for csvkey in self.keys.values():
            if csvkey not in fieldnames:
                raise FormatError()

    def parse(self, file, password=None):
        reader = csv.DictReader(file, fieldnames=self.fieldnames,
                                delimiter=',', quotechar='"')
        self._checkformat(reader.fieldnames)

        for row in reader:
            entry = OrderedDict()
            for key in self.keyslist:
                entry[key] = row.pop(self.keys.get(key, ''), None)

            if self.all:
                for col in row:
                    entry[col] = row.get(col, None)

            self.data.append(entry)


class PasswordManagerXML(PasswordManager):

    def _checkformat(self, tree):
        if tree.tag != self.format:
            raise FormatError()

    @classmethod
    def _getroot(cls, tree):
        return tree

    @classmethod
    def _getvalue(cls, elements, xmlkey):
        value = elements.find(xmlkey)
        return '' if value is None else value.text

    def _getentry(self, element):
        entry = OrderedDict()
        for key in self.keyslist:
            xmlkey = self.keys.get(key, '')
            if xmlkey != '':
                entry[key] = self._getvalue(element, xmlkey)
        for binary in element.iterfind('Binary'):
            binary_element = binary.getchildren()
            attachment_name = binary_element[0].text
            binary_ref = binary_element[1].attrib.get('Ref')
            entry['binary-' + binary_ref] = attachment_name
        return entry

    def _getbinary(self, element):
        for binary in element.iterfind('Binary'):
            binary_element = binary.getchildren()
            attachment_name = binary_element[0].text
            # binary_ref = binary_element[1].attrib.get('Ref')
            self.entry['binary'] = attachment_name
        return entry

    def parse(self, file, password=None):
        tree = ElementTree.XML(file.read())
        self._checkformat(tree)
        root = self._getroot(tree)
        self._import(root)


class PasswordManagerPIF(PasswordManager):
    ignore = ['keyID', 'typeName', 'uuid',
              'openContents', 'folderUuid', 'URLs']

    @staticmethod
    def _pif2json(file):
        """Convert 1pif to json see https://github.com/eblin/1passpwnedcheck."""
        data = file.read()
        cleaned = re.sub('(?m)^\*\*\*.*\*\*\*\s+', '', data)
        cleaned = cleaned.split('\n')
        cleaned = ','.join(cleaned).rstrip(',')
        cleaned = '[%s]' % cleaned
        return json.loads(cleaned)

    @staticmethod
    def _getvalue(jsonkey, item, scontent, fields):
        value = item.pop(jsonkey, None)
        value = scontent.pop(jsonkey, value)
        if value is None:
            for field in fields:
                if field.get('name', '') == jsonkey:
                    value = field.get('value', None)
                    index = fields.index(field)
                    fields.pop(index)
                    break
        return value

    def _sortgroup(self, folders):
        for folder in folders.values():
            parent = folder.get('parent', '')
            groupup = folders.get(parent, {}).get('group', '')
            folder['group'] = os.path.join(groupup, folder.get('group', ''))

        for entry in self.data:
            groupid = entry.get('group', '')
            entry['group'] = folders.get(groupid, {}).get('group', '')

    def parse(self, file, password=None):
        jsons = self._pif2json(file)
        folders = dict()
        for item in jsons:
            if item.get('typeName', '') == 'system.folder.Regular':
                key = item.get('uuid', '')
                folders[key] = {'group': item.get('title', ''),
                                'parent': item.get('folderUuid', '')}

            elif item.get('typeName', '') == 'webforms.WebForm':
                entry = OrderedDict()
                scontent = item.pop('secureContents', {})
                fields = scontent.pop('fields', [])
                for key in self.keyslist:
                    jsonkey = self.keys.get(key, '')
                    entry[key] = self._getvalue(
                        jsonkey, item, scontent, fields)

                if self.all:
                    for field in fields:
                        entry[field.get('name', '')] = field.get('value', '')
                    item.update(scontent)
                    for key, value in item.items():
                        if key not in self.ignore:
                            entry[key] = value

                self.data.append(entry)
        self._sortgroup(folders)


class OnePassword4PIF(PasswordManagerPIF):
    keys = {'title': 'title', 'password': 'password', 'login': 'username',
            'url': 'location', 'comments': 'notesPlain', 'group': 'folderUuid'}


class OnePassword4(PasswordManagerCSV):
    keys = {'title': 'title', 'password': 'password', 'login': 'username',
            'url': 'url', 'comments': 'notes'}


class OnePassword(PasswordManagerCSV):
    keys = {'title': 'Title', 'password': 'Password', 'login': 'Username',
            'url': 'URL', 'comments': 'Notes', 'group': 'Type'}


class Bitwarden(PasswordManagerCSV):
    keys = {'title': 'name', 'password': 'login_password', 'login': 'login_username',
            'url': 'login_uri', 'comments': 'notes', 'group': 'folder'}


class Chrome(PasswordManagerCSV):
    keys = {'title': 'name', 'password': 'password', 'login': 'username',
            'url': 'url'}


class ChromeSQLite(PasswordManagerCSV):
    keys = {'title': 'display_name', 'password': 'password_value',
            'login': 'username_value', 'url': 'origin_url'}


class Dashlane(PasswordManagerCSV):
    fieldnames = ['title', 'url', 'login', 'password', 'comments']
    keys = {'title': 'title', 'password': 'password', 'login': 'login',
            'url': 'url', 'comments': 'comments'}


class Enpass(PasswordManagerCSV):
    format = '"Title","Field","Value","Field","Value",.........,"Note"'
    keys = {'title': 'Title', 'password': 'Password', 'login': 'Username',
            'url': 'URL', 'comments': 'notes', 'group': 'group'}

    def parse(self, file, password=None):
        self._checkline(file)
        reader = csv.reader(file)
        for row in reader:
            entry = OrderedDict()
            entry['title'] = row.pop(0)
            comments = row.pop()
            for key in self.keyslist:
                csvkey = self.keys.get(key, '')
                if csvkey in row:
                    index = row.index(csvkey)
                    entry[key] = row.pop(index+1)
                    row.pop(index)
            entry['comments'] = comments

            if self.all:
                index = 0
                while index+2 <= len(row):
                    entry[row[index]] = row[index+1]
                    index += 2

            self.data.append(entry)


class FigaroPM(PasswordManagerXML):
    format = 'FPM'
    keys = {'title': 'title', 'password': 'password', 'login': 'user',
            'url': 'url', 'comments': 'notes', 'group': 'category'}

    @classmethod
    def _getroot(cls, tree):
        return tree.find('PasswordList')

    def _import(self, element):
        for xmlentry in element.findall('PasswordItem'):
            entry = self._getentry(xmlentry)
            self.data.append(entry)


class Gorilla(PasswordManagerCSV):
    keys = {'title': 'title', 'password': 'password', 'login': 'user',
            'url': 'url', 'comments': 'notes', 'group': 'group'}

    def parse(self, file, password=None):
        super(Gorilla, self).parse(file)
        for entry in self.data:
            entry['group'] = re.sub('(?<=[^\\\])\.', os.sep, entry['group'])
            entry['group'] = re.sub('\\\.', '.', entry['group'])


class KeepassX(PasswordManagerXML):
    group = 'group'
    entry = 'entry'
    format = 'database'
    keys = {'title': 'title', 'password': 'password', 'login': 'username',
            'url': 'url', 'comments': 'comment'}

    @classmethod
    def _getpath(cls, element, path=''):
        res = ''
        if element.tag != 'database':
            if element.find('title').text:
                res = os.path.join(path, element.find('title').text)
            else:
                res = os.path.join(path, 'untitled')
        return res

    def _import(self, element, path=''):
        path = self._getpath(element, path)
        for group in element.findall(self.group):
            self._import(group, path)

        for xmlentry in element.findall(self.entry):
            entry = self._getentry(xmlentry)
            entry['title'] = self._getpath(xmlentry)
            entry['group'] = path
            self.data.append(entry)


class Keepass(KeepassX):
    group = 'Group'
    entry = 'Entry'
    format = 'KeePassFile'
    keys = {'title': 'Title', 'password': 'Password', 'login': 'UserName',
            'url': 'URL', 'comments': 'Notes', 'binary': 'Binary'}

    @classmethod
    def _getroot(cls, tree):
        root = tree.find('Root')
        return root.find('Group')

    @classmethod
    def _getvalue(cls, elements, xmlkey):
        value = ''
        for element in elements:
            for child in element.findall('Key'):
                if child.text == xmlkey:
                    value = element.find('Value').text
                    break
        return value

    @classmethod
    def _getpath(cls, element, path=''):
        """Generate path name from elements title and current path."""
        title = ''
        if element.tag == 'Entry':
            title = cls._getvalue(element.findall('String'), 'Title')
        elif element.tag == 'Group':
            title = element.find('Name').text
        if title is None:
            title = ''
        return os.path.join(path, title)


    def write_attach(self, bin_elem, name, path):
        import gzip
        from base64 import b64decode
        if bin_elem.attrib['Compressed'] == 'True':
            data = gzip.decompress(b64decode(bin_elem.text))
        else:
            data = b64decode(bin_elem.text)
        filepath = os.path.join(path, name)
        msg = Msg()
        with open(filepath, 'wb') as f:
            f.write(bytearray(data))
            msg.echo('File ' + filepath + ' written')


    # def find_attachment_entry_former(self, entry):
        # root = ET.fromstring(entry.dump_xml().decode())
        # for binary in root.iter('Binary'):
        #     binary_element = binary.getchildren()
        #     attachment_name = binary_element[0].text
        #     binary_ref = binary_element[1].attrib.get('Ref')
        #     bin_elem = kp._xpath(
        #         '/KeePassFile/Meta/Binaries/Binary[@ID=' + binary_ref + ']')[0]

        #     # cleans = {"&": "and", "@": "At", "'": "", 
        #     #  "[": "", "]": "", "#": "", "/": "-", " ": "_"}
        #     path = TMP_ATTACHMENT_DIR + self._replaces(self.cleans, entry.title)
        #     if not os.path.exists(path):
        #         os.makedirs( path)
        #     self.write_attach(bin_elem, attachment_name, path)


    def find_attachment_entry(self, entry, keepassobj):
        # import xml.etree.ElementTree as ET
        # root = ET.fromstring(entry.dump_xml().decode())
        root = ElementTree.XML(entry.dump_xml().decode())

        for binary in root:
            if binary.tag == 'Binary':
                attachment_name = None
                binary_ref = None
                for binary_element in binary.iter('Binary'):

                    attachment_name = binary_element[0].text
                    binary_ref = binary_element[1].attrib.get('Ref')

                bin_elem = keepassobj._xpath(
                    '/KeePassFile/Meta/Binaries/Binary[@ID=' + binary_ref + ']')[0]

                path = TMP_ATTACHMENT_DIR + self._replaces(self.cleans, entry.title)
                if not os.path.exists(path):
                    os.makedirs(path)
                self.write_attach(bin_elem, attachment_name, path)


    def parse(self, file, password=None):
        super(Keepass, self).parse(file)
        if password:
            from pykeepass import PyKeePass

            file.seek(0)

            keepassfile = file.name.split(".")[0] + ".kdbx"

            # load database
            kp = PyKeePass(keepassfile, password)

            entries = kp.find_entries(title='.*', regex=True)

            msg = Msg()

            msg.message("Attachments extraction started")
            for entry in entries:
                try:
                    self.find_attachment_entry(entry, kp)
                except:
                    msg.warning("Problem extracting attachmemnt {entry} with error\n", sys.exc_info()[0])
            msg.message("ADD - Cleanup attachment files")
            msg.echo("Attachments extraction ended")


class KeepassCSV(PasswordManagerCSV):
    keys = {'title': 'Account', 'password': 'Password', 'login': 'Login Name',
            'url': 'Web Site', 'comments': 'Comments'}


class KeepassX2(PasswordManagerCSV):
    keys = {'title': 'Title', 'password': 'Password', 'login': 'Username',
            'url': 'URL', 'comments': 'Notes', 'group': 'Group'}


class KeepassXC(KeepassX2):
    pass


class Lastpass(PasswordManagerCSV):
    keys = {'title': 'name', 'password': 'password', 'login': 'username',
            'url': 'url', 'comments': 'extra', 'group': 'grouping'}


class NetworkManager(PasswordManager):
    etc = '/etc/NetworkManager/system-connections'
    keyslist = ['title', 'password', 'login', 'ssid']
    keys = {'title': 'connection.id', 'password': 'wifi-security.psk',
            'login': '802-1x.identity', 'ssid': 'wifi.ssid'}

    def parse(self, data, password=None):
        if isinstance(data, io.IOBase):
            files = [data]
        else:
            data = self.etc if data is None else data
            files = [open(path, 'r') for path in glob.glob(data + '/*')]

        for file in files:
            ini = configparser.ConfigParser()
            ini.read_file(file)
            self.keys['password'] = '802-1x.password' if '802-1x' in ini else 'wifi-security.psk'
            entry = OrderedDict()
            for key in self.keyslist:
                sect, option = self.keys.get(key, '.').split('.')
                entry[key] = ini.get(sect, option, fallback=None)

            if self.all:
                for section in ini.sections():
                    for option in ini.options(section):
                        entry[option] = ini.get(section, option, fallback=None)

            if entry.get('password', None) is not None:
                self.data.append(entry)

            file.close()


class PasswordExporter(PasswordManagerCSV):
    keys = {'title': 'hostname', 'password': 'password', 'login': 'username'}


class Pwsafe(PasswordManagerXML):
    format = 'passwordsafe'
    keyslist = ['title', 'password', 'login',
                'url', 'email', 'comments', 'group']
    keys = {'title': 'title', 'password': 'password', 'login': 'username',
            'url': 'url', 'email': 'email', 'comments': 'notes', 'group': 'group'}

    def _import(self, element):
        delimiter = element.attrib['delimiter']
        for xmlentry in element.findall('entry'):
            entry = self._getentry(xmlentry)
            entry['group'] = entry.get('group', '').replace('.', os.sep)
            entry['comments'] = entry.get(
                'comments', '').replace(delimiter, '\n')
            if self.all:
                for historyentry in xmlentry.findall('./pwhistory/history_entries/history_entry'):
                    key = 'oldpassword' + historyentry.attrib['num']
                    time = self._getvalue(historyentry, 'changedx')
                    oldpassword = self._getvalue(historyentry, 'oldpassword')
                    entry[key] = time + ' ' + oldpassword
            self.data.append(entry)


class Revelation(PasswordManagerXML):
    format = 'revelationdata'
    keys = {'title': 'name', 'password': 'generic-password',
            'login': 'generic-username', 'url': 'generic-hostname',
            'comments': 'notes', 'group': '', 'description': 'description'}

    @classmethod
    def _getvalue(cls, elements, xmlkey):
        fieldkeys = ['generic-hostname',
                     'generic-username', 'generic-password']
        if xmlkey in fieldkeys:
            for field in elements.findall('field'):
                if xmlkey == field.attrib['id']:
                    return field.text
        else:
            return elements.find(xmlkey).text
        return ''

    def _import(self, element, path=''):
        for xmlentry in element.findall('entry'):
            if xmlentry.attrib.get('type', '') == 'folder':
                _path = os.path.join(path, xmlentry.find('name').text)
                self._import(xmlentry, _path)
            else:
                entry = self._getentry(xmlentry)
                entry['group'] = path
                self.data.append(entry)


class Roboform(PasswordManagerCSV):
    keys = {'title': 'Name', 'password': 'Pwd', 'login': 'Login', 'url': 'Url',
            'comments': 'Note', 'group': 'Folder'}


class UPM(PasswordManagerCSV):
    fieldnames = ['title', 'login', 'password', 'url', 'comments']
    keys = {'title': 'title', 'password': 'password', 'login': 'login',
            'url': 'url', 'comments': 'comments'}


def argumentsparse(argv):
    """Geting arguments for 'pass import'."""
    parser = argparse.ArgumentParser(prog='pass import', description="""
  Import data from most of the password manager. Passwords
  are imported in the existing default password store, therefore
  the password store must have been initialised before with 'pass init'""",
                                     usage="%(prog)s [-h] [-V] [[-p PATH] [-c] [-C] [-s] [-e] [-b              KeePassFile password][-f] | -l] [manager] [file]",
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="More information may be found in the pass-import(1)              man page.")

    parser.add_argument('manager', type=str, nargs='?',
                        help="Can be: %s"
                        % ', '.join(list(importers.keys())) + '.')
    parser.add_argument('file', type=str, nargs='?',
                        help="""File is the path to the file that contains the
                        data to import, if empty read the data from stdin.""")

    parser.add_argument('-p', '--path', action='store', dest='root',
                        default='', metavar='PATH',
                        help='Import the passwords to a specific subfolder.')
    parser.add_argument('-e', '--extra', action='store_true',
                        help='Also import all the extra data present.')
    parser.add_argument('-b', '--binaries', type=str, metavar='KEEPASS_PW',
                        help='Also import all the binary attachments. \
                        Specify the password to open the KeePassFile')
    parser.add_argument('-c', '--clean', action='store_true',
                        help='Make the paths more command line friendly.')
    parser.add_argument('-C', '--convert', action='store_true',
                        help='Convert the invalid caracters present in the paths.')
    parser.add_argument('-s', '--separator', action='store', dest='separator',
                        metavar='CAR',
                        help="""Provide a caracter of replacement for the path
                         separator. Default: '-' """)
    parser.add_argument('-l', '--list', action='store_true',
                        help='List the supported password managers.')
    parser.add_argument('-f', '--force', action='store_true',
                        help='Overwrite existing path.')
    parser.add_argument('-q', '--quiet', action='store_true', help='Be quiet.')
    parser.add_argument('-v', '--verbose',
                        action='store_true', help='Be verbose.')
    parser.add_argument('-V', '--version', action='version',
                        version='%(prog)s ' + __version__,
                        help='Show the program version and exit.')

    return parser.parse_args(argv)


def listimporters(msg):
    """List supported password managers."""
    msg.success("The %s supported password managers are:" % len(importers))
    for name, value in importers.items():
        msg.message("%s%s%s - %s" % (msg.Bold, name, msg.end, value[1]))
    if msg.quiet:
        for name in importers:
            print(name)


def sanitychecks(arg, msg):
    """Sanity checks."""
    if arg.manager is None:
        msg.die("password manager not present. See 'pass import -h'")
    if arg.manager not in importers:
        msg.die("%s is not a supported password manager" % arg.manager)
    if arg.manager == 'networkmanager' and (arg.file is None or os.path.isdir(arg.file)):
        file = arg.file
    elif arg.file is None:
        file = sys.stdin
    elif os.path.isfile(arg.file):
        encoding = 'utf-8-sig' if arg.manager == '1password4pif' else 'utf-8'
        file = open(arg.file, 'r', encoding=encoding)
    else:
        msg.die("%s is not a file" % arg.file)

    if arg.separator is None:
        configpath = os.path.join(os.environ.get('PASSWORD_STORE_DIR', ''),
                                  arg.root, '.import')
        if os.path.isfile(configpath):
            with open(configpath, 'r') as configfile:
                ini = configparser.ConfigParser()
                ini.read_file(configfile)
                arg.separator = ini.get('convert', 'separator', fallback='-')
        else:
            arg.separator = '-'

    return file


def report(arg, msg, paths, binaries=None, error_binaries=None):
    """Print final success report."""
    msg.success("Importing passwords from %s" % arg.manager)
    if arg.file is None:
        arg.file = 'read from stdin'
    msg.message("File: %s" % arg.file)
    if arg.root != '':
        msg.message("Root path: %s" % arg.root)
    msg.message("Number of password imported: %s" % len(paths))
    if arg.convert:
        msg.message("Forbidden chars converted")
        msg.message("Path separator used: %s" % arg.separator)
    if arg.clean:
        msg.message("Imported data cleaned")
    if arg.extra:
        msg.message("Extra data conserved")
    if paths:
        msg.message("Passwords imported:")
        paths.sort()
        for path in paths:
            msg.echo(os.path.join(arg.root, path))
    if binaries:
        msg.message("Number of attachments imported: %s" % len(binaries))
        msg.message("Binaries imported:")
        for binary in binaries:
            msg.echo(binary)
        msg.message("Number of attachments not imported: %s" % len(error_binaries))
        msg.message("Binaries Not imported:")
        for binary in error_binaries:
            msg.echo(binary)



def main(argv):
    arg = argumentsparse(argv)
    msg = Msg(arg.verbose, arg.quiet)

    if arg.list:
        listimporters(msg)
    else:
        file = sanitychecks(arg, msg)

        # Import and clean data
        ImporterClass = getattr(importlib.import_module(__name__),
                                importers[arg.manager][0])
        importer = ImporterClass(arg.extra, arg.separator)
        try:
            importer.parse(file, arg.binaries)
            importer.clean(arg.clean, arg.convert)
        except (FormatError, AttributeError, ValueError):
            msg.die("%s is not a exported %s file" % (arg.file, arg.manager))
        except PermissionError as e:
            msg.die(e)
        finally:
            if arg.manager != 'networkmanager':
                file.close()

        # Insert data into the password store
        paths = []
        binaries = []
        error_binaries = []
        store = PasswordStore()
        if not store.exist():
            msg.die("password store not initialized")
        if not store.is_valid_recipients():
            msg.die('invalid user ID, password encryption aborted.')
        for entry in importer.data:
            try:
                passpath = os.path.join(arg.root, entry['path'])
                data = importer.get(entry)
                msg.verbose("Path", passpath)
                msg.verbose("Data", data.replace('\n', '\n           '))
                store.insert(passpath, data, arg.force)
                if arg.binaries:
                    try:
                        added_path = store.insert_binary(passpath, data, arg.force)
                        if added_path:
                            binaries = binaries + added_path
                    except:
                        error_binaries.append(passpath)
            except PasswordStoreError as e:
                msg.warning("Impossible to insert %s into the store: %s"
                            % (passpath, e))
            else:
                paths.append(entry['path'])

        # Success!
        report(arg, msg, paths, binaries, error_binaries)


if __name__ == "__main__":
    sys.argv.pop(0)
    main(sys.argv)
