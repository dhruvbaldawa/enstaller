# Copyright by Enthought, Inc.
# Author: Ilan Schnell <ischnell@enthought.com>

import re
import os
import sys
import platform
from os.path import isfile, join

from enstaller import __version__
from utils import PY_VER, abs_expanduser, fill_url


try:
    import keyring
    import keyring.backend
    # don't use keyring backends that require console input or just do
    # more or less the same thing we're already doing
    keyring.backend._all_keyring = [keyring.backend.OSXKeychain(),
                                    keyring.backend.GnomeKeyring(),
                                    keyring.backend.KDEKWallet(),
                                    keyring.backend.Win32CryptoKeyring(),
                                    keyring.backend.Win32CryptoRegistry(),
                                    keyring.backend.WinVaultKeyring()]
    keyring.core.init_backend()
    if keyring.get_keyring().supported() < 0:
        keyring = None
except (ImportError, KeyError):
    # the KeyError happens on Windows when the environment variable
    # 'USERPROFILE' is not set
    keyring = None

KEYRING_SERVICE_NAME = 'Enthought.com'

config_fn = ".enstaller4rc"
home_config_path = abs_expanduser("~/" + config_fn)
system_config_path = join(sys.prefix, config_fn)
webservice_base_url = 'https://api.enthought.com/eggs'
repo_base_url = 'http://www.enthought.com/eggs'

default = dict(
    prefix=sys.prefix,
    proxy=None,
    noapp=False,
    local=join(sys.prefix, 'LOCAL-REPO'),
    EPD_auth=None,
    EPD_userpass=None,
    use_webservice=True,
    autoupdate = True,
    IndexedRepos=[],
)


def get_path():
    """
    Return the absolute path to the config file.
    """
    if isfile(home_config_path):
        return home_config_path
    if isfile(system_config_path):
        return system_config_path
    return None


def input_auth():
    """
    Prompt user for username and password.  Return (username, password)
    tuple or (None, None) if left blank.
    """
    from getpass import getpass
    print """\
Please enter the email address (or username) and password for your
EPD or EPD Free subscription.  If you are not subscribed to EPD,
just press Enter.
"""
    username = raw_input('Email (or username): ').strip()
    if not username:
        return None, None
    return username, getpass('Password: ')


RC_TMPL = """\
# enstaller configuration file
# ============================
#
# This file contains the default package repositories and configuration
# used by enstaller %(version)s for the Python %(py_ver)s environment:
#
#   sys.prefix = %(sys_prefix)r
#
# This file was initially created by running the enpkg command.

%(auth_section)s

# `use_webservice` refers to using '%(webservice_base_url)s/'.
# The default is True; that is, the webservice URL is used for fetching
# eggs.  Uncommenting changes this behavior to using the explicit
# IndexedRepos listed below.
#use_webservice = False

# The enpkg command searches for eggs in the list `IndexedRepos` defined
# below.  When enpkg searches for an egg, it tries each repository in
# this list in order and selects the first one that matches, ignoring
# remaining repositories.  Therefore, the order of this list matters.
#
# For local repositories, the index file is optional.  Remember that on
# Windows systems backslashes in a directory path need to escaped, e.g.:
# r'file://C:\\repository\\' or 'file://C:\\\\repository\\\\'
IndexedRepos = [
#  '%(repo_base_url)s/ets/eggs/{SUBDIR}/',
  '%(repo_base_url)s/epd/GPL-eggs/{SUBDIR}/',
  '%(repo_base_url)s/epd/eggs/{SUBDIR}/',
# The Enthought PyPI build mirror:
  '%(repo_base_url)s/pypi/eggs/{SUBDIR}/',
]

# Install prefix (enpkg --prefix and --sys-prefix options overwrite
# this).  When this variable is not provided, it will default to the
# value of sys.prefix (within the current interpreter running enpkg).
#prefix = %(sys_prefix)r

# When running enpkg behind a firewall it might be necessary to use a
# proxy to access the repositories.  The URL for the proxy can be set
# here.  Note that the enpkg --proxy option will overwrite this setting.
%(proxy_line)s

# Uncomment the next line to disable application menu-item installation.
# This only affects the few packages that install menu items, such as
# IPython.
#noapp = True

# Uncomment the next line to turn off automatic prompts to update
# enstaller.
#autoupdate = False
"""


