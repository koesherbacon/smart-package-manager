#
# Copyright (c) 2004 Conectiva, Inc.
#
# Written by Gustavo Niemeyer <niemeyer@conectiva.com>
#
# This file is part of Gepeto.
#
# Gepeto is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Gepeto is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gepeto; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
from gepeto.interfaces.text.interface import TextInterface
from gepeto.interfaces.text.util import getScreenWidth
from gepeto.matcher import MasterMatcher
from gepeto.const import VERSION, NEVER
from gepeto.option import OptionParser
from gepeto.transaction import *
from gepeto import *
from cmd import Cmd
import sys, os
import shlex


class TextInteractiveInterface(TextInterface):

    def run(self):
        print "Gepeto %s - Shell Mode" % VERSION
        print
        self._ctrl.updateCache()
        Interpreter(self._ctrl).cmdloop()

    def confirmChange(self, oldchangeset, newchangeset, expected=0):
        if newchangeset == oldchangeset:
            return False
        changeset = newchangeset.difference(oldchangeset)
        keep = []
        for pkg in oldchangeset:
            if pkg not in newchangeset:
                keep.append(pkg)
        if len(keep)+len(changeset) <= expected:
            self.showChangeSet(changeset, keep=keep)
            return True
        return self.showChangeSet(changeset, keep=keep, confirm=True)

