#
# GraphvizTools.py
# Classes and definitions for drawing DAGs with GraphViz
# 

#------------------------------------------------------------------

import sys
import os
import time
import types
from . import DAG
import io

#------------------------------------------------------------------

class DOTDAG(DAG.DAG):
    '''
    A DOTDAG is a DAG that additionally supports the setting of
    DOT-language attributes (node-, edge-, or graph-level), and
    a __str__ method that returns the DOT-language representation
    of the graph. A DOTDAG can be created as a new "set of clothes" 
    over an existing DAG object.
    Example usage:
        # create a normal DAG
        d = DAG()
        d.addEdge(A,B)
        ...
        # attach a DOTDAG. d and dd share internal state
        dd = DOTDAG(d)
        # 
        dd.addEdge(A,C) # A->C added to both d and dd
        d.addEdge(B,D)  # B->D added to both d and dd
        # set DOT attributes
        dd.setGlobalAttr(DAG.GRAPH, 'size', '"4,4"')
        ...
        # print the DOT string
        print dd
    '''
    NODE  = 'node'
    EDGE  = 'edge'
    GRAPH = 'graph'

    #---------------------------------------------------------------------
    class DOTSubgraph(object):
        def __init__(self, name, dotdag, parent=None):
            self.name = name
            self.dotdag = dotdag
            self.parent = parent
            self.children = []
            if self.parent:
                self.parent.children.append(self)
            self.globalDotAttrs = { DOTDAG.NODE:{}, DOTDAG.EDGE:{}, DOTDAG.GRAPH:{} }
            self.nodes = set()
            self.edges = set()

        #----

        def getAttrs(self, which):
            return self.globalDotAttrs.setdefault(which,{})

        def getAttr(self, which, name):
            return self.getAttrs(which).setdefault(name,None)

        def getNodeAttr(self, name):
            return self.getAttr(DOTDAG.NODE, name)

        def getEdgeAttr(self, name):
            return self.getAttr(DOTDAG.EDGE, name)

        def getGraphAttr(self, name):
            return self.getAttr(DOTDAG.GRAPH, name)

        #----

        def setAttrs(self, which, attrs):
            self.getAttrs(which).update(attrs)

        def setAttr(self, which, name, val):
            self.getAttrs(which)[name] = val

        def setNodeAttr(self, name, val):
            self.setAttr(DOTDAG.NODE, name, val)

        def setEdgeAttr(self, name, val):
            self.setAttr(DOTDAG.EDGE, name, val)

        def setGraphAttr(self, name, val):
            self.setAttr(DOTDAG.GRAPH, name, val)

        #----

        def getParent(self):
            return self.parent

        def getChild(self, n):
            for c in self.children:
                if c.name == n:
                    return c
            return None

        #----


    #---------------------------------------------------------------------

    def __init__(self, dag=None, name=None):
        DAG.DAG.__init__(self)
        self.wrappedDag = dag
        if dag is not None:
            self.nodes = dag.nodes
        self.objDotAttrs = {}  # maps nodes and edges to DOT attributes (a dict)
        self.currSubgraph = None
        if name:
            rname = name
        else:
            rname = "__root__"
        self.rootSubgraph = self.pushSubgraph(rname)
        self.node2subgraph = {}
        self.edge2subgraph = {}

    def addNode(self, node, subgraph=None):
        if not self.hasNode(node):
            self.setNodeSubgraph(node, subgraph)
        return DAG.DAG.addNode(self,node)

    def removeNode(self, node):
        self.clearNodeSubgraph(node)
        return DAG.DAG.removeNode(self, node)

    def addEdge(self, p, c, edgeData=None, checkCycles=True, subgraph=None):
        self.setEdgeSubgraph(p, c, subgraph)
        return DAG.DAG.addEdge(self, p, c, edgeData, checkCycles)

    def removeEdge(self, p, c):
        self.clearEdgeSubgraph(p, c)
        return DAG.DAG.removeEdge(self, p, c)

    def pushSubgraph(self, name):
        existing = self.currSubgraph and self.currSubgraph.getChild(name)
        if existing:
            self.currSubgraph = existing
        else:
            self.currSubgraph = DOTDAG.DOTSubgraph(name, self, self.currSubgraph)
        return self.currSubgraph

    def popSubgraph(self):
        self.currSubgraph = self.currSubgraph.parent
        
    def setSubgraph(self, path="/"):
        if path.startswith("/"):
            self.currSubgraph = self.rootSubgraph
        for n in path.split('/'):
            if n == "" or n == ".":
                continue
            elif n == "..":
                self.currSubgraph = self.currSubgraph.getParent() \
                    or self.rootSubgraph
            else:
                self.pushSubgraph(n)
        return self.currSubgraph
            
    def peekSubgraph(self):
        return self.currSubgraph

    def getNodeSubgraph(self, node):
        return self.node2subgraph[node]

    def getEdgeSubgraph(self, p, c):
        return self.edge2subgraph[ (p,c) ]

    def setNodeSubgraph(self, node, subgraph = None):
        self.clearNodeSubgraph(node)
        if subgraph is None:
            subgraph = self.currSubgraph
        self.node2subgraph[node] = subgraph
        subgraph.nodes.add(node)

    def setEdgeSubgraph(self, p, c, subgraph = None):
        self.clearEdgeSubgraph(p,c)
        if subgraph is None:
            subgraph = self.currSubgraph
        self.edge2subgraph[(p,c)] = subgraph
        subgraph.edges.add( (p,c) )

    def clearNodeSubgraph(self, node):
        sg = self.node2subgraph.get(node, None)
        if sg:
            sg.nodes.discard(node)
            del self.node2subgraph[node]

    def clearEdgeSubgraph(self, p, c):
        e= (p,c)
        sg = self.edge2subgraph.get( e, None )
        if sg:
            sg.edges.discard(e)
            del self.edge2subgraph[e]

    def getNodeId(self, node):
        id = self.getObjAttr(node, 'id')
        if id:
            pass
        elif hasattr(node, 'id'):
            id =  getattr(node, 'id')
        else:
            id =  str(node)
        return '"%s"'%id

    def getObjAttrs(self, obj):
        return self.objDotAttrs.setdefault(obj, {})

    def hasObjAttr(self, obj, name):
        return name in self.getObjAttrs(obj)
        
    def getObjAttr(self, obj, name):
        return self.getObjAttrs(obj).get(name, None)
        
    def setObjAttr(self, obj, name, value):
        self.getObjAttrs(obj)[name]=value

    def setObjAttrs(self, obj, attrs):
        self.getObjAttrs(obj).update(attrs)

    def clearObjAttrs(self, obj):
        self.getObjAttrs(obj).clear()
        
    def getSGAttrs(self, which):
        return self.currSubgraph.getAttrs(which)

    def setSGAttrs(self, which, attrs):
        self.currSubgraph.setAttrs(which, attrs)

    def getSGAttr(self, which, name):
        return self.currSubgraph.getAttr(which,name)

    def setSGAttr(self, which, name, value):
        self.currSubgraph.setAttr(which,name,value)

    def __str__(self):
        b = io.StringIO()
        DOTWriter().write(self,b)
        s = b.getvalue()
        b.close()
        return s