def write(username=None, password=None, proxy=None):
    """
    Write the config file.
    """
    # If user is 'root', then always create the config file in sys.prefix,
    # otherwise in the user's HOME directory.
    if sys.platform != 'win32' and os.getuid() == 0:
        path = system_config_path
    else:
        path = home_config_path

    if username is None and password is None:
        username, password = input_auth()
    if username and password:
        if keyring:
            keyring.set_password(KEYRING_SERVICE_NAME, username, password)
            authline = 'EPD_username = %r' % username
        else:
            auth = ('%s:%s' % (username, password)).encode('base64')
            authline = 'EPD_auth = %r' % auth.strip()
        auth_section = """
# EPD subscriber authentication is required to access the EPD
# repository.  To change your credentials, use the 'enpkg --userpass'
# command, which will ask you for your email address (or username) and
# password.
%s
""" % authline
    else:
        auth_section = ''

    py_ver = PY_VER
    sys_prefix = sys.prefix
    version = __version__

    if proxy:
        proxy_line = 'proxy = %r' % proxy
    else:
        proxy_line = '#proxy = <proxy string>  # e.g. "123.0.1.2:8080"'
    
    format_dict = {
                   'py_ver': PY_VER,
                   'sys_prefix': sys.prefix,
                   'version': version,
                   'proxy_line': proxy_line,
                   'auth_section': auth_section,
                   'webservice_base_url': webservice_base_url,
                   'repo_base_url': repo_base_url,
                   }
    
    fo = open(path, 'w')
    fo.write(RC_TMPL % format_dict)
    fo.close()
    print "Wrote configuration file:", path
    clear_cache()


def get_auth():
    """
    Retrieve the saved `auth` (username, password) tuple.
    """
    password = None
    old_auth = get('EPD_auth')
    if old_auth:
        username, password = old_auth.decode('base64').split(':')
        if not keyring:
            return username, password
        else:
            change_auth(username, password)
    username = get('EPD_username')
    if username and keyring:
        if hasattr(get_auth, 'password'):
            password = get_auth.password
        else:
            password = keyring.get_password(KEYRING_SERVICE_NAME, username)
            get_auth.password = password
    if username and password:
        return username, password
    else:
        return None, None


class AuthFailedError(Exception):
    pass


def web_auth(auth,
        api_url=None):
    """
    Authenticate a user's credentials (an `auth` tuple of username,
    password) using the web API.  Return a dictionary containing user
    info.

    Function taken from Canopy and modified.
    """
    import json
    import urllib2
    
    if api_url is None:
        api_url = '%s/accounts/user/info/' % (webservice_base_url)

    # Make basic local checks
    username, password = auth
    if username is None or password is None:
        raise AuthFailedError("Authentication error: User login is required.")

    # Authenticate with the web API
    auth = 'Basic ' + (':'.join(auth).encode('base64').strip())
    req = urllib2.Request(api_url, headers={'Authorization': auth})

    try:
        f = urllib2.urlopen(req)
    except urllib2.URLError as e:
        raise AuthFailedError("Authentication error: %s" % e.reason)

    try:
        res = f.read()
    except urllib2.HTTPError as e:
        raise AuthFailedError("Authentication error: %s" % e.reason)

    # See if web API refused to authenticate
    user = json.loads(res)
    if not(user['is_authenticated']):
        raise AuthFailedError('Authentication error: Invalid user login.')

    return user


def subscription_level(user):
    """
    Extract the level of EPD subscription from the dictionary (`user`)
    returned by the web API.
    """
    if 'has_subscription' in user:
        if user.get('is_authenticated', False) and user.get('has_subscription', False):
            return 'EPD Basic or above'
        elif user.get('is_authenticated', False) and not(user.get('has_subscription', False)):
            return 'EPD Free'
        else:
            return None
    else:  # don't know the subscription level
        if user.get('is_authenticated', False):
            return 'EPD'
        else:
            return None


def subscription_message(user):
    """
    Return a 'subscription level' message based on the `user`
    dictionary.

    `user` is a dictionary, probably retrieved from the web API, that
    may contain `is_authenticated`, and `has_subscription`.
    """
    message = ""

    if user.get('is_authenticated', False):
        username, password = get_auth()
        login = "You are logged in as %s" % username
        subscription = "Subscription level: %s" % subscription_level(user)
        name = user.get('first_name', '') + ' ' + user.get('last_name', '')
        name = name.strip()
        if name:
            name = ' (' + name + ')'
        message = login + name + '.\n' + subscription
    else:
        message = "You are not logged in.  To log in, type 'enpkg --userpass'."

    return message


