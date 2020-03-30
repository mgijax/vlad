#
# ResultsWriter.py
#
# Defines the ResultsWriter interface along with 
# several concrete implementations. A ResultsWriter provides the
# following method:
#       write(fname, results, summary)
# where:
#    fname = name of the file to write, or an open file object.
#    results = mapping from namespace name to list of analysis results objects
#    summary = list of name,value pairs. The meta info for the analysis run.
# Usage:
#       rw = ResultsWriter.getImpl("dot")
#       rw().write("foo.dot", myResults, mySummary)
#

#-------------------------------------------------------------------
# std Python libs
import sys
import types
import os
import urllib.parse

# Vlad libs
from . import DAG
from . import GraphvizTools
from . import Stylist
from . import colors

# 3rd party libs
from . import xlsxwriter

#-------------------------------------------------------------------
COMMA   =       ','
PIPE    =       '|'

COLUMNLEGEND='TermID:ID of the ontology term.|Term:The text of the term.|Term Min P:The smallest P-val for any query set for this term.|Term Max P:The largest P-val for any query set for this term.|Term P ratio:Term Min P divided by Term Max P.|P:P value (significance score) for this query set for this ontology term.|Q:The False Discovery Rate (FDR) statistic.|k:The number of objects in the query set annotated to this term (or a descendant).|n:The size of the query set.|K:The number of objects in the database annotated to this term (or a descendant).|N:Number of annotated objects in the database.|k/n:Percent of query set objects annotated to this term (or a descendant).|K/N:Percent of database objects annotated to this term (or a descendant).|k/K:Percent of all objects annotated to this term present in the query set.|n/N:Percent of database in the query set.|Qset:The name of the query set.|Symbols:The symbols query set objects annotated to this term (or a descendant).'
#-------------------------------------------------------------------

IMPLS = {}

def __addImpl__(cls):
    for ext in cls.extensions:
        IMPLS[ext] = cls

def getImpl(extension):
    return IMPLS.get(extension, TextWriter)

def write(vlad, fname, results, summary):
    ext = os.path.splitext(fname)[-1][1:]
    rw = getImpl(ext)
    rw(vlad).write(fname, results, summary)

#-------------------------------------------------------------------
def makeLink(label, url, target="_self"):
    return '<a href="%s" target="%s">%s</a>'%(url,target,label)