#------------------------------------------------------------------

class DOTWriter(DAG.Traversal):
    '''
    A traversal over DOTDAGs that generates the DOT-language
    representation of the draph. (AKA: the implementation
    of a DOTDAG's __str__ method.)
    '''

    def write(self, dag, wp=sys.stdout):
        self.dag = dag
        doopen = (type(wp) is str)
        if doopen:
            wp = open(wp, 'w')
        self.wp = wp
        self.writeSubgraph(self.dag.rootSubgraph)
        if doopen:
            self.wp.close()

    def writeSubgraph(self, subgraph):
        self.writeHead(subgraph)
        for c in subgraph.children:
            self.writeSubgraph(c)
        for n in subgraph.nodes:
            self.append( self.getNodeStr( self.dag, n ) )
        for p,c in subgraph.edges:
            self.append( self.getEdgeStr( self.dag, p, c ) )
        self.writeTail()

    def append(self, line):
        self.wp.write(line)
        self.wp.write('\n')

    def writeHead(self, subgraph):
        '''
        Initialize line buffer. Adds graph declaration line,
        opening brace, and global attribute declarations.
        '''
        if subgraph.parent is None:
            self.append('digraph "%s" {' %subgraph.name)
        else:
            self.append('subgraph "%s" {' %subgraph.name)
        self.append(self.getGlobalAttrsStr(subgraph, DOTDAG.GRAPH))
        self.append(self.getGlobalAttrsStr(subgraph, DOTDAG.NODE))
        self.append(self.getGlobalAttrsStr(subgraph, DOTDAG.EDGE))

    def writeTail(self):
        '''
        Appends closing brace.
        '''
        self.append("}")

    def getAttrStr(self, name, value):
        '''
        Formats one name/value pair as DOT.
        '''
        if type(value) is str:
            if not (name == "label" and value[:1] == "<"):
                value = '"%s"'%value 
        return "%s = %s" % (name, str(value))

    def getAttrString(self, attrs, doFilter=True):
        '''
        Formats a set of attributes (a dict) as DOT.  E.g., 
            shape = box, weight = 0.8, label = "Hi there"
        If doFilter is True (the default), only standard DOT
        attributes are written.
        This means that you can safely add node/edge attributes
        that are not recognized by dot (and may not even have
        a string representation).
        '''
        itms = list(attrs.items())
        if doFilter:
            itms = [x for x in itms if x[0] in DOTATTRNAMES]
        return ", ".join([self.getAttrStr(x[0],x[1]) for x in itms])

    def getGlobalAttrsStr(self, subgraph, type):
        '''
        Formats a set of global attributes in DOT.
        '''
        attrs = self.getAttrString(subgraph.getAttrs(type))
        if attrs:
            return "%s [ %s ];" % (type, attrs)
            '''
            if type == DOTDAG.GRAPH:
                return "%s;"%attrs
            else:
                return "%s [ %s ];" % (type, attrs)
            '''
        else:
            return ""

    def getNodeStr(self, dag, node):
        '''
        Formats a node as DOT. Nodes have the form:
            id ;
        or
            id [ <attrs> ] ;
        '''
        id = dag.getNodeId(node)
        attrs = self.getAttrString( dag.getObjAttrs(node) )
        if attrs:
            return "%s [ %s ];" % (id, attrs)
        else:
            return "%s ;" % id

    def getEdgeStr(self, dag, parent, child):
        '''
        Formats an edge as DOT. Edges have the form:
            id -> id ;
        or
            id -> id [ <attrs> ] ;
        '''
        pid = dag.getNodeId(parent)
        cid = dag.getNodeId(child)
        attrs = self.getAttrString(dag.getObjAttrs( (parent,child) ))
        if attrs:
            return "%s -> %s [ %s ];" % (pid, cid, attrs)
        else:
            return "%s -> %s;" % (pid, cid)
        