def authenticate(auth, remote=None):
    """
    Attempt to authenticate the user's credentials by the appropriate
    means.

    `auth` is a tuple of (username, password).
    `remote` is enpkg.remote, required if not using the web API to authenticate

    If 'use_webservice' is set, authenticate with the web API and return
    a dictionary containing user info on success.

    Else, authenticate with remote.connect and return a dict containing
    is_authenticated=True on success.

    If authentication fails, raise an exception.
    """
    user = {}
    if get('use_webservice'):
        # check credentials using web API
        try:
            user = web_auth(auth)
            assert user['is_authenticated']
        except:
            raise
    else:
        # check credentials using remote.connect
        try:
            print 'Verifying user login...'
            remote.connect(auth)
            user = dict(is_authenticated=True)
        except KeyError:
            raise AuthFailedError('Authentication failed:'
                    ' Invalid user login.')
        except Exception as e:
            raise AuthFailedError('Authentication failed: %s.' % e)
    return user


def clear_auth():
    username = get('EPD_username')
    if username and keyring:
        keyring.set_password(KEYRING_SERVICE_NAME, username, '')
    change_auth('', None)


def change_auth(username, password):
    # clear the cache so the next get_auth is correct
    clear_cache()

    path = get_path()
    if path is None:
        write(username, password)
        return
    fi = open(path)
    data = fi.read()
    fi.close()

    if username is None and password is None:
        return

    if username and password:
        if keyring:
            keyring.set_password(KEYRING_SERVICE_NAME, username, password)
            authline = 'EPD_username = %r' % username
        else:
            auth = ('%s:%s' % (username, password)).encode('base64')
            authline = 'EPD_auth = %r' % auth.strip()

    pat = re.compile(r'^(EPD_auth|EPD_username)\s*=.*$', re.M)

    if username == '':
        data = pat.sub('', data)
    elif pat.search(data):
        data = pat.sub(authline, data)
    else:
        lines = data.splitlines()
        lines.insert(10, authline)
        data = '\n'.join(lines) + '\n'
    fo = open(path, 'w')
    fo.write(data)
    fo.close()


def checked_change_auth(username, password, remote=None):
    """
    Only run change_auth if the credentials are authenticated (or if the
    username is None).  Print out subscription info if successful.

    `remote` is enpkg.remote and is required if not using the web API to
    authenticate.

    If successful at authenticating, return a dictionary containing user info.
    """
    auth = (username, password)
    user = {}

    # For backwards compatibility
    if username is None or username is '':
        change_auth(username, password)
        return user

    try:
        user = authenticate(auth, remote)
    except Exception as e:
        print e.message
        print "No credentials saved."
    else:
        change_auth(username, password)
        print subscription_message(user)
    return user


def prepend_url(url):
    f = open(get_path(), 'r+')
    data = f.read()
    pat = re.compile(r'^IndexedRepos\s*=\s*\[\s*$', re.M)
    if not pat.search(data):
        sys.exit("Error: IndexedRepos section not found")
    data = pat.sub(r"IndexedRepos = [\n  '%s'," % url, data)
    f.seek(0)
    f.write(data)
    f.close()


def clear_cache():
    if hasattr(read, 'cache'):
        del read.cache


def read():
    """
    Return the configuration from the config file as a dictionary,
    fix some values, and give defaults.
    """
    if hasattr(read, 'cache'):
        return read.cache

    path = get_path()
    read.cache = default
    if path is None:
        return read.cache

    execfile(path, read.cache)
    for k in read.cache:
        v = read.cache[k]
        if k == 'IndexedRepos':
            read.cache[k] = [fill_url(url) for url in v]
        elif k in ('prefix', 'local'):
            read.cache[k] = abs_expanduser(v)
    return read.cache


def get(key, default=None):
    return read().get(key, default)


def print_config(remote):
    print "Python version:", PY_VER
    print "enstaller version:", __version__
    print "sys.prefix:", sys.prefix
    print "platform:", platform.platform()
    print "architecture:", platform.architecture()[0]
    print "use_webservice:", get('use_webservice')
    print "config file:", get_path()
    print "settings:"
    for k in 'prefix', 'local', 'noapp', 'proxy':
        print "    %s = %r" % (k, get(k))
    print "    IndexedRepos:", '(not used)' if get('use_webservice') else ''
    for repo in get('IndexedRepos'):
        print '        %r' % repo

    username, password = get_auth()
    user = {}
    try:
        user = authenticate((username, password), remote)
    except Exception as e:
        print e
    print subscription_message(user)

if __name__ == '__main__':
    write()
    print_config()
