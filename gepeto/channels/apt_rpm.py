from gepeto.backends.rpm.header import RPMPackageListLoader
from gepeto.channel import Channel, ChannelDataError
from gepeto.const import SUCCEEDED, FAILED
from gepeto.cache import LoaderSet
from gepeto import *
import posixpath

class APTRPMChannel(Channel):

    def __init__(self, baseurl, comps, *args):
        Channel.__init__(self, *args)
        
        self._baseurl = baseurl
        self._comps = comps

        self._loader = LoaderSet()

    def getFetchSteps(self):
        return len(self._comps)+1

    def fetch(self, fetcher, progress):

        fetcher.reset()

        # Fetch release file
        url = posixpath.join(self._baseurl, "base/release")
        item = fetcher.enqueue(url)
        fetcher.run(progress=progress)
        failed = item.getFailedReason()
        if failed:
            iface.warning("Failed acquiring release file for '%s': %s" %
                          (self._alias, failed))
            iface.debug("%s: %s" % (url, failed))
            progress.add(len(self._comps))
            progress.show()
            return

        # Parse release file
        md5sum = {}
        started = False
        for line in open(item.getTargetPath()):
            if not started:
                if line.startswith("MD5Sum:"):
                    started = True
            elif not line.startswith(" "):
                break
            else:
                try:
                    md5, size, path = line.split()
                except ValueError:
                    pass
                else:
                    md5sum[path] = (md5, int(size))

        # Fetch package lists
        fetcher.reset()
        items = []
        for comp in self._comps:
            pkglist = "base/pkglist."+comp
            url = posixpath.join(self._baseurl, pkglist)
            if pkglist+".bz2" in md5sum:
                upkglist = pkglist
                pkglist += ".bz2"
                url += ".bz2"
            elif pkglist+".gz" in md5sum:
                upkglist = pkglist
                pkglist += ".gz"
                url += ".gz"
            elif pkglist not in md5sum:
                iface.warning("Component '%s' is not in release file" % comp)
                continue
            else:
                upkglist = None
            info = {"component": comp, "uncomp": True}
            info["md5"], info["size"] = md5sum[pkglist]
            if upkglist:
                info["uncomp_md5"], info["uncomp_size"] = md5sum[upkglist]
            items.append(fetcher.enqueue(url, **info))

        fetcher.run(progress=progress)

        firstfailure = True
        for item in items:
            if item.getStatus() == SUCCEEDED:
                localpath = item.getTargetPath()
                loader = RPMPackageListLoader(localpath, self._baseurl)
                loader.setChannel(self)
                self._loader.append(loader)
            else:
                if firstfailure:
                    firstfailure = False
                    iface.warning("Failed acquiring information for '%s':" %
                                  self._alias)
                iface.warning("%s: %s" % (item.getURL(), item.getFailedReason()))

def create(type, alias, data):
    name = None
    description = None
    priority = 0
    baseurl = None
    comps = None
    if isinstance(data, dict):
        name = data.get("name")
        description = data.get("description")
        baseurl = data.get("baseurl")
        comps = (data.get("components") or "").split()
        priority = data.get("priority", 0)
    elif getattr(data, "tag", None) == "channel":
        for n in data.getchildren():
            if n.tag == "name":
                name = n.text
            elif n.tag == "description":
                description = n.text
            elif n.tag == "priority":
                priority = n.text
            elif n.tag == "baseurl":
                baseurl = n.text
            elif n.tag == "components":
                comps = n.text.split()
    else:
        raise ChannelDataError
    if not baseurl:
        raise Error, "Channel '%s' has no baseurl" % alias
    if not comps:
        raise Error, "Channel '%s' has no components" % alias
    try:
        priority = int(priority)
    except ValueError:
        raise Error, "Invalid priority"
    return APTRPMChannel(baseurl, comps,
                         type, alias, name, description, priority)

# vim:ts=4:sw=4:et