#-------------------------------------------------------------------
class ResultsWriter(object):
    extensions = []
    def __init__(self, vlad):
        self.vlad = vlad
        self.cfgParser = vlad.cfgParser
        self.javascriptPart = None
        self.formPart = None
        self.batchUrl = False
        self.urlMap = {}
        self.columnLegend = None
        self.filesWritten = []
        self.getConfig(self.cfgParser)

    def write(self, fname, results, summary):
        self.filesWritten = []
        self.fname = fname
        self.results = results
        self.summary = summary
        self._writeFile_()

    def getExtensions(self):
        return self.extensions

    def openOutputFile(self, fname):
        self.filesWritten.append(fname)
        if self.fname == "-":
            ofd = sys.stdout
        elif type(fname) is str:
            ofd = open(fname, 'w')
        elif hasattr(fname, "write") and callable(getattr(fname, "write")):
            ofd = fname
        else:
            raise RuntimeError("Could not open file:" + str(fname))
        return ofd


    def getConfig(self, cfgParser):
        self.columnLegend = [x.split(":") for x in COLUMNLEGEND.split("|")]
        self.colName2Legend = {}
        for n,v in self.columnLegend:
            self.colName2Legend[n]=v
        self.registerBatchUrl()

    def closeFile(self, fp):
        if fp is not sys.stdout:
            fp.close()

    def parseUrl(self, url):
        '''
        Parses a url into its components, using urlparse.urlsplit().
        Further splits the query portion into a list of (name,value) strings.
        Returns a tuple containing the components from urlsplit() and
        the list of arg tuples.
        '''
        parts = urllib.parse.urlsplit(url)
        args = []
        for arg in parts[3].split('&'): # split query part
            if '=' in arg:
                args.append(arg.split('='))
        return (parts, args)

    def registerBatchUrl(self):
        self.batchUrl = getattr( \
            self.vlad.annotations.config, 'batchurl', '')
        components, args = self.parseUrl(self.batchUrl)
        formid = "_batch_link_form_"
        idlistParamName = "x"
        for n,v in args:
            if "%s" in v:
                idlistParamName = n
                break
        self.javascriptPart = JAVASCRIPT_TMPLT % (formid, idlistParamName)

        inputs = []
        for n,v in args:
            inputs.append( HTML_FORM_INPUT_TMPLT % (n,v) )
        inputs = "".join(inputs)
        #
        actionurl = "%s://%s%s"%(components[0],components[1],components[2])
        self.formPart = HTML_FORM_TMPLT % (formid,actionurl,inputs)

    def makeLink(self, label, url, target="_self"):
        return makeLink(label,url,target)

    def getTermLink(self, term, labelfield="id", target="_blank"):
        url = term.getUrl()
        label = getattr(term, labelfield)
        if url:
            return self.makeLink( label, url, target )
        else:
            return label

    def getDbObjUrl(self, dbobj):
        tmplt = getattr(self.vlad.annotations.config, 'linkurl', None)
        if tmplt is None:
            tmplt = self.urlMap.get(dbobj.getDb(), None)
        if tmplt:
            return tmplt % dbobj.getId()
        else:
            return None

    def getDbObjLink(self, dbobj, target="_blank"):
        url = self.getDbObjUrl(dbobj)
        label = dbobj.getSymbol()
        if url:
            return self.makeLink( label, url, target )
        else:
            return label

    def getBatchLink(self, dbobjs, target="_blank"):
        if len(dbobjs) == 0:
            return None
        if self.batchUrl:
            idlist = ' '.join([x.getId() for x in dbobjs])
            label = ", ".join( [x.getSymbol() for x in dbobjs])
            return HTML_BATCH_LINK_TMPLT % (idlist, label)
        else:
            return None

    def getHeaderLabels(self):
        return self.checkRow([x[0] for x in self.columnLegend])

    def checkRow(self, row):
        '''
        UGLY HACK: if there's only one query set, remove the columns that pertain
        to multiple qsets.
        If analysis type is percentages, don't show Q column.
        '''
        if len(self.vlad.qsets) == 1:
            del row[2:5]
            if self.vlad.options.analysis == "percentage":
                del row[3]
        elif self.vlad.options.analysis == "percentage":
            del row[6]
        return row

    def result2list(self, result, format='text'):
        '''
        Convert result object to a list for output.
        '''
        dbobjs = result.aList
        if format == 'html':
            id = self.getTermLink( result.term )
            symbols = self.getBatchLink( dbobjs )
            if symbols is None:
                symbols = COMMA.join(map(self.getDbObjLink, dbobjs))
            if not symbols:
                symbols = "&nbsp;"
        else:
            id = result.term.id
            symbols = COMMA.join([x.getSymbol() for x in dbobjs])
        qid = result.qsid
        qcolor = self.vlad.options.qsid2color[qid]
        p = result.pval
        q = result.qval
        minp = result.minpval
        maxp = result.maxpval
        pratio = minp/maxp
        k = result.k
        n = result.n
        K = result.K
        N = result.N
        kn = float(k)/n
        KN = float(K)/N
        kK = float(k)/K
        nN = float(n)/N
        if format in ['html', 'text']:
            qid = str(qid)
            minp = "%0.2e"%minp
            maxp = "%0.2e"%maxp
            p = "%0.2e"%p
            q = "%0.2e"%q
            if format== 'html' and len(self.vlad.qsets) > 1:
                c = colors.rgb_to_string(colors.hsv_to_rgb(qcolor))
                qid = ('<span><span style="background-color:%s;border:thin solid black;">' + \
                      '&nbsp;&nbsp;</span>&nbsp;%s</span>') % (c,qid)
            pratio = "%0.2e"%pratio
            k = str(k)
            n = str(n)
            K = str(K)
            N = str(N)
            kn = "%1.2f%%"%(100*kn)
            KN = "%1.2f%%"%(100*KN)
            kK = "%1.2f%%"%(100*kK)
            nN = "%1.2f%%"%(100*nN)
        return self.checkRow([
            id,
            result.term.name,
            minp,
            maxp,
            pratio,
            p,
            q,
            k,
            n,
            K,
            N,
            kn,
            KN,
            kK,
            nN,
            qid,
            symbols,
            ])

