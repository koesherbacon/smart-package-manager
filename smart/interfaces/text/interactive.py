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
from smart.interfaces.text.interface import TextInterface, getScreenWidth
from smart.matcher import MasterMatcher
from smart.const import VERSION, NEVER
from smart.option import OptionParser
from smart.transaction import *
from smart import *
from cmd import Cmd
import sys, os
import shlex


class TextInteractiveInterface(TextInterface):

    def run(self, command=None, argv=None):
        print "Smart Package Manager %s - Shell Mode" % VERSION
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

    prompt = "smart> "
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
            cmd, arg, line = self.parseline(line)
            if arg in ("-h", "--help"):
                try:
                    getattr(self, "help_"+cmd)()
                    return None
                except AttributeError:
                    pass
            return Cmd.onecmd(self, line)
        except Error, e:
            iface.error(str(e))
            return None

    def help_help(self):
        print "What would you expect!? ;-)"

    def help_EOF(self):
        print "The exit/quit/EOF command returns to the system."
    help_exit = help_EOF
    help_quit = help_EOF

    def do_EOF(self, line):
        print
        return True
    do_exit = do_EOF
    do_quit = do_EOF

    def help_shell(self):
        print "The shell command offers execution of system commands."
        print ""
        print "Usage: shell [<cmd>]"
        print "       ![<cmd>]"

    def do_shell(self, line):
        if not line.strip():
            line = os.environ.get("SHELL", "/bin/sh")
        os.system(line)

    def help_status(self):
        print "The status command shows currently marked changes."
        print ""
        print "Usage: status"

    def do_status(self, line):
        if line.strip():
            raise Error, "Invalid arguments"
        if not self._changeset:
            print "There are no marked changes."
        else:
            iface.showChangeSet(self._changeset)

    def help_install(self):
        print "The install command marks packages for installation."
        print ""
        print "Usage: install <pkgname> ..."

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

    def help_reinstall(self):
        print "The reinstall command marks packages for reinstallation."
        print ""
        print "Usage: reinstall <pkgname> ..."

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

    def help_upgrade(self):
        print "The upgrade command marks packages for upgrading."
        print ""
        print "Usage: upgrade <pkgname> ..."

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

    def help_remove(self):
        print "The remove command marks packages for being removed."
        print ""
        print "Usage: remove <pkgname> ..."

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

    def help_keep(self):
        print "The keep command unmarks currently marked packages."
        print ""
        print "Usage: keep <pkgname> ..."

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

    def help_fix(self):
        print ("The fix command verifies relations of given packages\n"
               "and marks the necessary changes for fixing them.")
        print ""
        print "Usage: fix <pkgname> ..."

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

    def help_download(self):
        print ("The download command fetches the given packages\n"
               "to the local filesystem.")
        print ""
        print "Usage: download <pkgname> ..."

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

    def help_commit(self):
        print "The commit command applies marked changes in the system."
        print ""
        print "Usage: commit"

    def do_commit(self, line):
        transaction = Transaction(self._ctrl.getCache(),
                                  changeset=self._changeset)
        if self._ctrl.commitTransaction(transaction):
            del self._undo[:]
            del self._redo[:]
            self._changeset.clear()
            self._ctrl.updateCache()

    def help_undo(self):
        print "The undo command reverts marked changes."
        print ""
        print "Usage: undo"

    def do_undo(self, line):
        if not self._undo:
            return
        newchangeset = ChangeSet(self._ctrl.getCache())
        newchangeset.setPersistentState(self._undo[0])
        if iface.confirmChange(self._changeset, newchangeset):
            state = self._undo.pop(0)
            self._redo.insert(0, self._changeset.getPersistentState())
            self._changeset.setPersistentState(state)

    def help_redo(self):
        print "The redo command reapplies undone changes."
        print ""
        print "Usage: redo"

    def do_redo(self, line):
        if not self._redo:
            return
        newchangeset = ChangeSet(self._ctrl.getCache())
        newchangeset.setPersistentState(self._redo[0])
        if iface.confirmChange(self._changeset, newchangeset):
            state = self._redo.pop(0)
            self._undo.insert(0, self._changeset.getPersistentState())
            self._changeset.setPersistentState(state)

    def help_ls(self):
        print ("The ls command lists packages by name. Wildcards\n"
               "are accepted.")
        print ""
        print "Options:"
        print "   -i  List only installed packages"
        print "   -n  List only new packages"
        print "   -v  Show versions"
        print "   -s  Show summaries"
        print ""
        print "Usage: ls [options] [<string>] ..."

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

    def help_update(self):
        print "The update command will update channel information."
        print ""
        print "Usage: update [<alias>] ..."

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

    def help_query(self):
        print ("The query command allows querying package information,\n"
               "and accepts the same options available in the command\n"
               "line interface.")
        print ""
        print "Usage: query [options] [<pkgname>] ..."

    complete_query = completeAll
    def do_query(self, line):
        from smart.commands import query
        try:
            opts = query.parse_options(shlex.split(line))
            query.main(opts, self._ctrl, updatecache=False)
        except SystemExit:
            pass

    def help_search(self):
        print "The search command allows searching for packages."
        print ""
        print "Usage: search <string> ..."

    complete_search = completeAll
    def do_search(self, line):
        from smart.commands import search
        try:
            opts = search.parse_options(shlex.split(line))
            search.main(opts, self._ctrl, updatecache=False)
        except SystemExit:
            pass

# vim:ts=4:sw=4:et