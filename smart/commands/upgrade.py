#
# Copyright (c) 2004 Conectiva, Inc.
#
# Written by Gustavo Niemeyer <niemeyer@conectiva.com>
#
# This file is part of Smart Package Manager.
#
# Smart Package Manager is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation; either version 2 of the License, or (at
# your option) any later version.
#
# Smart Package Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Smart Package Manager; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
from smart.transaction import Transaction, PolicyUpgrade, UPGRADE
from smart.matcher import MasterMatcher
from smart.option import OptionParser
from smart import *
import string
import re

USAGE="smart upgrade [options] [package] ..."

DESCRIPTION="""
This command will upgrade one or more packages which
are currently installed in the system. If no packages
are given, all installed packages will be checked.
"""

EXAMPLES="""
smart upgrade
smart upgrade pkgname
smart upgrade '*kgnam*'
smart upgrade pkgname-1.0
smart upgrade pkgname-1.0-1
smart upgrade pkgname1 pkgname2
"""

def parse_options(argv):
    parser = OptionParser(usage=USAGE,
                          description=DESCRIPTION,
                          examples=EXAMPLES)
    parser.add_option("--stepped", action="store_true",
                      help="split operation in steps")
    parser.add_option("--urls", action="store_true",
                      help="dump needed urls and don't commit operation")
    parser.add_option("--download", action="store_true",
                      help="download packages and don't commit operation")
    parser.add_option("--force", action="store_true",
                      help="do not ask for confirmation")
    opts, args = parser.parse_args(argv)
    opts.args = args
    return opts

def main(ctrl, opts):

    ctrl.updateCache()
    cache = ctrl.getCache()
    trans = Transaction(cache, PolicyUpgrade)
    pkgs = [x for x in cache.getPackages() if x.installed]
    if opts.args:
        newpkgs = []
        for arg in opts.args:
            matcher = MasterMatcher(arg)
            fpkgs = matcher.filter(pkgs)
            if not fpkgs:
                raise Error, "'%s' matches no installed packages" % arg
            newpkgs.extend(fpkgs)
        pkgs = dict.fromkeys(newpkgs).keys()
    for pkg in pkgs:
        trans.enqueue(pkg, UPGRADE)
    iface.showStatus("Computing transaction...")
    trans.run()
    if not trans:
        iface.showStatus("No interesting upgrades available!")
    else:
        iface.hideStatus()
        confirm = not opts.force
        if opts.urls:
            ctrl.dumpTransactionURLs(trans)
        elif opts.download:
            ctrl.downloadTransaction(trans, confirm=confirm)
        elif opts.stepped:
            ctrl.commitTransactionStepped(trans, confirm=confirm)
        else:
            ctrl.commitTransaction(trans, confirm=confirm)

# vim:ts=4:sw=4:et