__addImpl__(ResultsWriter)

#-------------------------------------------------------------------

class HTMLWriter(ResultsWriter):

    extensions =  ["html", "htm"]

    def writeHtmlRow(self, lst, fp, trTag='tr', tdTags='td', rowspan = None ):
        '''
        Write result to an HTML file as a row in a table.
        '''
        trEndTag = trTag.split()[0]

        if type(tdTags) is str:
            tdTags = [ tdTags ] * len(lst)
        tdEndTags = [x.split()[0] for x in tdTags]

        if rowspan is None:
            pts = []
            for i,v in enumerate(lst):
                tdTag = tdTags[i]
                tdEndTag = tdEndTags[i]
                pts.append( '<%s>%s</%s>' % (tdTag, v, tdEndTag))
            fp.write( '<%s>%s</%s>' % (trTag, ''.join(pts), trEndTag))
        else:
            cells = []
            for i,v in enumerate(lst):
                tdTag = tdTags[i]
                tdEndTag = tdEndTags[i]
                if i >= len(rowspan):
                    rs = 1
                else:
                    rs = rowspan[i]
                if rs == 0:
                    continue
                elif rs == 1:
                    cells.append('<%s>%s</%s>' % (tdTag, v, tdEndTag) )
                else:
                    cells.append('<%s rowspan="%d">%s</%s>'% (tdTag, rs, v, tdEndTag) )
            fp.write('<%s>%s</%s>' % (trTag, ''.join(cells), trEndTag))

    def getColumnLegendHtml(self):
        if self.columnLegend is None:
            return ''
        else:
            content = "".join(
                ["<dt>%s</dt><dd>%s</dd>"%(x[0],x[1]) for x in self.columnLegend])
            html = '<div id="columnLegend"><div>Column Descriptions</div><dl>%s</dl></div>\n' % content
            return html

    def getClientSideImageMap(self, fname):
        fd = open(fname, 'U')
        imap = fd.read()
        fd.close()
        return imap

    def writeHtmlSummary(self, fp):
        fp.write('<h1><img src="%s" align="middle" />' \
            % (self.imgurlroot+"/vlad_logo.gif") )
        fp.write('<a name="top">%s</a></h1>\n' \
            % self.vlad.options.runname)
        fp.write('<table class="summary" cellspacing="0">')
        for lbl,val in self.summary:
            fp.write('<tr><td class="label">%s:</td><td>%s</td></tr>'%(lbl,val))
        fp.write('</table>\n')

    def _writeHtmlTable_(self, fp, ns, idsInMap):
        # write the results table for this namespace
        fp.write('<div class="results">')
        fp.write('<table border="0" cellspacing="0" cellpadding="2" class="results">')
        #
        tdTags = []
        hdrlbls = self.getHeaderLabels()
        for hl in hdrlbls:
            lgnd = self.colName2Legend.get(hl, None)
            xtra = ''
            if lgnd:
                xtra = 'alt="%s" title="%s"' % (lgnd,lgnd)
            tdTags.append( 'th class="label" %s'%xtra )
        self.writeHtmlRow( hdrlbls, fp, tdTags=tdTags )
        #
        nsresults = self.results[ns]
        rowClasses = ["zlight", "zdark"]
        nrc = len(rowClasses)
        irc = 0
        lastTerm = None
        for (i,r) in enumerate(nsresults):
            rowidattr = ''
            if r.term != lastTerm:
                irc = (irc+1) % nrc
                rowspan = None
                j = i+1
                while j < len(nsresults):
                    if nsresults[j].term is not r.term:
                        break
                    j += 1
                rowidattr = 'id="%s"'%r.term.id
                rowspan = [j-i]*5
            else:
                rowspan = [0]*5
            rowClass = rowClasses[irc]
            rowvals = self.result2list(r,'html')
            #
            if idsInMap and r.term.id in idsInMap:
                imgLink = \
                  ('<a href="#" onclick="hilightNode(\'%s\'); return false;">' \
                  + '<img border="0" src="%s" /></a>') \
                  % (r.term.id,self.imgurlroot+"/ball.gif")
                rowvals[0] = imgLink + '&nbsp;' + rowvals[0]
            #
            tdTags = ['td']*len(rowvals)
            tdTags[-1] = 'td class="termlinks"'
            self.writeHtmlRow(rowvals, fp, 
                    trTag='tr class="%s" %s'%(rowClass,rowidattr), 
                    tdTags = tdTags,
                    rowspan=rowspan )
            lastTerm = r.term
        fp.write('</table>')
        fp.write('</div>')

    def _writeFile_(self):
        fp = self.openOutputFile(self.fname)
        nss = list(self.results.keys())
        nss.sort()

        fp.write("<html>")
        fp.write("<head>")
        fp.write(CSSSTYLE)
        if self.javascriptPart:
            fp.write(self.javascriptPart)
        fp.write("</head>")
        fp.write("<body>")
        if self.formPart:
            fp.write(self.formPart)
        self.writeHtmlSummary(fp)
        links = list(map(self.makeLink, nss, ['#'+x for x in nss]))
        links.append( self.makeLink( "Unannotated id/symbols", "#__unannotated__" ))
        links = " | ".join(links)
        fp.write('<b>Jump to:</b> %s<p>'%links)

        for ns in nss:
            # add a section for each namespace
            fp.write('<h3><a name="%s">%s</a> (<a href="#top">top</a>)</h3>'%(ns,ns))
            if len(self.results[ns]) == 0:
                continue

            # add image and clientside image map to section, if available
            imgfile, (imapfile,idsInMap) = self.ns2img.get(ns, [None,[None,None]])
            if imgfile:
                imgurl = self.imgurlroot+"/"+os.path.basename(imgfile) # use relative path for url
                imgid = "img_"+ns
                mapname = "map_"+ns
                imgtag = '''<img id="%s" src="%s" usemap="#%s" 
                    onclick="showEdgeTypeLegend(event);" />
                    <br/><br/>''' \
                    %(imgid, imgurl, mapname)
                fp.write(imgtag)
                if imapfile:
                    imgmap = self.getClientSideImageMap(imapfile)
                    fp.write(imgmap)
            if self.vlad.options.tHtml:
                self._writeHtmlTable_(fp, ns, idsInMap)

        # report on missing ids
        fp.write('<h3><a name="__unannotated__">Unannotated IDs</a></h3>\n')
        fp.write('<table border="0">\n<tr>\n')
        for i,qsn in enumerate(self.vlad.options.qsnames):
            fp.write('<td><b>%s</b><br/>\n'%qsn)
            qsnf = list(self.vlad.qsNotFound[i])
            qsnf.sort()
            fp.write('<textarea rows="15" cols="18">%s</textarea>\n</td>\n' % ("\n".join(qsnf)))
        fp.write('</table>\n')

        # include the edge legend 
        legendurl = self.imgurlroot+"/legend.gif"
        fp.write('''<span id="edgetypelegend" 
                     class="edgetypelegend"
                     style="left:0;top:0;display:none;" 
                     onclick="hideEdgeTypeLegend();" >
                         <table border="0"><tr>
                         <td style="text-align:left;cursor:pointer;">[close]</td>
                         <td style="text-align:center;"><b>Legend: Edge Types</b></td>
                         <td style="text-align:right;"><a href="http://www.geneontology.org/GO.ontology.relations.shtml" target="_blank">(details)</a></td>
                         </tr>
                         <tr><td colspan="3"><img src="%s" /></td></tr>
                         </table>
                     </span>\n''' % legendurl)

        # all done
        fp.write("</body>")
        fp.write("</html>")
        self.closeFile(fp)

    def write(self, fname, results, summary, images = {}, imgurlroot=""):
        self.ns2img = images
        self.imgurlroot = imgurlroot
        ResultsWriter.write( self, fname, results, summary )

