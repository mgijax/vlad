#
# Vlad.py
#
#-------------------------------------------------------------------

# standard Python libs
import sys
import types
import os
import re
import optparse
import time
import configparser
import tempfile

# Vlad libs
from . import Annotation
from . import Ontology
from . import Analyzer
from . import ResultsWriter
from . import colors

#-------------------------------------------------------------------

VERSION = "1.8.0"

#-------------------------------------------------------------------

class Vlad(object):
    def __init__(self):
        self.cfgParser = configparser.ConfigParser()
        self.VERSION = VERSION
        self.optParser = None
        self.options = None
        self.ontology = None
        self.annotations = None
        self.qsets = []
        self.results = None
        self.term2results = None
        self.notfound = None
        self.messages = []
        self.summary = []
        self.urlMap = {}
        self.batchUrlMap = {}
        self.initArgParser()

    def initArgParser(self, pclass=optparse.OptionParser):
        usage = "\n\tpython %s -o ontologyfile -a annotationfile [options]" % sys.argv[0]
        usage += "\nFor help:\n\tpython %s -h" % sys.argv[0]
        self.optParser = pclass(usage)

        self.optParser.add_option(
            "-R", 
            dest="runname", 
            default="Vlad Results",
            metavar="NAME", 
            help="Run name. Provides a title for the output." + \
                " (default='Vlad Results'")

        self.optParser.add_option(
            "-g", 
            dest="configfiles", 
            default=[],
            action="append",
            metavar="CONFIGFILE", 
            help="Configuration file. (optional, repeatible)")

        self.optParser.add_option(
            "-y", 
            dest="analysis", 
            default="enrichment",
            help="Type of analysis to perform: enrichment, depletion, or percentage. (default=enrichment)")

        self.optParser.add_option(
            "-a", 
            dest="annotationfile", 
            default=None,
            metavar="ANNOTATIONFILE", 
            help="Registered annot set name or a GAF format annotation file. (required)")

        self.optParser.add_option(
            "-o", 
            dest="ontologyfile", 
            default=None,
            metavar="VOCABULARY", 
            help="Registered ontology file name or an OBO format ontology file. (required)")

        self.optParser.add_option(
            "-q", 
            "-f", 
            dest="qsets", 
            default=[],
            metavar="IDS",
            action="callback",
            type="string",
            callback=self.parseQuerySetArg,
            help="Query set(s). Use -q to specify IDs/symbols " + \
                "directly on the command line. Use -f to specify a file. " + \
                "Repeatable. At least one required.")

        self.optParser.add_option(
            "-n",
            dest="qsnames",
            default=[],
            metavar="NAME",
            action="callback",
            type="string",
            callback=self.parseQuerySetNameArg,
            help="Specifies a name for the preceding query set (-q or -f). " + \
                "Follow each -q or -f with a -n to specify a name for the query set. " + \
                "The default name for a -q query set is 'qsetn', where n is 0, 1, 2, ... " + \
                "The default name for a -f query set is the name of the file. ")

        self.optParser.add_option(
            "-c",
            dest="qscolors",
            default=[],
            metavar="COLOR",
            action="callback",
            type="string",
            callback=self.parseQuerySetColorArg,
            help="Specifies a color for the preceding query set (-q or -f). " + \
                "Follow each -q or -f with a -c to specify a color that will be used " + \
                "in the output to signify this query set. COLOR is an HSV color value " + \
                "in the form 'h,s,v', where h, s, and v are all floats in the range 0 to 1. " + \
                "If the i-th query set is NOT assigned a color via this argument, the " + \
                "i-th color in the configuration option ('DOT','qscolors') will be used." + \
                "")

        self.optParser.add_option(
            "-u", 
            "-U",
            dest="uset", 
            default=[],
            metavar="IDS",
            action="callback",
            type="string",
            callback=self.parseUniverseSetArg,
            help="Universe set. Use -u to specify IDs/symbols " + \
                "directly on the command line. Use -U to specify a file. " + \
                "Optional. Default is to use entire database as universe set")

        self.optParser.add_option(
            "-x", 
            dest="exclude", 
            default=set(),
            action="callback",
            callback=self.parseExcludeArg,
            type="string",
            metavar="CODE", 
            help="Evidence code(s) to exclude, e.g. '-x IEA'")

        self.optParser.add_option(
            "-O", 
            dest="outputfiles", 
            default=[],
            action='append',
            metavar="FILE", 
            help="Output file. Repeatible. Use '-' for standard out.")

    def parseArgs(self, args):
        (self.options, xxx) = self.optParser.parse_args(args)
        self.readConfig(self.options.configfiles)
        if self.options.ontologyfile is None:
            self.optParser.error("No ontology file specified.")
        if self.options.annotationfile is None:
            self.optParser.error("No annotation file specified.")
        if len(self.options.qsets) == 0:
            self.optParser.error("No query set(s) specified. At least one -q or -f is required.")
        self.options.staticdir = self.options.vladdir

    def readConfig(self, files):
        self.cfgParser.read(files)
        if self.cfgParser.has_section('VLAD'):
            for n,v in self.cfgParser.items('VLAD'):
                if not self.options.__dict__.get(n,None):
                    if n == "exclude":
                        v = set( self.parseExcludeList(v) )
                    elif n == "maxage":
                        # Max age is given as days. Convert to seconds.
                        v = float(v)*24*3600
                    self.options.__dict__[n] = v
        self.options.oconfigs = self.getOntologyConfig(self.cfgParser)
        self.options.aconfigs = self.getAnnotationSetConfig(self.cfgParser, self.options.oconfigs)
        # see if -a was a file or an annotation set name
        asname = self.options.annotationfile
        if asname and hasattr(self.options.aconfigs, asname):
            # it was a name. look it up and set both the annot file and ontol file
            asconfig = getattr(self.options.aconfigs, asname)
            self.options.annotationconfig = asconfig
            self.options.annotationfile = asconfig.file
            self.options.ontologyconfig = asconfig.ontology
            self.options.ontologyfile = asconfig.ontology.file
        else:
            self.options.annotationconfig = {}

        # see if -o was a file or an ontology name
        oname = self.options.ontologyfile
        if oname and hasattr(self.options.oconfigs, oname):
            # it was a name. look it up and set the ontol file
            oconfig = getattr(self.options.oconfigs, oname)
            self.options.ontologyfile = oconfig.file
            self.options.ontologyconfig = oconfig
        else:
            self.options.ontologyconfig = {}

        if self.cfgParser.has_option("DOT", "qscolors"):
            qscs = eval(self.cfgParser.get("DOT","qscolors"))
            for i,c in enumerate(self.options.qscolors):
                if c is None:
                    self.options.qscolors[i] = qscs[i%len(qscs)]
            #
        self.options.qsid2color = {}
        for i,qs in enumerate(self.options.qsnames):
            self.options.qsid2color[qs] = self.options.qscolors[i]

    def getOntologyConfig(self, config):
        oconfigs = _blank_()
        for sn in config.sections():
            if sn.startswith("Ontology."):
                o = _blank_()
                o.name = sn.split(".",1)[1]
                setattr(oconfigs, o.name, o)
                o.order = config.get(sn, 'order', fallback=100)
                o.label = config.get(sn, 'name')
                o.file = config.get(sn, 'file')
                o.linkurl = None
                if config.has_option(sn, 'linkurl'):
                    o.linkurl = config.get(sn, 'linkurl')
                o.evidencecodes = config.get(sn, 'evidencecodes')
                o.defaultexcluded = ''
                if config.has_option(sn,'defaultexcluded'):
                    o.defaultexcluded = config.get(sn, 'defaultexcluded')
                o.namespaces = []
                onss = config.get(sn, 'namespaces').split("|")
                for ns in onss:
                    n = _blank_()
                    o.namespaces.append(n)
                    pts = ns.split("=",1)
                    n.label = pts[0]
                    n.match = pts[-1]
        return oconfigs

    def getAnnotationSetConfig(self, config, oconfigs):
        aconfigs = _blank_()
        for sn in config.sections():
            if sn.startswith("AnnotationSet."):
                o = _blank_()
                o.name = sn.split(".",1)[1]
                setattr(aconfigs, o.name, o)
                o.order = config.get(sn, 'order', fallback=100)
                if config.has_option(sn, 'linkurl'):
                    o.linkurl = config.get(sn, 'linkurl')
                if config.has_option(sn, 'batchurl'):
                    o.batchurl = config.get(sn, 'batchurl')
                o.label = config.get(sn, 'name')
                o.file = config.get(sn, 'file')
                oname = config.get(sn, 'ontology')
                o.ontology = getattr(oconfigs, oname)
        return aconfigs

    def parseExcludeArg(self, option, opt_str, value, parser):
        parser.values.exclude.update( self.parseExcludeList(value) )

    def parseQuerySetNameArg(self, option, opt_str, value, parser):
        parser.values.qsnames[-1] = value

    def parseQuerySetColorArg(self, option, opt_str, value, parser):
        c = colors.string_to_rgb(value)
        parser.values.qscolors[-1] = colors.rgb_to_hsv(c[0],c[1],c[2])

    def parseQuerySetArg(self, option, opt_str, value, parser):
        if opt_str == "-f":
            dfltqsname = os.path.basename(value)
            qset = self.parseIdList(self.readFile(value))
        else:
            dfltqsname = "qset%d" % len(parser.values.qsets)
            qset = self.parseIdList(value)
        i=len(parser.values.qsets)
        parser.values.qsets.append(qset)
        parser.values.qsnames.append(dfltqsname)
        parser.values.qscolors.append(None)

    def parseUniverseSetArg(self, option, opt_str, value, parser):
        if opt_str == "-U":
            dfltusname = os.path.basename(value)
            uset = self.parseIdList(self.readFile(value))
        else:
            dfltusname = "specified by user"
            uset = self.parseIdList(value)
        parser.values.uset = uset
        parser.values.usname = dfltusname

    def parseIdList(self, idString):
        return [_f for _f in re.split(r'[^a-zA-Z0-9_:.-]+', idString) if _f]

    def parseExcludeList(self, value):
        return [_f for _f in re.split( r'\W+', value.upper() ) if _f]

    def readFile(self, fname):
        fd = open(fname, 'U')
        results = fd.read()
        fd.close()
        return results

    def resolveQsets(self):
        '''
        Resolves each of the user's query sets. A user's query set may include
        id's, symbols, duplicates, and invalid labels. Resolving a query set finds
        (and returns) the set of unique, valid ids represented as well as the labels
        that were not found. Note that this is relative to a specific AnnotationSet.
        For example, an id may be a valid id, but if that object has no annotations,
        the id will still be returned as "not found".
        '''
        self.qsets = []
        self.qsNotFound = []
        for i,qs in enumerate(self.options.qsets):
            (rids, nfids) = self.annotations.resolve(qs)
            self.qsets.append(rids)
            self.qsNotFound.append(nfids)

    def resolveUset(self):
        '''
        Resolves the ids/symbols in a user-specified universe set.
        '''
        self.uset, self.usetnotfound = self.annotations.resolve( self.options.uset )

    def output(self):
        for fname in self.options.outputfiles:
            ResultsWriter.write(self, fname, self.results, self.summary)

    def summarize(self):
        #
        odate = self.ontology.getAttribute("date")
        try:
            odate = time.asctime(time.strptime(odate, '%d:%m:%Y %H:%M'))
        except ValueError:
            pass
        #
        adate = self.annotations.getAttribute("Submission Date")
        try:
            adate = time.asctime(time.strptime(adate, '%m/%d/%Y'))
        except ValueError:
            pass
        #
        excluded = ','.join(self.options.exclude)
        if excluded == '':
            excluded = '(none - all codes included)'

        # Reports QS summary data.
        qsval = []
        for i,qsn in enumerate( self.options.qsnames ):
            qsz = len(self.qsets[i])
            qnfz = len(self.qsNotFound[i])
            qsval.append( ("Query set %d"%(i+1), "%s (n=%d; %d not found)"%(qsn, qsz, qnfz) ) )

        self.summary = [
            ("Vlad version", 'v%s'%VERSION),
            ("Date", time.asctime(time.localtime(self.starttime))),
            ("Run time", '%1.2f sec'%(self.endtime-self.starttime)),
            ("Ontology file", os.path.basename(self.options.ontologyfile)),
            ("Ontology date", odate),
            ("Annotation file", os.path.basename(self.options.annotationfile)),
            ("Annotation date", adate),
            ("Analysis type", self.options.analysis),
            ("Excluded evidence codes", excluded),
            ("Number of query sets", str(len(self.qsets))),
            ] + qsval

        if len(self.uset) > 0:
            self.summary.append( ("Universe set", "%s; size=%d"%(self.options.usname,len(self.uset))))
        else:
            self.summary.append( ("Universe set", "default (everything)"))

    def analyze(self):
        self.ontology = Ontology.load( 
                self.options.ontologyfile, cullObsolete=True, loadMinimal=True, config=self.options.ontologyconfig)
        self.annotations = Annotation.load( self.options.annotationfile, config=self.options.annotationconfig )
        self.resolveQsets()
        self.resolveUset()
        self.notfound, self.results, self.term2results = Analyzer.analyze(
                self.qsets, self.options.qsnames, self.uset, self.ontology, self.annotations,
                self.options.exclude, self.options.analysis)
        # check for no results in each namespace and remove before output
        for ns,rslts in list(self.results.items()):
          if len(rslts) == 0:
            del self.results[ns]

    def addMessage(self, msg, type="info"):
        self.messages.append((type,msg))

    def getMessages(self, clear=True):
        rv = "".join(
          ['<div class="message %s-message">%s</div>' % (m[0],m[1]) for m in self.messages])
        if clear:
            self.messages = []
        return rv

    def go(self, args):
        self.starttime = time.time()
        self.messages = []
        self.parseArgs(args)
        self.analyze()
        self.endtime = time.time()
        self.summarize()
        self.output()

