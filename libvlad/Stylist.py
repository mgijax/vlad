#
# Stylist.py
#
# Classes for building and styling DOTDAGs from analysis results.
#

import math
import types
from . import DAG
from . import GraphvizTools as GVT
from . import colors

class Stylist(object):
    def getNodeSGName(self, node):
        return "/nodes"

    def getEdgeSGName(self, p, c, d):
        if d == "is_a":
            return "/edges/is_a"
        elif d == "part_of":
            return "/edges/part_of"
        elif d == "regulates":
            return "/edges/regulates"
        elif d == "positively_regulates":
            return "/edges/regulates/positive"
        elif d == "negatively_regulates":
            return "/edges/regulates/negative"
        else:
            return "/edges"

    def getSubgraphAttrs(self):
        return self.subgraphAttrs

    def setNodeAttrs(self, n):
        #self.setNodeColor(n)
        self.setNodeSize(n)
        self.setNodeLabel(n)
        self.setNodeLink(n)

    def setNodeLink(self, n):
        self.dotdag.setObjAttr(n, 'URL', '#'+n.id)

    def setNodeSize(self, n):
        #
        if n.is_nsroot:
            self.dotdag.setObjAttr(n, 'shape', "box")
            self.dotdag.setObjAttr(n, 'width', 1.5)
            return
        rslts = self.term2results[self.namespace].get(n,[])
        maxer = 0.0 # max e ratio
        minp  = 1.0 # min p val
        for r in rslts:
            maxer = max(maxer, r.eRatio)
            minp  = min(minp,  r.pval)
        maxdiameter = 1.5 # inches
        mindiameter = 0.1
        #if self.nqsets <= 2:
        if False:
            self.dotdag.setObjAttr(n, 'shape', 'circle')
            maxarea = math.pi * maxdiameter**2 / 4
            minarea = math.pi * mindiameter**2 / 4
            area = minarea + maxer*(maxarea-minarea)
            diameter = 2*math.sqrt(area/math.pi)
        else:
            self.dotdag.setObjAttr(n, 'shape', 'box')
            maxarea = maxdiameter**2
            minarea = mindiameter**2
            area = minarea + maxer*(maxarea-minarea)
            diameter = math.sqrt(area)
        self.dotdag.setObjAttr(n, 'width', diameter)
        self.dotdag.setObjAttr(n, 'height', diameter)

    def typesetLabel(self, n, minlen=8, maxlen=20, NL='<BR/>'):
        tokens = n.name.split()
        label = n.id + NL
        cllen = 0
        lasti = len(tokens)-1
        for (i,t) in enumerate(tokens):
            nlen = cllen + len(t)
            startnewline = (nlen >= maxlen) # and not  (i==lasti and len(t) < minlen)
            if i == 0:
               sep = ''
               cllen = len(t)
            elif startnewline:
               sep = NL
               cllen = len(t)
            else:
               sep = ' '
               cllen += len(t)+1
            label = label + sep + t
        label = label.strip()
        return label


    def setNodeLabel(self, n):
        # if text labels are turned off globally, then the colorbar itself
        # becomes the node. 
        cbarIsNode = not self.vlad.options.gLabelEnable

        dolabel = n.is_nsroot or self.vlad.options.gLabelEnable # do this partic. label?
        dolabel = dolabel and (self.dotdag.getObjAttr(n, 'width') >= 0.50)

        # width in points of the node
        pwidth = 72.0 * self.dotdag.getObjAttr(n, 'width')

        rslts = self.term2results[self.namespace].get(n,[])
        # label
        label = ''
        if dolabel:
            maxlinelen = 20
            label = self.typesetLabel(n, maxlen=maxlinelen)
            # don't set the label in the node yet...

            # Calculate the font size for the label
            maxfontsize = 20.0
            minfontsize = 5.0
            pwchar = 2 * pwidth / maxlinelen 
            fontsize = min(maxfontsize, max(minfontsize, pwchar))
            self.dotdag.setObjAttr(n, 'fontsize', fontsize)


        # color bar
        clrbar = ''
        segs = []
        for r in rslts:
            qsc = self.qsid2color[r.qsid]
            qsc = ' '.join(['%s'%x for x in qsc])
            segs.append( [qsc, r.e] )
        #
        if len(segs) > 0 and self.nqsets > 1:
            if cbarIsNode:
                aspect = 1.0
                tlen = 0.92*pwidth
            else:
                aspect = 0.15
                tlen = 0.85*pwidth
            clrbar = self.mkColorBar(segs, totallength=tlen, aspect=aspect)

        # stats line
        stats = ''
        if dolabel and not n.is_nsroot:
            K=0 # K = #genes annotated to this node in the database
            if self.nqsets == 1:
                # for a single query set, just display the stats as two lines of text: p, then k and K.
                stats = 'p=%0.1E<BR/>k=%d, K=%d' % (r.pval, r.k, r.K)
            elif self.nqsets > 1 :
                # for multiple query sets, display a table of stats, and include a color swatch
                for r in rslts:
                    # add a row for this result. show p and k
                    qsc = ' '.join(['%s'%x for x in self.qsid2color[r.qsid]])
                    stats += '<TR><TD BGCOLOR="%s" FIXEDSIZE="true" WIDTH="0.5"></TD><TD ALIGN="LEFT">p=%0.0E, k=%d</TD></TR>' \
                      % (qsc, r.pval, r.k)
                    K = r.K # all results for this node have same K
                if stats:
                    # show K
                    stats += '<TR><TD COLSPAN="2">K=%d</TD></TR>' % K
                    # wrap in a table
                    stats = '<TABLE BORDER="0" ALIGN="LEFT" CELLPADDING="1" CELLSPACING="1">%s</TABLE>' % stats
        #
        if label:
            label = '<TR><TD>%s</TD></TR>'%label

        if clrbar:
            clrbar = '<TR><TD>%s</TD></TR>'%clrbar

        if stats:
            stats = '<TR><TD>%s</TD></TR>'%stats

        if label or clrbar:
            label = \
            '''<<TABLE BORDER="0">%s%s%s</TABLE>>''' % (label, clrbar, stats)

        self.dotdag.setObjAttr(n, 'label', label)

        
    def setEdgeAttrs(self, p, c, d):
        pass

    #----------------------------------------------------------

    def assignSubgraphs(self):
        # assigns nodes and edges to their proper subgraph
        for n in self.dotdag.iterNodes():
            sgn = self.getNodeSGName(n)
            sg = self.dotdag.setSubgraph(sgn)
            self.dotdag.setNodeSubgraph(n, sg)

        for p,c,d in self.dotdag.iterEdges():
            sgn = self.getEdgeSGName(p,c,d)
            sg = self.dotdag.setSubgraph(sgn)
            self.dotdag.setEdgeSubgraph(p,c,sg)
        
    def createSubgraphs(self):
        # creates the subgraph hierarhy according to data from the cfg file
        sgattrs = self.getSubgraphAttrs() # map: path->{attrs}
        for (sgn, attrs) in list(sgattrs.items()):
            self.dotdag.setSubgraph(sgn) # creates the sg path
            for which, wattrs in list(attrs.items()): # now set sg attributes
                self.dotdag.setSGAttrs(which, wattrs)

    def doConfig(self, cfgParser):
        DOT="DOT"
        self.subgraphAttrs = {}

        self.qsColors = self.vlad.options.qscolors[:]
        self.qsid2color = self.vlad.options.qsid2color.copy()

        # extract the subgraph configuration data
        for sname in cfgParser.sections():
            # look for a section denoting a subgraph. (begins w/ "DOT/")
            if sname.startswith("DOT/"):
                # get the path part (beginning w/ the "/")
                sgpath = sname[3:]
                curr_sg = self.subgraphAttrs.setdefault(sgpath,{})
                for (n,v) in cfgParser.items(sname):
                    # set the subgraph attributes
                    tokens = n.split(".", 1)
                    if len(tokens) == 1:
                        pass
                    else:
                        curr_sg.setdefault(tokens[0],{})[tokens[1]] = eval(v)

        # Set the background color
        vbg = self.vlad.options.gBackground
        sga = self.subgraphAttrs.setdefault("/",{})
        sga.setdefault("graph", {})['bgcolor'] = vbg
        # Set the node fill color
        vnc = self.vlad.options.gNodeColor
        sga = self.subgraphAttrs.setdefault("/nodes",{})
        sga.setdefault("node", {})['fillcolor'] = vnc
        self.nodeFillColor = vnc
        # Set the font color to contrast with the node color
        lblclr = 'black'
        if colors.bwcontrast(colors.string_to_rgb(vnc)):
            lblclr = 'white';
        sga["node"]['fontcolor'] = lblclr
        self.nodeFontColor = lblclr

    def mkColorBar(self, colors, thickness=None, totallength=None, aspect=0.1):
        '''
        Returns a fragment of a label that draws a horizontal bar consisting
        of a seqeunce of fragments of varying lengths and colors.
        Args:
            colors      (list [color,length]) A list of segment specifications.
                        Each is a pair defining the color and length, resp., of 
                        the segment. Colors are strings (that will go into BGCOLOR
                        attributes).
            totallength If specified, the color bar is scaled so the total length
                        equals this value. Otherwise, the total length is the sum of
                        the segment lengths.
            aspect      The desired aspect ratio of the color bar.
            thickness   The thickness of the color bar. If this is specified, aspect is
                        ignored.
        Returns:
            string, of the form "<TABLE>...</TABLE>"
        '''
        clrbar = [
            '<TABLE BORDER="0" CELLPADDING="0" CELLSPACING="0" CELLBORDER="0" FIXEDSIZE="true">',
            '<TR>',
        ]
        # sum up the segment lengths
        segtotal = 0
        for c,ll in colors:
            segtotal += ll

        # if no segs, no color bar!
        if segtotal == 0:
            return ''

        # determine final total length and the scale factor to use
        if totallength is None:
            totallength = segtotal
            sf = 1.0
        else:
            sf = float(totallength) / segtotal

        #
        if totallength <= 0:
            return ''

        # also, determine the thickness of the bar
        if thickness is None:
            thickness = round(aspect*totallength)

        # add each line seg
        for color,length in colors:
            cell = '<TD FIXEDSIZE="true" WIDTH="%s" HEIGHT="%s" BGCOLOR="%s"></TD>' \
                 % (round(sf*length),thickness,color)
            clrbar.append(cell)
        clrbar.append('</TR></TABLE>')
        # c'est finis
        return ''.join(clrbar)

    def go(self, ns, dag, vlad, labelTerms):
        self.namespace = ns
        self.vlad = vlad
        self.nqsets = len(self.vlad.qsets)
        self.globalMinP = 1.0
        self.doConfig(self.vlad.cfgParser)
        self.labelTerms = labelTerms

        self.results = vlad.results[ns]
        self.term2results = vlad.term2results

        minp = 1.0
        for t in labelTerms:
            rs = self.term2results[ns].get(t,None)
            if rs:
                minp = min(minp, rs[0].minpval)
        self.globalMinP = minp
        self.globalMaxE = -math.log10(self.globalMinP)

        self.dag = dag
        self.dotdag = GVT.DOTDAG(self.dag,ns)


        lbl = '<<TABLE COLOR="black" BGCOLOR="white"><TR><TD COLSPAN="2" BGCOLOR="%s"><FONT COLOR="%s">%s</FONT></TD></TR>' \
            % (self.nodeFillColor, self.nodeFontColor, ns)
        for qsn in self.vlad.options.qsnames:
            qclr = self.qsid2color[qsn]
            if self.nqsets > 1:
                lbl += '<TR><TD BGCOLOR="%s %s %s"> </TD><TD BORDER="0">%s</TD></TR>' \
                    % (qclr[0],qclr[1],qclr[2], qsn)
            else:
                lbl += '<TR><TD BORDER="0">%s</TD></TR>' % qsn
        '''
        if self.nqsets == 2:
            c1 = self.qsid2color[ self.vlad.options.qsnames[0] ]
            c2 = self.qsid2color[ self.vlad.options.qsnames[1] ]
            c1c2 = colors.interpolate(c1, c2, 5)
            c1c2 = map(lambda x:'<TD BGCOLOR="%s %s %s"> </TD>'%(x[0], x[1], x[2]), c1c2)
            c1c2s = "".join(c1c2)
            lbl += '<TR><TD COLSPAN="2"><TABLE BORDER="0"><TR>%s</TR></TABLE></TD></TR>'%c1c2s
        '''

        lbl += '</TABLE>>'
        self.dotdag.setSGAttr('graph','label',lbl)

        for r in self.results:
            if self.globalMaxE == 0:
                r.eRatio = 1.0 / len(self.results)
            else:
                r.eRatio = r.e / self.globalMaxE
            self.dotdag.setObjAttr(r.term, 'minpval', r.minpval)
            self.dotdag.setObjAttr(r.term, 'k', r.k)
            self.dotdag.setObjAttr(r.term, 'K', r.K)
        for n in self.dotdag.iterNodes():
            self.setNodeAttrs(n)
        for p,c,d in self.dotdag.iterEdges():
            self.setEdgeAttrs(p, c, d)

        if self.vlad.options.gCull:
            NodeCutter(self.labelTerms).go(dag=self.dotdag, allPaths=True)

        self.createSubgraphs()
        self.assignSubgraphs()
        return self.dotdag