__addImpl__(HTMLWriter)

#-------------------------------------------------------------------
class DOTWriter(ResultsWriter):
    extensions = ['dot']

    def __init__(self, 
        vlad,           # a Vlad instance
        roi=[],         # region of interest; a list of term ids
        cutoff=0.001,   # cutoff val. float, int, or negative int
        includeAncestors=True, # if true, do upward closure
        maxImgSize=None,# max image size (w,h), or None for unlimited
        additional=[]): # additional files to generate by running dot
                        # Each item is a tuple: (format,extension)
                        # For example: ('png','png').
        #
        ResultsWriter.__init__(self, vlad)
        self.roi = roi
        self.cutoff = cutoff
        self.includeAncestors = includeAncestors
        self.additional = additional    # [(fmt,ext)]
        self.maxImgSize = maxImgSize

    def _writeFile1_(self, namespace, nsresults, outputfile):
        fp = self.openOutputFile(outputfile) # a .dot file

        # Generate set of terms that meet the cutoff.
        # If a region of interest was specified, terms must additionally
        # come from within the region.
        terms = set()
        if type(self.cutoff) is int:
            if self.cutoff > 0:
                # keep first N terms
                for r in nsresults:
                    if len(terms) >= self.cutoff :
                        break
                    if self.roi and r.term not in self.roi:
                        continue
                    terms.add(r.term)
            elif self.cutoff < 0:
                # keep the top N local minima (with respect to P val)
                # Gotta find 'em first.
                # (N/A if analysis type === percentages)
                nterms = -self.cutoff
                for r in nsresults:
                    rt = r.term
                    if self.roi and rt not in self.roi:
                        continue
                    # Now check the min P val for the nodes in the family (i.e.,
                    # parents and children) of the current term.
                    family = self.vlad.ontology.getChildren(rt) + self.vlad.ontology.getParents(rt)
                    for n in family:
                        # if the other node has a smaller score or is a
                        # child with an equal score, I'm not a local max.
                        nr = self.vlad.term2results[namespace].get(n,None)
                        if nr \
                        and (nr[0].minpval < r.minpval \
                        or nr[0].minpval == r.minpval \
                        and self.vlad.ontology.isChild(nr[0].term, rt)):
                            # rt is not a local minimum
                            break
                    else:
                        # rt is a local minimum. Add it to our set.
                        terms.add(rt)
                        if len(terms) >= nterms :
                            break
        elif type(self.cutoff) is float:
            for r in nsresults:
                if self.vlad.options.analysis == "percentage":
                    if r.maxpval < self.cutoff :
                        break
                else:
                    if r.minpval >= self.cutoff :
                        break
                if self.roi and r.term not in self.roi:
                    continue
                terms.add(r.term)

        # using these terms as starting points, extract the subgraph 
        # consisting of the specified nodes (top 25 or whatever) and
        # their ancestors.
        sgext = DAG.SubgraphExtracter(inclusive=self.includeAncestors)
        subgr = sgext.go(self.vlad.ontology, startNodes=terms, reversed=True)

        if self.roi:
            # if a ROI was specified, the following pass will remove
            # any ancestors added by previous step that are not also in the ROI.
            subgr = sgext.go(subgr, startNodes=self.roi)

        # now use a Stylist to create a dot graph
        dotgr = Stylist.Stylist().go(namespace, subgr, self.vlad, terms)

        # write the DOT graph to a .dot file
        GraphvizTools.DOTWriter().write(dotgr, fp)
        self.closeFile(fp)

        # run dot over the graph file to generate image and imagemap files
        dotfile=outputfile 
        cgihome = None
        if self.cfgParser.has_option("DOT","cgihome"):
            cgihome = self.cfgParser.get("DOT","cgihome")
        dr = GraphvizTools.DOTRunner( self.cfgParser.get("DOT", "executable"), cgihome )
        dargs = ["-q"]
        if self.maxImgSize:
            dargs.append("-Gsize="+self.maxImgSize)
        for fmt,ext in self.additional:
            fn = dotfile[:-3] + ext 
            self.filesWritten.append(fn)
            fmtOverrides = []
            if fmt == "eps":
                fmtOverrides.append("-Nfontname=Helvetica")
            else:
                fmtOverrides.append("-Nfontname=Arial")
            dr.run( dotfile, fn, fmt, dargs+fmtOverrides )

    def _writeFile_(self):
        nss = list(self.results.keys())
        nss.sort()
        for ns in nss:
            nsresults = self.results[ns]
            (hd,tl) = os.path.split(self.fname)
            fnbase,ext = os.path.splitext(tl)
            fn = os.path.join(hd, fnbase+"."+ns+ext)
            self._writeFile1_(ns, nsresults, fn)