#------------------------------------------------------------------

class DOTRunner(object):
    def __init__(self, executable, homeDir=None):
        self.executable = executable
        if not os.path.exists(self.executable):
            raise RuntimeError("Could not find dot executable: "+self.executable)
        self.spawnEnv = os.environ.copy()
        if homeDir:
            self.spawnEnv['HOME'] = homeDir

    def run0(self, args = []):
        os.spawnve(os.P_WAIT, self.executable, [self.executable]+args, self.spawnEnv)

    def run(self, dotfile, outfile, format, extraArgs=[]):
        args = [ "-o%s"%outfile, "-T%s"%format ] + extraArgs + [dotfile]
        self.run0(args)

#------------------------------------------------------------------

# The set of all attribute names defined in the DOT language.
DOTATTRNAMES = set('''
Damping K URL arrowhead arrowsize arrowtail aspect bb bgcolor
center charset clusterrank color colorList colorscheme comment compound concentrate constraint
decorate defaultdist dim dimen dir diredgeconstraints distortion dpi
edgeURL edgehref edgetarget edgetooltip epsilon esep
fillcolor fixedsize fontcolor fontname fontnames fontpath fontsize
group
headURL headclip headhref headlabel headport headtarget headtooltip height href
id image imagescale
label labelURL labelangle labeldistance labelfloat labelfontcolor labelfontname labelfontsize
labelhref labeljust labelloc labeltarget labeltooltip landscape layer layers layersep
layout len levels levelsgap lhead lp ltail
margin maxiter mclimit mindist minlen mode model mosek nodesep
nojustify normalize nslimit nslimit1
ordering orientation orientation outputorder overlap overlap_scaling
pack packmode pad pointf page pagedir pencolor penwidth peripheries pin pos
quadtree quantum
rank rankdir ranksep ratio rects regular remincross repulsiveforce resolution root rotate
samehead sametail samplepoints searchsize sep shape shapefile showboxes sides size
skew smoothing sortv splines start style stylesheet
tailURL tailclip tailhref taillabel tailport tailtarget tailtooltip target tooltip truecolor
vertices viewport voro_margin
weight width
z
'''.strip().split())

