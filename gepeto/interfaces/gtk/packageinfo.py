#!/usr/bin/python
from gepeto.interfaces.gtk.packageview import GtkPackageView
import gobject, gtk, pango

class GtkPackageInfo(gtk.Alignment):

    def __init__(self):
        gtk.Alignment.__init__(self)
        self.__gobject_init__()

        self._pkg = None

        self._notebook = gtk.Notebook()
        self._notebook.show()
        self.add(self._notebook)
        
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.set_border_width(5)
        sw.show()

        self._descrtv = gtk.TextView()
        self._descrtv.set_editable(False)
        self._descrtv.set_cursor_visible(False)
        self._descrtv.set_left_margin(5)
        self._descrtv.set_right_margin(5)
        self._descrtv.show()
        buffer = self._descrtv.get_buffer()
        fontdesc = self._notebook.style.font_desc.copy()
        fontdesc.set_size(fontdesc.get_size()-pango.SCALE)
        buffer.create_tag("description", font_desc=fontdesc)
        fontdesc.set_weight(pango.WEIGHT_BOLD)
        buffer.create_tag("summary", font_desc=fontdesc)
        sw.add(self._descrtv)

        label = gtk.Label("Description")
        self._notebook.append_page(sw, label)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.set_border_width(5)
        sw.show()

        self._conttv = gtk.TextView()
        self._conttv.set_editable(False)
        self._conttv.set_cursor_visible(False)
        self._conttv.set_left_margin(5)
        self._conttv.set_right_margin(5)
        self._conttv.show()
        buffer = self._conttv.get_buffer()
        fontdesc = self._notebook.style.font_desc.copy()
        fontdesc.set_size(fontdesc.get_size()-pango.SCALE)
        buffer.create_tag("content", font_desc=fontdesc)
        sw.add(self._conttv)

        label = gtk.Label("Content")
        self._notebook.append_page(sw, label)

        label = gtk.Label("Relations")
        self._relations = GtkPackageView()
        self._relations.set_border_width(5)
        self._relations.getTreeView().set_headers_visible(False)
        self._relations.show()
        self._notebook.append_page(self._relations, label)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_border_width(5)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.show()

        model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        self._channels = gtk.TreeView(model)
        self._channels.show()
        renderer = gtk.CellRendererText()
        self._channels.insert_column_with_attributes(-1, "Alias",
                                                     renderer, text=0)
        self._channels.insert_column_with_attributes(-1, "Name",
                                                     renderer, text=1)
        sw.add(self._channels)

        label = gtk.Label("Channels")
        self._notebook.append_page(sw, label)

        self._notebook.connect("switch_page", self._switchPage)

    def _switchPage(self, notebook, page, pagenum):
        self.setPackage(self._pkg, _pagenum=pagenum)

    def setPackage(self, pkg, _pagenum=None):

        self._pkg = pkg

        if _pagenum is not None:
            num = _pagenum
        else:
            num = self._notebook.get_current_page()

        if num == 0:

            # Update summary/description.

            descrbuf = self._descrtv.get_buffer()
            descrbuf.set_text("")
            if not pkg: return

            iter = descrbuf.get_end_iter()
            for loader in pkg.loaders:
                info = loader.getInfo(pkg)
                summary = info.getSummary()
                if summary:
                    descrbuf.insert_with_tags_by_name(iter, summary+"\n\n",
                                                      "summary")
                    description = info.getDescription()
                    if description != summary:
                        descrbuf.insert_with_tags_by_name(iter,
                                                          description+"\n\n",
                                                          "description")
                    break
            else:
                loader = pkg.loaders.keys()[0]

        elif num == 1:

            # Update contents.

            contbuf = self._conttv.get_buffer()
            contbuf.set_text("")
            if not pkg: return

            iter = contbuf.get_end_iter()
            for loader in pkg.loaders:
                if loader.getInstalled():
                    break
            else:
                loader = pkg.loaders.keys()[0]
            info = loader.getInfo(pkg)
            for path in info.getPathList():
                contbuf.insert_with_tags_by_name(iter, path+"\n", "content")

        elif num == 2:

            if not pkg:
                self._relations.setPackages([])
                return

            self._setRelations(pkg)

        elif num == 3:

            model = self._channels.get_model()
            model.clear()

            if not pkg:
                return

            items = []
            for loader in pkg.loaders:
                channel = loader.getChannel()
                item = (channel.getAlias(), channel.getName() or "")
                items.append(item)

            items.sort()

            lastitem = None
            for item in items:
                if item != lastitem:
                    lastitem = item
                    model.append(item)

    def _setRelations(self, pkg):

        class Sorter(str):
            ORDER = ["Provides", "Upgrades", "Requires", "Conflicts"]
            def __cmp__(self, other):
                return cmp(self.ORDER.index(str(self)),
                           self.ORDER.index(str(other)))
            def __lt__(self, other):
                return cmp(self, other) < 0

        relations = {}

        for prv in pkg.provides:

            prvmap = {}
            
            requiredby = []
            for req in prv.requiredby:
                requiredby.extend(req.packages)
            if requiredby:
                prvmap["Required By"] = requiredby

            upgradedby = []
            for upg in prv.upgradedby:
                upgradedby.extend(upg.packages)
            if upgradedby:
                prvmap["Upgraded By"] = upgradedby

            conflictedby = []
            for cnf in prv.conflictedby:
                conflictedby.extend(cnf.packages)
            if conflictedby:
                prvmap["Conflicted By"] = conflictedby

            if prvmap:
                relations.setdefault(Sorter("Provides"), {})[str(prv)] = prvmap

        requires = {}
        for req in pkg.requires:
            lst = requires.setdefault(str(req), [])
            for prv in req.providedby:
                lst.extend(prv.packages)
            lst[:] = dict.fromkeys(lst).keys()
        if requires:
            relations[Sorter("Requires")] = requires

        upgrades = {}
        for upg in pkg.upgrades:
            lst = upgrades.setdefault(str(upg), [])
            for prv in upg.providedby:
                lst.extend(prv.packages)
            lst[:] = dict.fromkeys(lst).keys()
        if upgrades:
            relations[Sorter("Upgrades")] = upgrades

        conflicts = {}
        for cnf in pkg.conflicts:
            lst = conflicts.setdefault(str(cnf), [])
            for prv in cnf.providedby:
                lst.extend(prv.packages)
            lst[:] = dict.fromkeys(lst).keys()
        if conflicts:
            relations[Sorter("Conflicts")] = conflicts

        self._relations.setPackages(relations)

gobject.type_register(GtkPackageInfo)

# vim:ts=4:sw=4:et