__addImpl__(DOTWriter)

#-------------------------------------------------------------------

class TextWriter(ResultsWriter):

    extensions = ['txt']

    def writeTabDelimitedRow(self, lst, fp, sep='\t', nl='\n'):
        '''
        Write result to a TAB-delimited file.
        '''
        fp.write(sep.join(lst) + nl)

    def _writeFile_(self):
        fp = self.openOutputFile(self.fname)
        fp.write('# %s\n' % self.vlad.options.runname)
        for lbl,val in self.summary:
            fp.write('# %s = %s\n'%(lbl,val))
        nss = list(self.results.keys())
        nss.sort()
        self.writeTabDelimitedRow( ['Namespace'] + self.getHeaderLabels(), fp)
        for ns in nss:
            # add a section for each namespace
            nsresults = self.results[ns]
            for (i,r) in enumerate(nsresults):
                self.writeTabDelimitedRow([ns]+self.result2list(r,'text'), fp)
        self.closeFile(fp)

__addImpl__(TextWriter)

#-------------------------------------------------------------------

class ExcelWriter(ResultsWriter):
    extensions = ['xls','xlsx']

    def getWorksheetRowStyles(self):
        return self.checkRow([
            self.xlsDefaultStyle,
            self.xlsDefaultStyle,
            self.xlsSciStyle,
            self.xlsSciStyle,
            self.xlsSciStyle,
            self.xlsSciStyle,
            self.xlsSciStyle,
            self.xlsDefaultStyle,
            self.xlsDefaultStyle,
            self.xlsDefaultStyle,
            self.xlsDefaultStyle,
            self.xlsPercentStyle,
            self.xlsPercentStyle,
            self.xlsPercentStyle,
            self.xlsPercentStyle,
            self.xlsDefaultStyle,
            self.xlsDefaultStyle,
            ])

    def writeWorksheetLink(self, text, url, sheet, row, col):
        sheet.write_url(row, col, url, self.xlsLinkStyle, text)

    def writeWorksheetGenelist(self, dbobjs, sheet, row, col):
        for i, obj in enumerate(dbobjs):
            url = self.getDbObjUrl(obj)
            if url:
                self.writeWorksheetLink( obj.id, url, sheet, row+i, col )
            else:
                sheet.write( row+i, col, obj.id )
            sheet.write(row+i, col+1, obj.symbol)
        
    def writeWorksheetRow(self, lst, sheet, row, col, styles=[]):
        for i,v in enumerate(lst):
            if i < len(styles):
                sheet.write(row, col+i, v, styles[i])
            else:
                sheet.write(row, col+i, v)
        return col+i # return index of last column written

    def writeWorksheetCol(self, lst, sheet, row, col):
        for i,v in enumerate(lst):
            sheet.write(row+i, col, v)
        return row+i # return index of last row written

    def writeExcelQuerySets(self, sheet, row, col):
        for i,qs in enumerate(self.vlad.qsets):
            sheet.merge_range( row, col, row, col+1, self.vlad.options.qsnames[i], self.xlsHeadingStyle )
            dbobjs = self.vlad.annotations.getDbObjects(qs)
            dbobjs.sort(key=lambda x:x.symbol)
            self.writeWorksheetGenelist(dbobjs, sheet, row+1, col)
            col += 3

    def _writeFile_(self):
        self.filesWritten.append(self.fname)
        wb = xlsxwriter.Workbook(self.fname)

        # define styles
        self.xlsDefaultStyle = wb.add_format({})
        self.xlsBoldStyle = wb.add_format({'bold': True})
        self.xlsHeadingStyle = wb.add_format({'bold': True, 'align': 'center'})
        self.xlsLinkStyle = wb.add_format({'font_color' : 'blue' })
        self.xlsPercentStyle = wb.add_format({'num_format' : '0.00%'})
        self.xlsSciStyle = wb.add_format({'num_format' : '0.00E+00'})

        # write summary page
        sheet = wb.add_worksheet("Summary")
        # run name
        a = self.vlad.options.runname
        sheet.merge_range(0, 0, 0, 1, "%s"%a, self.xlsHeadingStyle )
        sheet.set_column(0, 0, 16)
        sheet.set_column(1, 1, 64)
        # run summary attribute/values
        for (i, (lbl,val)) in enumerate(self.summary):
            sheet.write( i+1, 0, lbl )
            sheet.write( i+1, 1, val )

        nss = list(self.results.keys())
        nss.sort()
        i += 2
        sheet.write(i, 0, "Jump to", self.xlsBoldStyle)
        for ns in nss:
            self.writeWorksheetLink(ns, "#%s!A1"%ns, sheet, i, 1)
            i+=1
        if self.columnLegend:
            i += 2
            sheet.merge_range( i, 0, i, 1, "Column Descriptions", self.xlsHeadingStyle )
            for j, (lbl,val) in enumerate(self.columnLegend):
                sheet.write( j+i+1, 0, lbl, self.xlsBoldStyle )
                sheet.write( j+i+1, 1, val )
        #
        # List all the query sets
        self.writeExcelQuerySets(sheet, 0, 3)
        # write results page for each namespace
        rowstyles = self.getWorksheetRowStyles()
        for ns in nss:
            # add a sheet for each namespace
            sheet = wb.add_worksheet(ns)
            nsresults = self.results[ns]
            hlabels = self.getHeaderLabels()
            self.writeWorksheetRow( hlabels, sheet, 0, 0, len(hlabels)*[self.xlsHeadingStyle] )
            sheet.set_column(1, 1, 28)
            for (i,r) in enumerate(nsresults):
                url=None
                if url:
                    rowstyles[-1] = self.xlsLinkStyle
                else:
                    rowstyles[-1] = self.xlsDefaultStyle
                lastcol = self.writeWorksheetRow(self.result2list(r,'xlsx'), sheet, i+1, 0, rowstyles)
                if url:
                    self.writeWorksheetLink( None, url, sheet, i+1, lastcol )
        wb.close()

