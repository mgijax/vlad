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

        if self.doPercents:
            self.dotdag.setObjAttr(n, 'shape', 'box')
            self.dotdag.setObjAttr(n, 'width', 1.0)
            self.dotdag.setObjAttr(n, 'height', 1.0)
            return

        rslts = self.term2results[self.namespace].get(n,[])
        score = 0.0
        for r in rslts:
            if self.doPercents:
                score = max(score, r.pval)
            else:
                score = max(score, r.eRatio)
        maxdiameter = 1.5 # inches
        mindiameter = 0.1
        self.dotdag.setObjAttr(n, 'shape', 'box')
        maxarea = maxdiameter**2
        minarea = mindiameter**2
        area = minarea + score*(maxarea-minarea)
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
            if self.doPercents:
                l = r.pval
            else:
                l = r.e
            segs.append( [qsc, l] )
        #
        if not n.is_nsroot and len(segs) > 0 and self.nqsets > 1:
            if cbarIsNode:
                aspect = 1.0
                tlen = 0.92*pwidth
            else:
                aspect = 0.15
                tlen = 0.85*pwidth
            if self.doPercents:
                clrbar = self.mkBarChart(tlen, aspect*tlen, segs)
            else:
                clrbar = self.mkColorBar(segs, totallength=tlen, aspect=aspect)

        # stats line
        stats = ''
        if dolabel and rslts and not n.is_nsroot:
            K=0 # K = #genes annotated to this node in the database
            if self.nqsets == 1:
                # for a single query set, just display the stats as two lines of text: p, then k and K.
                r = rslts[0]
                if self.doPercents:
                    stats = '%d%%<BR/>k=%d, K=%d' % (round(100*r.pval), r.k, r.K)
                else:
                    stats = 'p=%0.1E<BR/>k=%d, K=%d' % (r.pval, r.k, r.K)
            elif self.nqsets > 1 :
                # for multiple query sets, display a table of stats, and include a color swatch
                for r in rslts:
                    # add a row for this result. show p and k
                    qsc = ' '.join(['%s'%x for x in self.qsid2color[r.qsid]])
                    if self.doPercents:
                      stats += '<TR><TD BGCOLOR="%s" FIXEDSIZE="true" WIDTH="0.5"></TD><TD ALIGN="LEFT">%d%%, k=%d</TD></TR>' \
                        % (qsc, round(100*r.pval), r.k)
                    else:
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

    def mkBarChart(self, width, height, colors):
        clrbar = [
            ('<TABLE BORDER="1" CELLPADDING="0" CELLSPACING="0" CELLBORDER="0" FIXEDSIZE="true" ' + \
            '  WIDTH="%s" HEIGHT="%s" >') % (width, height)
        ]

        # calculate width of each bar
        nbars = len(colors)
        if nbars == 0:
          return ''
        spacerWidth = 2
        barThickness = (height - 2 - (spacerWidth * (nbars - 1))) / nbars

        # add each line seg
        for i, (color,pct) in enumerate(colors):
            if i > 0:
                #add spacer
                cell = '<TR><TD ALIGN="left" FIXEDSIZE="true" WIDTH="1" HEIGHT="%s"></TD></TR>' % spacerWidth
                clrbar.append(cell)
            # add bar
            cell = '<TR><TD ALIGN="left" FIXEDSIZE="true" WIDTH="%s" HEIGHT="%s" BGCOLOR="%s"></TD></TR>' \
                 % (pct*width, barThickness, color)
            clrbar.append(cell)
        clrbar.append('</TABLE>')
        # c'est finis
        return ''.join(clrbar)

    def go(self, ns, dag, vlad, labelTerms):
        self.namespace = ns
        self.vlad = vlad
        self.doPercents = (vlad.options.analysis == "percentage")
        self.nqsets = len(self.vlad.qsets)
        self.globalMinP = 1.0
        self.doConfig(self.vlad.cfgParser)
        self.labelTerms = labelTerms

        self.results = vlad.results[ns]
        self.term2results = vlad.term2results

        # find the global minimum p-val, then calc the global maximum e-val
        minp = 1.0
        maxp = 0.0
        for t in labelTerms:
            rs = self.term2results[ns].get(t,None)
            if rs:
                minp = min(minp, rs[0].minpval)
                maxp = max(maxp, rs[0].maxpval)
        self.globalMinP = minp
        self.globalMaxP = maxp
        if not self.doPercents:
            self.globalMaxE = -math.log10(self.globalMinP)
        else:
            self.globalMaxE = 0.0

        # create the DOT dag that we will manipulate from the base dag
        self.dag = dag
        self.dotdag = GVT.DOTDAG(self.dag,ns)


        # generate the graph title box
        lbl = '<<TABLE COLOR="black" BGCOLOR="white"><TR><TD COLSPAN="2" BGCOLOR="%s"><FONT COLOR="%s">%s (N=%d)</FONT></TD></TR>' \
            % (self.nodeFillColor, self.nodeFontColor, ns, self.results[0].N)
        for i,qsn in enumerate(self.vlad.options.qsnames):
            qsize = self.results[i].n
            qclr = self.qsid2color[qsn]
            if self.nqsets > 1:
                lbl += '<TR><TD BGCOLOR="%s %s %s"> </TD><TD BORDER="0">%s (n=%d)</TD></TR>' \
                    % (qclr[0],qclr[1],qclr[2], qsn, qsize)
            else:
                lbl += '<TR><TD BORDER="0">%s (n=%d)</TD></TR>' % (qsn, qsize)

        lbl += '</TABLE>>'
        self.dotdag.setSGAttr('graph','label',lbl)

        # 
        for r in self.results:
            if not self.doPercents:
                if self.globalMaxE == 0:
                    r.eRatio = 1.0 / len(self.results)
                else:
                    r.eRatio = r.e / self.globalMaxE
            self.dotdag.setObjAttr(r.term, 'minpval', r.minpval)
            self.dotdag.setObjAttr(r.term, 'maxpval', r.maxpval)
            self.dotdag.setObjAttr(r.term, 'k', r.k)
            self.dotdag.setObjAttr(r.term, 'K', r.K)

        for n in self.dotdag.iterNodes():
            self.setNodeAttrs(n)
        for p,c,d in self.dotdag.iterEdges():
            self.setEdgeAttrs(p, c, d)

        if self.vlad.options.gCull:
            culled = NodeCuller('minpval').go(dag=self.dotdag, allPaths=True)
            NodeCutter(culled).go(dag=self.dotdag, allPaths=True)
            NodeCollapser().go(dag=self.dotdag)

        self.createSubgraphs()
        self.assignSubgraphs()
        return self.dotdag