#-------------------------------------------------------------------

class TempFileCleaner(object):
    def __init__(self, dir, age):
        self.dir = dir # directory to be purged
        self.age = age # max age; anything older will be removed

    def _ageCheck_(self, path):
        statinfo = os.stat(path)
        age = time.time() - statinfo.st_mtime
        return age > self.age
        
    def go(self):
        for sdRoot, sdSubdirs, sdFiles in os.walk(self.dir, topdown=False):
            for f in sdFiles:
                path = os.path.join(sdRoot,f)
                if os.access(path, os.W_OK) and self._ageCheck_(path):
                    os.remove(path)
            for d in sdSubdirs:
                path = os.path.join(sdRoot,d)
                if os.access(path, os.W_OK) and len(os.listdir(path)) == 0:
                    os.rmdir(path)
        

#-------------------------------------------------------------------

class VladCGI(Vlad):
    '''
    A subclass of Vlad specialized for running as a CGI. 
    Features:
        (1) Argument parser errors are caught and reported via cgitb module.
        (2) Always outputs html format (to stdout).
        (3) Also writes .xls spreadsheet to a temp file, and adds link to the html output.
        (4) Removes old temp files (older than self.options.maxage)
    '''
    class ParameterError(RuntimeError):
        pass

    class CGIArgParser(optparse.OptionParser):
        '''
        Subclass of OptionParser that raises our ParameterError class
        rather than calling sys.exit() in the event of a parameter error.
        '''
        def error(self, msg):
            raise VladCGI.ParameterError(msg)

    def parseGCutoffValue(self, value):
        try:
            if value is None or value.lower() == "none":
                return "none"
            elif value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
                return int(value)
            else:
                return float(value)
        except:
            raise RuntimeError("cutoff must be a number or 'none'")

    def parseGCutoffArg(self, option, opt_str, value, parser):
        setattr(parser.values, option.dest, self.parseGCutoffValue(value))

    def parseGMaxImgSizeValue(self, value):
        if value is None:
            return None
        vals = list(map(float,value.replace(","," ").replace("x"," ").split()))
        if len(vals) == 0:
            return None
        if len(vals) == 1:
            vals.append(vals[0])
        if len(vals) > 2:
            raise RuntimeError("Bad value for max image size: " + value)
        return "%s,%s" % tuple(vals)

    def parseGMaxImgSizeArg(self, option, opt_str, value, parser):
        setattr(parser.values, option.dest, self.parseGMaxImgSizeValue(value))
        try:
            setattr(parser.values, option.dest, self.parseGMaxImgSizeValue(value))
        except:
            raise optparse.OptionValueError("--gMaxImgSize: bad value: " + str(value))

    def initArgParser(self):
        '''
        Override. Cause arg parser to be our CGIArgParser class.
        '''
        #
        Vlad.initArgParser(self, VladCGI.CGIArgParser)
        #

        self.optParser.add_option(
            "-D",
            "--outputDir", 
            dest="outputdir", 
            help="Output directory." )

        self.optParser.add_option(
            "--cleanTempFiles", 
            action="store_true",
            default=False,
            dest="cleanTempFiles", 
            help="Output directory." )

        self.optParser.add_option(
            "-A",
            "--maxAge",
            dest="maxage",
            type="int",
            help="Maximum age (in days) before temp files are removed.")

        self.optParser.add_option(
            "--tExcel", 
            dest="tExcel", 
            default=False,
            action="store_true",
            help="Generate spreadsheet (.xlsx) output.")

        self.optParser.add_option(
            "--tHtml", 
            dest="tHtml", 
            default=False,
            action="store_true",
            help="Generate HTML table output.")

        self.optParser.add_option(
            "--tText", 
            dest="tText", 
            default=False,
            action="store_true",
            help="Generate text table output.")

        self.optParser.add_option(
            "--gEnable", 
            dest="gEnable", 
            default=True,
            action="store_true",
            help="Generate graphical output. (the default)")

        self.optParser.add_option(
            "--gDisable", 
            dest="gEnable", 
            default=True,
            action="store_false",
            help="Don't generate graphical output.")

        self.optParser.add_option(
            "--gLabelEnable", 
            dest="gLabelEnable", 
            default=True,
            action="store_true",
            help="Draw term names on the nodes. (the default)")

        self.optParser.add_option(
            "--gLabelDisable", 
            dest="gLabelEnable", 
            default=True,
            action="store_false",
            help="Don't draw term names on the nodes.")

        self.optParser.add_option(
            "--gROI", 
            dest="gROI", 
            default=[],
            metavar="IDS",
            action="callback",
            type="string",
            callback=self.parseROIArg,
            help="Region of interest for graphical output. If specified, generates graphical " + \
                "output only for regions the ontology at or below the specified IDs.")

        self.optParser.add_option(
            "--gBackground", 
            dest="gBackground", 
            default="white",
            metavar="COLOR",
            help="Specifies a color for the graph background. (default=white)")

        self.optParser.add_option(
            "--gNodeColor", 
            dest="gNodeColor", 
            default="gray",
            metavar="COLOR",
            help="Specifies a color for nodes. (default=gray)")

        self.optParser.add_option(
            "--gCutoff", 
            dest="gCutoff",
            default=10,
            action="callback",
            callback=self.parseGCutoffArg,
            type="string",
            metavar="CUTOFF", 
            help="Cutoff value. Specify integer for top n results" + \
                 " or float for P-value cutoff. E.g. '--gc 10' keeps only top ten results." + \
                 " '--gc 1e-4' keeps results where P <= 0.0001." )

        self.optParser.add_option(
            "--gCull", 
            dest="gCull", 
            default=False,
            action="store_true",
            help="Cull interior nodes (heuristic).")

        self.optParser.add_option(
            "--gIncAncestors", 
            default=True,
            action="store_true",
            help="Include ancestors of nodes meeting cutoff (the default).")

        self.optParser.add_option(
            "--gNoIncAncestors", 
            default=True,
            dest="gIncAncestors",
            action="store_false",
            help="Do not include ancestors of nodes meeting cutoff.")

        self.optParser.add_option(
            "--gMaxImgSize", 
            dest="gMaxImgSize",
            type="string",
            default="",
            metavar="W,H", 
            action="callback",
            callback=self.parseGMaxImgSizeArg,
            help="If specified, limits the max image size. Generated images will be " + \
                " scaled down if necessary." + \
                " Value is width and height, separated by comma, or a single " + \
                " value that is used for both width and height. Units are inches. ")

    def parseROIArg(self, option, opt_str, value, parser):
        parser.values.gROI = self.parseIdList(value)

    def parseBackgroundColorArg(self, option, opt_str, value, parser):
        c = colors.string_to_rgb(value)
        parser.values.gBackground = colors.rgb_to_hsv(c[0],c[1],c[2])

    def mkdtemp(self, suffix='', prefix=''):
        '''
        Creates a temporary directory for this run. Output files will be created
        in this directory. Returns a tuple containing the full path of the new
        temp dir, and a url equivalent of that dir. 
        '''
        tdir = tempfile.mkdtemp(suffix, prefix, self.options.outputdir)
        sep = (not self.options.outputdirurl.endswith("/") and "/" or "")
        turl = self.options.outputdirurl + sep + os.path.basename(tdir)
        return (tdir, turl)

    def getFileUrl(self, path):
        if path.startswith(self.options.outputdir):
            return path.replace(self.options.outputdir, self.options.outputdirurl, 1)
        else:
            return None

    def fixClientSideImageMap(self, fname, ns):
        '''
        Reads a file containing a server side image map and rewrites
        it as a client side image map.
        Using DOT's builtin client side image map, you don't get to customize,
        e.g., to add onclick hooks. So instead, we first write the server
        side map (which is easy to parse), and then call this routine to convert it.
        Server side format:
            rect http://some.where.org/ 128,200 150,170
        Client side format:
            <area shape="rect" href="http://some.where.org/" coords="128,200,150,170" ETC />
        where "ETC" is whatever else we want to add. In this case, we add alt/title attrs
        so the user gets a popup over each node. Also add onclick handler: nodeClicked().
        '''
        idsInMap = set()
        fd = open(fname, 'U')
        areas = []
        for line in fd:
            tokens = line[:-1].split()
            if len(tokens) == 4 and tokens[0] == "rect":
                href = tokens[1]
                tid = href[1:] # the hrefs look like "#GO:012345"
                idsInMap.add(tid);
                coords = tokens[2]+','+tokens[3]
                term = self.ontology.getTerm(tid)
                rr = self.term2results[ns].get(term,None)
                if rr:
                    if self.options.analysis == "percentage":
                        p = rr[0].maxpval
                        tiptext = "%s %s (%1.0f%%)"%(term.id, term.name, 100*p)
                    else:
                        p = rr[0].minpval
                        tiptext = "%s %s (%0.2e)"%(term.id,term.name,p)
                else:
                    tiptext = "%s %s"%(term.id,term.name)
                areas.append(('<area id="area_%s" shape="rect" href="%s" coords="%s" ' + \
                        ' alt="%s" title="%s" onclick="return nodeClicked(this,event);" />') \
                             % (tid, href, coords, tiptext, tiptext))
        fd.close()
        mapbody = '\n'.join(areas)
        mapname = "map_"+ns
        reslt = '<map name="%s">\n%s\n</map>\n' % (mapname, mapbody)
        ofd = open(fname, 'w')
        ofd.write(reslt)
        ofd.close()
        return idsInMap;
                
    def cleanTempFiles(self):
        TempFileCleaner(self.options.outputdir, self.options.maxage).go()

    def generateGraphicalOutput(self):
        # if user specified a region of interest, first
        # generate the set of nodes within the region.
        self.gROI = set()
        if self.options.gROI:
            # convert ids into terms
            snodes = []
            msgs = []
            for id in self.options.gROI:
                if self.ontology.hasTerm(id):
                    t = self.ontology.getTerm(id)
                    snodes.append(t)
                    msgs.append("%s (%s)" % (t.name, t.id))
                else:
                    msgs.append("?id not found: %s" % id)

            # get the descendents
            self.ontology.traverse( 
               startNodes=snodes,
               beforeEdge=lambda g,p,c,d,h: d in ["is_a","part_of"],
               beforeNode=lambda g,n,p: self.gROI.add(n))

            self.summary.append( ("Graph region of interest", "<br>".join(msgs)) )

        # Generate the dot files, image files, and imagemap files.
        dw = ResultsWriter.DOTWriter(self, 
            roi=self.gROI,
            cutoff=self.options.gCutoff,
            includeAncestors = self.options.gIncAncestors,
            maxImgSize = self.options.gMaxImgSize,
            additional=[("png","png"),("imap","map"),("eps","eps")])
        dw.write(os.path.join(self.myauxdir,"vlad.results.dot"), self.results, self.summary)

        # HACK: parse the names of files written by the DOTWriter. Build
        # a dict that maps namespace name (e.g., 'biological_process') to a
        # pair, [imagefile,imapfile], where imagefile is a complete path to
        # an image file and imapfile is a complete path to an image map file
        # that goes with the image. imapfile may be None.
        ns2img = {}
        for n in dw.filesWritten:
            fn = os.path.basename(n)
            if fn.startswith("vlad.results."):
                fnparts = fn.split(".")
                # assume the namespace name might contain "."
                ns = ".".join(fnparts[2:-1])
                ext = fnparts[-1]
                nsImg = ns2img.setdefault(ns, [None,None])
                if ext == "png":
                    nsImg[0] = n
                elif ext == "map":
                    nsImg[1] = n

        # "fix" each image map file. (See method comments.)
        for (ns, [ifile, mfile]) in list(ns2img.items()):
            if mfile:
                idsInMap = self.fixClientSideImageMap(mfile, ns)
                ns2img[ns][1] = [mfile,idsInMap]

        # generate a "cutoff" summary message
        if type(self.options.gCutoff) is int:
            if self.options.gCutoff > 0:
                coff = "Top %d scoring terms" % self.options.gCutoff
            else:
                coff = "Top %d local maximum terms" % -self.options.gCutoff
        elif self.options.analysis == "percentage":
            coff = "Terms with max percentage > %1.3g" % self.options.gCutoff
        else:
            coff = "Terms with min Pval <= %1.3g" % self.options.gCutoff

        if self.options.gIncAncestors:
            coff += " and their ancestors"
        coff += "."
        if self.options.gCull:
            coff += "<BR/>Interior nodes have been culled."
        self.summary.append( ("Graph display", coff) )    
        #
        return ns2img

    def generateText(self):
        tw = ResultsWriter.TextWriter(self)
        tw.write(os.path.join(self.mydir,"results.tsv"), self.results, self.summary)

    def generateExcel(self):
        xw = ResultsWriter.ExcelWriter(self)
        try:
            xw.write(os.path.join(self.mydir,"results.xlsx"), self.results, self.summary)
        except:
            self.addMessage("Error while generating spreadsheet. Excel file not written.","error")

    def generateHtml(self, images, imgurlroot):
        # generate the html file
        hw = ResultsWriter.HTMLWriter(self)
        hw.write(os.path.join(self.mydir,"results.html"), 
                 self.results, self.summary, images, imgurlroot)
        # copy the vlad logo image
        lf = os.path.join(self.options.staticdir,self.options.logofile)
        cmd = 'cp %s %s' % (lf, self.myauxdir)
        os.system(cmd)
        # copy the little green ball icon
        lf = os.path.join(self.options.staticdir,"ball.gif")
        cmd = 'cp %s %s' % (lf, self.myauxdir)
        os.system(cmd)
        # copy the edge-types legend
        lf = os.path.join(self.options.staticdir,"legend.gif")
        cmd = 'cp %s %s' % (lf, self.myauxdir)
        os.system(cmd)


    def zipCommand(self):
        dir = self.mydir
        pdir,based = os.path.split(dir)
        zfname = "%s.zip"%based
        cmd = 'cd %s; zip -q -r %s %s; mv %s %s' % (pdir, zfname, based, zfname, based)
        zfurl = "%s/%s.zip"%(self.myurl,based)
        return (cmd,zfname,zfurl)

    def output(self):
        '''
        Overrides Vlad.output(). For a cgi, we output a standard set of files
        and write a "Your results are ready" message to stdout.
        '''

        # Poor-man's cleanup strategy... Each time we run, check for old temp files from
        # prior runs, and remove them if they're more then some (24 hrs) age. See 'maxAge'
        # config setting.
        if self.options.cleanTempFiles:
            self.cleanTempFiles()

        # create my own temp directory
        prefix = "VLAD.%s." % re.sub( "[^-a-zA-Z0-9_]","_",self.options.runname)
        (self.mydir,self.myurl) = self.mkdtemp(suffix='', prefix=prefix)
        # add a subdirectory "auxfiles"
        self.myauxdir = os.path.join(self.mydir,"auxfiles")
        self.myauxurl = "auxfiles"
        os.mkdir(self.myauxdir)

        # get the comand to create the zip, plus filename and url
        (zc, zfn, zfu) = self.zipCommand()

        # create the output files
        images = {}
        if self.options.gEnable:
            images = self.generateGraphicalOutput()
        if self.options.tExcel:
            self.generateExcel()
        if self.options.tText:
            self.generateText()
        self.generateHtml(images, self.myauxurl)

        # actually create the zip file
        os.system(zc)

        gendate=time.asctime(time.localtime(self.endtime))
        maxaged = self.options.maxage / (3600*24.0)
        exdate = time.asctime(time.localtime(self.endtime+self.options.maxage))

        lbl = self.options.runname
        viewLink = ResultsWriter.makeLink("View", "%s/results.html"%self.myurl, zfn)
        downloadLink = ResultsWriter.makeLink("Save", zfu)
        discardLink = '<a href="#" onclick="discardResults(this); ' + \
            ' return false;">Discard</a>'

        # total elapsed time
        elapsedtime = time.time() - self.starttime

        # and here is Vlad's output...!
        print('''
        %s <font size="-2">(%s | %s | %s)<br/>
        %s <br/> Generated: %s; Expires: %s;
        %s
        </font>
        '''%(lbl, viewLink, downloadLink, discardLink, zfn, gendate, exdate, self.getMessages()))

#-------------------------------------------------------------------
class _blank_(object):
    pass
#-------------------------------------------------------------------

if __name__ == "__main__":
    VladCGI().go(sys.argv)