__addImpl__(ExcelWriter)

#-------------------------------------------------------------------

CSSSTYLE= '''
<style type="text/css">       

    body {        
        background-color: MediumAquaMarine;
    }

    .zdark {
        background-color: #bbbbbb;
    }

    .zlight {
        background-color: #ffffff;
    }

    div.node-hilite {
        position : absolute;
        border : medium solid red;
        display : none;
    }

    div.results {
        width: 95%;
        height: 480;
        overflow: auto;
    }

    table.results {
        border: thin solid black;
    }

    .label { 
        font-weight: bold;
        background-color: #333;
        color: white;
    }

    table.results tr {
    }

    table.results th {
        border-right: thin solid black;
    }

    table.results td {
        border-top: thin solid black;
        border-right: thin solid black;
    }

    table.results td.termlinks {
        white-space: nowrap;
    }

    table.summary {
        white-space:nowrap;
        padding: 0px;
        border-left   : thin solid gray;
        border-bottom : thin solid gray;
    }

    table.summary td {
        border-top : thin solid gray;
        border-right : thin solid gray;
    }

    table.summary td:first-child {
        background-color: #333;
        color: white;
    }

    .edgetypelegend { 
         background-color:gray;
         padding:4px;
         position:absolute;
    }

</style>
'''

JAVASCRIPT_TMPLT = '''
<script language="javascript">
function submitForm(idlist){
    var form = document.getElementById("%s");
    form.%s.value = idlist;
    form.submit();
}
function nodeClicked(areaElt,evt){
    var h = areaElt.href;
    var i = h.lastIndexOf('#');
    if(i == -1)
        return true;
    var goid = h.substring(i+1);
    var e = document.getElementById(goid);
    if(e){
        e.scrollIntoView()
        evt.cancelBubble = true;
        return false;
    }
    return true;
}
function findAreaNode(id){
    return document.getElementById("area_"+id);
}
function findImgForArea(a){
    var map = a.parentNode;
    var mapname = map.name;
    var imgid = "img_"+mapname.slice(4);
    return document.getElementById(imgid);
}
function hilightNode(id){
    var a = findAreaNode(id);
    var d = window.nodeHilightDiv;
    if(a){
        var img = findImgForArea(a);
        if(! img) return;
        var coords = a.coords.split(",");
        var x = parseInt(coords[0]);
        var y = parseInt(coords[1]);
        d.style.left = x + img.offsetLeft;
        d.style.top  = y + img.offsetTop;
        d.style.width = parseInt(coords[2]) - x;
        d.style.height = parseInt(coords[3]) - y;
        d.style.display = "block";
        d.scrollIntoView();
    }
}
function getWindowScroll(){
    if(window.pageXOffset === undefined)
        if(document.body.scrollLeft === undefined)
            return [document.documentElement.scrollLeft,
                    document.documentElement.scrollTop];
        else
            return [document.body.scrollLeft,
                    document.body.scrollTop];
    else 
        return [window.pageXOffset,
                window.pageYOffset];
}

function showEdgeTypeLegend(evt){
    var img = document.getElementById("edgetypelegend");
    if(img){
        var wscroll = getWindowScroll();
        img.style.display = 'block';
        img.style.left = evt.clientX + wscroll[0] + 5;
        img.style.top  = evt.clientY + wscroll[1] + 5;
        if( typeof(evt.stopPropagation) === "function" )
            evt.stopPropagation();
    }
}

function hideEdgeTypeLegend(){
    var img = document.getElementById("edgetypelegend");
    if(img) img.style.display='none';
}

window.onload = function(){
    window.nodeHilightDiv = document.createElement('div');
    document.body.appendChild(window.nodeHilightDiv);
    window.nodeHilightDiv.className = 'node-hilite';
    window.nodeHilightDiv.onclick = function(){ window.nodeHilightDiv.style.display="none"; };
}
</script>
'''     # t % (formid,idlistParamName)

FIREBUGLITE= '''
<script type='text/javascript' 
        src='http://getfirebug.com/releases/lite/1.2/firebug-lite-compressed.js'></script>
'''

HTML_FORM_TMPLT = '''
<form target="_blank" name="_gene_link_form_" id="%s" 
      action="%s"
      method="post" enctype='multipart/form-data'>
      %s
</form>
'''     # t % (formid,actionUrl,forminputs)

HTML_FORM_INPUT_TMPLT = \
'''<input type="hidden" name="%s" value="%s" />
''' # t % (name,value)

HTML_BATCH_LINK_TMPLT = \
'''<a href="#" onclick="submitForm('%s');">%s</a>
''' # t % (idlist,symbollist)