# A traversal that marks each node to be culled with a flag.
# Return value is the set of marked nodes. (Doesn't actually change the dag)
class NodeCuller(DAG.Traversal):
    def __init__(self, scoreAttr):
        self.scoreAttr = scoreAttr
        self.markedNodes = set()
    def beforeEdge(self, dag, parent, child, data, path):
        pscore = dag.getObjAttr(parent, self.scoreAttr)
        cscore = dag.getObjAttr(child, self.scoreAttr)
        if cscore >= pscore and not parent.is_nsroot:
            self.markedNodes.add(parent)
    def getResults(self):
        return self.markedNodes

# A traversal that prunes nodes and reattaches edges.
# Init with the set of nodes to cut and the string label for replacement edges.
class NodeCutter(DAG.Traversal):
    def __init__(self, nodesToCut, edgeLabel="..."):
        self.nodesToCut = nodesToCut
        self.edgesToAdd = None
        self.edgeLabel = edgeLabel

    def getResults(self):
        return self.dag

    def beforeTraverse(self, dag):
        self.edgesToAdd = set()

    # If parent node is to be cut, but my child isn't, need to
    # reconnect child to nearest unpruned (retained) ancestor node in the
    # current path.
    def beforeEdge(self, dag, parent, child, data, path):
        if child not in self.nodesToCut and parent in self.nodesToCut:
            for (i, n) in enumerate(reversed(path)):
                if i%2==0 and not n in self.nodesToCut:
                    self.edgesToAdd.add( (n, child, self.edgeLabel) )
                    break;

    # After traversal is done, process the results. Remove the nodes. Add the edges.
    def afterTraverse(self, dag):
        for n in self.nodesToCut:
            dag.removeNode(n)
        for p,c,d in self.edgesToAdd:
            dag.addEdge(p,c,d)
        # Remove redundant edges added by previous step
        redges = DAG.RedundantEdgeFinder().go(dag=dag, allPaths=True)
        for p,c,d in redges:
            if d == self.edgeLabel and dag.hasEdge(p,c):
                dag.removeEdge(p,c)

class NodeCollapser(DAG.Traversal):
  def __init__(self, width = 0.1, height = 0.1, label = ''):
    self.width = width
    self.height = height
    self.label = label

  def beforeNode(self, dag, node, path):
    if dag.isInteriorNode(node):
      dag.setObjAttr(node, 'width', self.width)
      dag.setObjAttr(node, 'height', self.height)
      dag.setObjAttr(node, 'label', self.label)