class Interpreter(Cmd):

    prompt = "gpt> "
    ruler = "-"

    # Translate these:
    doc_header = "Documented commands (type help <topic>):"
    undoc_header = "Undocumented commands:"
    misc_header = "Miscelaneous help topics:"
    nohelp = "*** No help on %s"

    def __init__(self, ctrl):
        Cmd.__init__(self)
        self._ctrl = ctrl
        self._changeset = ChangeSet(ctrl.getCache())

        self._undo = []
        self._redo = []

    def completeAll(self, text, line, begidx, endidx):
        matches = []
        for pkg in self._ctrl.getCache().getPackages():
            value = str(pkg)
            if value.startswith(text):
                matches.append(value)
        return matches

    def completeInstalled(self, text, line, begidx, endidx):
        matches = []
        for pkg in self._ctrl.getCache().getPackages():
            if pkg.installed:
                value = str(pkg)
                if value.startswith(text):
                    matches.append(value)
        return matches

    def completeAvailable(self, text, line, begidx, endidx):
        matches = []
        for pkg in self._ctrl.getCache().getPackages():
            if not pkg.installed:
                value = str(pkg)
                if value.startswith(text):
                    matches.append(value)
        return matches

    def completeMarked(self, text, line, begidx, endidx):
        matches = []
        for pkg in self._ctrl.getCache().getPackages():
            if pkg in self._changeset:
                value = str(pkg)
                if value.startswith(text):
                    matches.append(value)
        return matches

    def saveUndo(self):
        state = self._changeset.getPersistentState()
        if not self._undo or state != self._undo[0]:
            self._undo.insert(0, self._changeset.getPersistentState())
            del self._redo[:]
            del self._undo[20:]

    def pkgsFromLine(self, line):
        args = shlex.split(line)
        for arg in args:
            matcher = MasterMatcher(arg)
            pkgs = matcher.filter(self._ctrl.getCache().getPackages())
            if not pkgs:
                raise Error, "'%s' matches no packages" % arg
            if len(pkgs) > 1:
                sortUpgrades(pkgs)
            yield arg, pkgs

    def preloop(self):
        Cmd.preloop(self)
        if self.completekey:
            try:
                import readline
                delims = readline.get_completer_delims()
                delims = "".join([x for x in delims if x != "-"])
                readline.set_completer_delims(delims)
            except ImportError:
                pass

    def emptyline(self):
        pass

    def onecmd(self, line):
        try:
            return Cmd.onecmd(self, line)
        except Error, e:
            iface.error(str(e))
            return None

    def do_EOF(self, line):
        print
        return True
    do_exit = do_EOF
    do_quit = do_EOF

    def do_shell(self, line):
        if not line.strip():
            line = os.environ.get("SHELL", "/bin/sh")
        os.system(line)

    def do_status(self, line):
        if line.strip():
            raise Error, "Invalid arguments"
        if not self._changeset:
            print "There are no marked changes."
        else:
            iface.showChangeSet(self._changeset)

    complete_install = completeAvailable
    def do_install(self, line):
        cache = self._ctrl.getCache()
        transaction = Transaction(cache, policy=PolicyInstall)
        transaction.setState(self._changeset)
        changeset = transaction.getChangeSet()
        expected = 0
        for arg, pkgs in self.pkgsFromLine(line):
            expected += 1
            if pkgs[0].installed:
                raise Error, "%s matches '%s' and is already installed" % \
                             (pkgs[0], arg)
            pkgs = [x for x in pkgs if not x.installed]
            if len(pkgs) > 1:
                iface.warning("'%s' matches multiple packages, selecting: %s" % \
                              (arg, pkgs[0]))
            transaction.enqueue(pkgs[0], INSTALL)
        transaction.run()
        if iface.confirmChange(self._changeset, changeset, expected):
            self.saveUndo()
            self._changeset.setState(changeset)

    complete_reinstall = completeInstalled
    def do_reinstall(self, line):
        cache = self._ctrl.getCache()
        transaction = Transaction(cache, policy=PolicyInstall)
        transaction.setState(self._changeset)
        changeset = transaction.getChangeSet()
        expected = 0
        for arg, pkgs in self.pkgsFromLine(line):
            expected += 1
            if not pkgs:
                raise Error, "'%s' matches no installed packages" % arg
            if len(pkgs) > 1:
                raise Error, "'%s' matches multiple installed packages" % arg
            transaction.enqueue(pkgs[0], REINSTALL)
        transaction.run()
        if iface.confirmChange(self._changeset, changeset, expected):
            self.saveUndo()
            self._changeset.setState(changeset)

    complete_upgrade = completeInstalled
    def do_upgrade(self, line):
        cache = self._ctrl.getCache()
        transaction = Transaction(cache, policy=PolicyUpgrade)
        transaction.setState(self._changeset)
        changeset = transaction.getChangeSet()
        expected = 0
        if not line.strip():
            for pkg in cache.getPackages():
                if pkg.installed:
                    transaction.enqueue(pkg, UPGRADE)
        else:
            for arg, pkgs in self.pkgsFromLine(line):
                expected += 1
                found = False
                for pkg in pkgs:
                    if pkg.installed:
                        found = True
                        transaction.enqueue(pkg, UPGRADE)
                if not found:
                    raise Error, "'%s' matches no installed packages" % arg
        transaction.run()
        if changeset == self._changeset:
            print "No interesting upgrades available!"
        elif iface.confirmChange(self._changeset, changeset, expected):
            self.saveUndo()
            self._changeset.setState(changeset)

    complete_remove = completeInstalled
    def do_remove(self, line):
        cache = self._ctrl.getCache()
        transaction = Transaction(cache, policy=PolicyRemove)
        transaction.setState(self._changeset)
        changeset = transaction.getChangeSet()
        expected = 0
        for arg, pkgs in self.pkgsFromLine(line):
            expected += 1
            found = False
            for pkg in pkgs:
                if pkg.installed:
                    found = True
                    transaction.enqueue(pkg, REMOVE)
            if not found:
                raise Error, "'%s' matches no installed packages" % arg
        transaction.run()
        if iface.confirmChange(self._changeset, changeset, expected):
            self.saveUndo()
            self._changeset.setState(changeset)

    complete_keep = completeMarked
    def do_keep(self, line):
        cache = self._ctrl.getCache()
        transaction = Transaction(cache, policy=PolicyInstall)
        transaction.setState(self._changeset)
        changeset = transaction.getChangeSet()
        expected = 0
        for arg, pkgs in self.pkgsFromLine(line):
            expected += 1
            pkgs = [x for x in pkgs if x in changeset]
            if not pkgs:
                raise Error, "'%s' matches no marked packages" % arg
            for pkg in pkgs:
                transaction.enqueue(pkg, KEEP)
        transaction.run()
        if iface.confirmChange(self._changeset, changeset, expected):
            self.saveUndo()
            self._changeset.setState(changeset)

    complete_fix = completeAll
    def do_fix(self, line):
        cache = self._ctrl.getCache()
        transaction = Transaction(cache, policy=PolicyInstall)
        transaction.setState(self._changeset)
        changeset = transaction.getChangeSet()
        expected = 0
        for arg, pkgs in self.pkgsFromLine(line):
            expected += 1
            for pkg in pkgs:
                transaction.enqueue(pkg, FIX)
        transaction.run()
        if changeset == self._changeset:
            print "No problems to resolve!"
        elif iface.confirmChange(self._changeset, changeset, expected):
            self.saveUndo()
            self._changeset.setState(changeset)

    complete_download = completeAll
    def do_download(self, line):
        packages = []
        for arg, pkgs in self.pkgsFromLine(line):
            if len(pkgs) > 1:
                iface.warning("'%s' matches multiple packages, selecting: %s" % \
                              (arg, pkgs[0]))
            packages.append(pkgs[0])
        if packages:
            self._ctrl.downloadPackages(packages, targetdir=os.getcwd())

    def do_commit(self, line):
        transaction = Transaction(self._ctrl.getCache(),
                                  changeset=self._changeset)
        if self._ctrl.commitTransaction(transaction):
            del self._undo[:]
            del self._redo[:]
            self._changeset.clear()
            self._ctrl.updateCache()

    def do_undo(self, line):
        if not self._undo:
            return
        newchangeset = ChangeSet(self._ctrl.getCache())
        newchangeset.setPersistentState(self._undo[0])
        if iface.confirmChange(self._changeset, newchangeset):
            state = self._undo.pop(0)
            self._redo.insert(0, self._changeset.getPersistentState())
            self._changeset.setPersistentState(state)

    def do_redo(self, line):
        if not self._redo:
            return
        newchangeset = ChangeSet(self._ctrl.getCache())
        newchangeset.setPersistentState(self._redo[0])
        if iface.confirmChange(self._changeset, newchangeset):
            state = self._redo.pop(0)
            self._undo.insert(0, self._changeset.getPersistentState())
            self._changeset.setPersistentState(state)

    complete_ls = completeAll
    def do_ls(self, line):
        pkgs = self._ctrl.getCache().getPackages()
        args = shlex.split(line)
        parser = OptionParser(add_help_option=False)
        parser.add_option("-i", action="store_true", dest="installed")
        parser.add_option("-v", action="store_true", dest="version")
        parser.add_option("-s", action="store_true", dest="summary")
        parser.add_option("-n", action="store_true", dest="new")
        opts, args = parser.parse_args(args)
        if opts.installed:
            pkgs = [x for x in pkgs if x.installed]
        if opts.new:
            pkgs = sysconf.filterByFlag("new", pkgs)
        if args:
            newpkgs = []
            for arg in args:
                matcher = MasterMatcher(arg)
                fpkgs = matcher.filter(pkgs)
                if not fpkgs:
                    raise Error, "'%s' matches no packages" % arg
                newpkgs.extend(fpkgs)
            pkgs = newpkgs
        pkgs = dict.fromkeys(pkgs).keys()
        pkgs.sort()

        if opts.summary:
            for pkg in pkgs:
                if opts.version:
                    print str(pkg), "-",
                else:
                    print pkg.name, "-",
                for loader in pkg.loaders:
                    info = loader.getInfo(pkg)
                    summary = info.getSummary()
                    if summary:
                        print summary
                        break
                else:
                    print
            return

        maxnamelen = 0
        for pkg in pkgs:
            if opts.version:
                namelen = len(str(pkg))
            else:
                namelen = len(pkg.name)
            if namelen > maxnamelen:
                maxnamelen = namelen

        screenwidth = getScreenWidth()
        perline = screenwidth/(maxnamelen+2)
        if perline == 0:
            perline = 1
        columnlen = screenwidth/perline
        numpkgs = len(pkgs)
        numlines = (numpkgs+perline-1)/perline
        blank = " "*columnlen
        out = sys.stdout
        for line in range(numlines):
            for entry in range(perline):
                k = line+(entry*numlines)
                if k >= numpkgs:
                    break
                pkg = pkgs[k]
                s = opts.version and str(pkg) or pkg.name
                out.write(s)
                out.write(" "*(columnlen-len(s)))
            print

    def complete_update(self, text, line, begidx, endidx):
        matches = []
        for channel in self._ctrl.getChannels():
            alias = channel.getAlias()
            if alias.startswith(text):
                matches.append(alias)
        return matches
        
    def do_update(self, line):
        args = shlex.split(line)
        if args:
            channels = [x for x in self._ctrl.getChannels()
                        if x.getAlias() in args]
            if not channels:
                return
        else:
            channels = None
        self._ctrl.updateCache(channels, caching=NEVER)
        cache = self._ctrl.getCache()
        newpackages = sysconf.filterByFlag("new", cache.getPackages())
        if not newpackages:
            iface.showStatus("Channels have no new packages.")
        else:
            if len(newpackages) <= 10:
                newpackages.sort()
                info = ":\n"
                for pkg in newpackages:
                    info += "    %s\n" % pkg
            else:
                info = "."
            iface.showStatus("Channels have %d new packages%s"
                             % (len(newpackages), info))