class NodeCutter(DAG.Traversal):
    def __init__(self, selected):
        self.nodesToCut = None
        self.edgesToAdd = None
        self.selected = selected

    def getResults(self):
        return self.dag

    def beforeTraverse(self, dag):
        self.nodesToCut = set()
        self.edgesToAdd = set()
        # compute the closure over selected nodes (i.e., for every node, the
        # set of selected descendants)
        selected = self.selected
        ns = lambda n:n in selected
        self.closure = DAG.Closure(nodeSelector=ns).go(dag=dag)

    # keep only f node is selected or is an interior "meeting point".
    def decider(self, dag, node, path):
        if node in self.selected:
            return False

        sz = len(self.closure[node])
        for c in dag.iterChildren(node):
            if sz == len(self.closure[c]):
                return True

        return False

    def beforeNode(self, dag, node, path):
        if self.decider(dag, node, path):
            self.nodesToCut.add(node)

    def afterEdge(self, dag, parent, child, data, path):
        if child not in self.nodesToCut and parent in self.nodesToCut:
            for (i, n) in enumerate(reversed(path)):
                if i%2==0 and not n in self.nodesToCut:
                    self.edgesToAdd.add( (n, child, "...") )
                    break;

    def afterTraverse(self, dag):
        for n in self.nodesToCut:
            dag.removeNode(n)
        for p,c,d in self.edgesToAdd:
            dag.addEdge(p,c,d)
        # Remove redundant edges added by previous step
        redges = DAG.RedundantEdgeFinder().go(dag=dag, allPaths=True)
        for p,c,d in redges:
            if d == "..." and dag.hasEdge(p,c):
                dag.removeEdge(p,c)