#------------------------------------------------------------------

## main

if __name__ == "__main__":
    DOTDIR = '/Users/jer/Desktop/Graphviz1.13/Graphviz.app/Contents/MacOS'
    A='a'
    B='b'
    C='c'
    D='d'
    E='e'
    F='f'
    g = DOTDAG()
    sg_n = g.setSubgraph("/nodes")
    sg_n.setNodeAttr("color", "magenta")
    sg_nx = g.setSubgraph("/nodes/expanded")
    sg_nx.setNodeAttr("shape","ellipse")
    sg_nc = g.setSubgraph("/nodes/collpased")
    sg_nc.setNodeAttr("shape", "point")
    sg_e = g.setSubgraph("/edges")
    sg_e.setEdgeAttr("dir", "back")
    sg_e.setEdgeAttr("weight", 0.85)
    sg_ei = g.setSubgraph("/edges/isa")
    sg_ei.setEdgeAttr("color","green")
    sg_ei.setEdgeAttr("arrowtail","empty")
    sg_ep = g.setSubgraph("/edges/partof")
    sg_ep.setEdgeAttr("color","purple")
    sg_ep.setEdgeAttr("arrowtail","diamond")
    sg_er = g.setSubgraph("/edges/regulates")
    sg_er.setEdgeAttr("color","blue")
    sg_ep.setEdgeAttr("arrowtail","vee")
    
    g.setSubgraph("/nodes/expanded")
    g.addNode(A).addNode(B, subgraph=sg_nc).addNode(C, subgraph=sg_nc).addNode(D).addNode(E).addNode(F)
    g.setSubgraph("/edges/isa")
    g.addEdge(A,B).addEdge(A,C).addEdge(C,D, subgraph=sg_ep).addEdge(B,D, subgraph=sg_er).addEdge(B,E).addEdge(C,F)
    print(g)

    #d = DAG.DAG()
    #d.addEdge(A,B).addEdge(A,C).addEdge(B,D).addEdge(C,D).addEdge(B,E).addEdge(C,F)
    #g = DOTDAG(d)
    #print g

    dotfile = '/Users/jer/Desktop/xxx.dot'
    imgfile = '/Users/jer/Desktop/xxx.png'
    dw = DOTWriter()
    dw.write(g, dotfile)
    dr = DOTRunner(DOTDIR)
    dr.run(dotfile, imgfile, 'png')

