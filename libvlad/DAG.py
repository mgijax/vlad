#
# DAG.py
#
# Directed acyclic graph representation. There are two main concepts implemented here: 
# DAGs and traversals. 
#
# A DAG is that mathmatical object having nodes and edges that we all know and love 
# from ontology work. 
# A DAG object encapsulates a set of nodes and edges and provides basic structuring and
# inquiry methods.
# Any hashable object (i.e., anything
# that could be a key in a dict) can be a node. You can supply your own node class
# if you want. Simple strings and numbers can also be nodes.
# Edges are associations between nodes that optionally carries an arbitrary
# user-defined data object.
# Edges have a direction (there is a "parent" and a "child" node). 
#
# A traversal encapsulates a recursive procedure that (by default) visits every node
# and crosses every edge in order do something, e.g., compute a closure, pretty print
# the DAG, check for cycles, whatever. The traversal framework takes care of the
# navigation and bookkeeping; user-supplied callbacks perform whatever computation is 
# desired.
#
# For examples of usage, see the self test at the end of this file.
#
# Implementation: 
#   The dag is a dict.
#     The nodes are the dict's keys.
#     Each node maps to a tuple: (in-edges, out-edges)
#       In-edges is a dict that maps parent nodes to edge data values.
#	    => a node's direct parents are the keys in this dict
#	Out-edges is a dict that maps child nodes to edge data values.
#	    => a node's direct children are the keys in this dict
#
# Facts:
#    The nodes of the dag == the keys of the dag's dict.
#    There is no node class or edge class. All methods are defined on the DAG object itself.
#    A given edge is represented twice: in the out-edges of the
#    parent node, and in the in-edges of the child node. 
#

import sys

#####################################################################

class DAG(object):
    def __init__(self):
	self.nodes = {}

    #----------------------------------------------------------
    # STRUCTURING METHODS
    #----------------------------------------------------------

    def addNode(self, n):
	if not self.hasNode(n):
	    self.__addnode__(n)
	return self

    def removeNode(self, n):
        for p in self.iterParents(n):
	    self.__children__(p).pop(n)
	for c in self.iterChildren(n):
	    self.__parents__(c).pop(n)
	self.nodes.pop(n)
	return self

    def addEdge(self, parent, child, edgeData=None, checkCycles=True):
        self.addNode(parent)
	self.addNode(child)
	if checkCycles and (parent == child or self.isDescendant(parent, child)):
	    raise CycleError("Edge would create cycle. parent(%s) child(%s)"%(str(parent), str(child)))
	self.__children__(parent)[child] = edgeData
	self.__parents__(child)[parent] = edgeData
	return self

    def removeEdge(self, parent, child):
        self.__children__(parent).pop(child)
	self.__parents__(child).pop(parent)
	return self

    def clone(self):
        cln = DAG()
	for n, (parents, children) in self.nodes.iteritems():
	    cln.nodes[n] = (parents.copy(), children.copy())
	return cln

    def clear(self):
        self.nodes = {}
	return self

    #----------------------------------------------------------
    # INQUIRY METHODS
    #----------------------------------------------------------

    # Returns True iff n is a node in the graph
    def hasNode(self, n):
        return n in self.nodes

    # Returns True iff there is an edge from parent to child in the graph.
    def hasEdge(self, parent, child):
        return self.hasNode(parent) and child in self.__children__(parent)

    # Returns True iff n is in the graph and has no ancestors.
    def isRoot(self, n):
        return self.hasNode(n) and len(self.__parents__(n)) == 0

    # Returns True iff n is in the graph and has no descendants.
    def isLeaf(self, n):
        return self.hasNode(n) and len(self.__children__(n)) == 0

    # Returns True iff n is in the graph and has both ancestors and descendants.
    def isInteriorNode(self, n):
        return self.hasNode(n) and not (self.isRoot(n) or self.isLeaf(n))

    # Returns True iff both n and m are in the graph and n is a child of m.
    def isChild(self, n, m):
        return n in self.__children__(m)

    # Returns True iff both n and m are in the graph and n is a parent of m.
    def isParent(self, n, m):
        return self.isChild(m, n)

    # Returns True iff both n and m are in the graph and n is a descendant of m.
    def isDescendant(self, n, m):
        return self.isAncestor(m, n)

    # Returns True iff both n and m are in the graph and n is an ancestor of m.
    def isAncestor(self, n, m):
        for p in self.iterParents(m):
            if n == p or self.isAncestor(n, p):
                return True
        return False

    #----------------------------------------------------------
    # ITERATION METHODS
    #----------------------------------------------------------

    def iterNodes(self):
        return self.nodes.iterkeys()

    def iterRoots(self):
        for n in self.iterNodes():
	    if self.isRoot(n):
	        yield n

    def iterLeaves(self):
        for n in self.iterNodes():
	    if self.isLeaf(n):
	        yield n

    def iterInEdges(self, n):
        return self.__parents__(n).iteritems()

    def iterParents(self, n):
        return self.__parents__(n).iterkeys()

    def iterOutEdges(self, n):
        return self.__children__(n).iteritems()

    def iterChildren(self, n):
        return self.__children__(n).iterkeys()

    def iterEdges(self):
        for n in self.iterNodes():
	    for n2,d in self.iterOutEdges(n):
	        yield n, n2, d

    #
    # General purpose graph traversal method. A traversal is a procedure for
    # visiting all or parts of a DAG in a depth-first, recursive manner from a 
    # specified set of starting nodes.
    # Optional callback functions supplied by the caller provide hooks
    # for custom node/edge processing. In other words, you provide the 
    # logic, we provide the transportation!
    #
    # Paths. A path is the "trail" by which we got to a given point during a
    # traversal. It is an alternating sequence nodes and edges, beginning with
    # one of the start nodes, and ending just prior to the current node or edge.
    #
    # Args:
    #	startNodes	None, or list (or other iterable) of nodes. Specifies the
    #		starting point(s) for the traversal. If None, the default starts
    #		at the root(s) if traversal is forward, and leaves if reversed.
    #	reversed	Boolean. If False (the default) traversal descends from
    #		nodes to their descendants. If True, traversal ascends from nodes
    #		to their ancestors.
    #	allPaths	Boolean. If False (the default), a given node is visited 
    #		exactly once. Otherwise, the node is visited along all possible 
    #		paths from any start node.
    #	beforeTraverse  Callable. Callback function invoked immediately prior to
    #		start of traversal. Function called with the DAG instance.
    #	afterTraverse  Callable. Callback function invoked immediately following
    #		end of traversal. Function called with the DAG instance.
    #	beforeNode  Callable. Callback function invoked at start of visit to each
    #		node. Function called with three args: the dag, the node, and the
    #		current path. 
    #	afterNode  Callable. Callback function invoked at end of visit to each
    #		node. Function called with three args: the dag, the node, and the
    #		current path. 
    #	afterEdge Callable. Callback function invoked immediately prior to crossing
    #		an edge. Function called with five args: the dag, the current node,
    #		the other node, the edge data object (if any), and the current path.
    #	beforeEdge Callable. Callback function invoked immediately prior to crossing
    #		an edge. Function called with five args: the dag, the current node,
    #		the other node, the edge data object (if any), and the current path.
    # 
    def traverse(self, 
		startNodes=None,
		reversed=False,
		allPaths=False,
    		beforeTraverse=None, afterTraverse=None, 
		beforeNode=None, afterNode=None, 
		beforeEdge=None, afterEdge=None):
	visited = set()
	# Path stack. A path:
	#  - is an alternating sequence of nodes and edges
	#  - begins with a startNode
	#  - ends with the edge (or node) just prior to the current node
	#    (or edge). That is:
	# 	beforeNode() and afterNode() see a path whose last
	#	item is the edge we crossed to get to the node.
	#	beforeEdge() and afterEdge() see a path whose
	#	last item is the node from which the edge is crossed.
	# Note that:
	#  - when processing a startNode, the path is empty
	#  - the path item at position i is a node if i is even,
	#	and an edge if i is odd.
	#
	path = [ ]
	iterEdges = self.iterOutEdges
	if reversed:
	    iterEdges = self.iterInEdges
	# here's the recursive function for "visit"-ing a node
	def reach(n):
	    if beforeNode and beforeNode(self, n, path) == False:
	        return
	    path.append(n)
	    visited.add(n)
	    for (n2,d) in iterEdges(n):
		if reversed:
		    p,c = n2,n
		else:
		    p,c = n,n2
		if beforeEdge and beforeEdge(self,p,c,d, path) == False:
		    continue
		if allPaths or not n2 in visited:
		    path.append( (n, n2, d) )
		    reach(n2)
		    path.pop()
		afterEdge and afterEdge(self,p,c,d, path)
	    path.pop()
	    afterNode and afterNode(self, n, path)
	##
	## Traversal top level:
	if beforeTraverse and beforeTraverse(self) == False:
	    return
	if startNodes is None:
	    # set start nodes, if not specified.
	    # start from leaves or roots, depending on traversal direction
	    if reversed:
		startNodes = self.iterLeaves()
	    else:
		startNodes = self.iterRoots()
	# visit each start node
	for r in startNodes:
	    if self.hasNode(r) and not r in visited:
		reach(r)
	# postprocessing hook
	afterTraverse and afterTraverse(self)

    #----------------------------------------------------------
    # ACCESS METHODS
    #----------------------------------------------------------

    def getNode(self, n):
        if not self.hasNode(n):
	    raise KeyError(n)
	return n

    def getEdge(self, parent, child):
        return self.__children__(parent)[child]

    def getNodes(self):
        return list(self.iterNodes())

    def getRoots(self):
        return list(self.iterRoots())

    def getLeaves(self):
        return list(self.iterLeaves())

    def getParents(self, n):
        return list(self.iterParents(n))

    def getChildren(self, n):
        return list(self.iterChildren(n))

    def getInEdges(self, n):
        return list(self.iterInEdges(n))

    def getOutEdges(self, n):
        return list(self.iterOutEdges(n))

    #----------------------------------------------------------
    # INTERNAL METHODS
    #----------------------------------------------------------

    def __addnode__(self, n):
        self.nodes[n] = ({}, {})    # ({parents}, {children})

    def __parents__(self, child):
        return self.nodes[child][0]

    def __children__(self, parent):
        return self.nodes[parent][1]

    #----------------------------------------------------------
    # MISCELLANEOUS METHODS
    #----------------------------------------------------------

    def __str__(self):
        return str(self.nodes)

    def debug(self, fd=sys.stdout):
	NL='\n'
        def prn(dag,node):
	    fd.write("NODE:"+str(node)+NL)
	def pre(dag,node1,node2,edata):
	    fd.write("EDGE:"+str(edata)+": "+str(node1)+" -> "+str(node2)+NL)
	self.traverse(beforeNode=prn, beforeEdge=pre)

#####################################################################

class Traversal(object):

    beforeTraverse	= None
    afterTraverse	= None
    beforeNode		= None
    afterNode		= None
    beforeEdge		= None
    afterEdge		= None

    def getResults(self):
        return self

    def go(self, dag, startNodes=None, reversed=False, allPaths=False):
	self.dag = dag
	self.startNodes = startNodes
	self.reversed = reversed
	self.allPaths = allPaths
	self.dag.traverse(
	    startNodes = self.startNodes,
	    reversed = self.reversed,
	    allPaths = self.allPaths,
	    beforeTraverse = self.beforeTraverse,
	    afterTraverse = self.afterTraverse,
	    beforeNode = self.beforeNode,
	    afterNode = self.afterNode,
	    beforeEdge = self.beforeEdge,
	    afterEdge = self.afterEdge )
	return self.getResults()

#-------------------------------------------------------

class SimplePrinter(Traversal):
    def beforeNode(self, dag, node, path):
	print str(node)
    def beforeEdge(self, dag, p, c, d, path):
	print str(p), '->', str(c), "["+str(d)+"]"

#-------------------------------------------------------

class Closure(Traversal):
    def __init__(self,nodeSelector=lambda n:True):
        self.closure = {}
	self.nodeSelector = nodeSelector
    def beforeNode(self,dag,node,path):
        s = set()
	if self.nodeSelector(node):
	    s.add(node)
	self.closure[node] = s
    def afterEdge(self,dag,p,c,d,path):
        if self.reversed:
	    self.closure[c] |= self.closure[p]
	else:
	    self.closure[p] |= self.closure[c]
    def getResults(self):
        return self.closure

#-------------------------------------------------------

class RedundantEdgeFinder(Traversal):
    def __init__(self):
        self.redges = []
	self.allPaths=True
    def beforeNode(self, dag, node, path):
	# scan the nodes along the path for edges to me.
	maxi = len(path)-4 # stop scan two nodes back
        for i,p in enumerate(path):
	    if i > maxi:
	        break
	    if i%2==0 and dag.hasEdge(p,node):
		self.redges.append( [p,node,dag.getEdge(p,node)] )
    def getResults(self):
        return self.redges

#-------------------------------------------------------

class SimplePruner(Traversal):
    def __init__(self, nodeFilt=None, edgeFilt=None):
        self.nodeFilt = nodeFilt
	self.edgeFilt = edgeFilt
	self.pruneNodes = []
	self.pruneEdges = []

    def beforeNode(self, dag, node, path):
        if self.nodeFilt and self.nodeFilt(node):
	    self.pruneNodes.append(node)

    def beforeEdge(self, dag, p, c, d, path):
	if self.edgeFilt and self.edgeFilt(p, c, d):
	   self.pruneEdges.append( (p, c, d) )

    def afterTraverse(self, dag):
        for (p,c,n) in self.pruneEdges:
	    dag.removeEdge(p,c)
	for n in self.pruneNodes:
	    dag.removeNode(n)

#-------------------------------------------------------

class SubgraphExtracter(Traversal):
    def __init__(self, inclusive=True):
	self.subgraph = None
	# If True, extraction includes everything reachable
	# from the start nodes. If False, extraction only includes
	# the nodes given and any edges between them.
	self.inclusive = inclusive
    def beforeTraverse(self, dag):
        self.subgraph = DAG()
	if not self.inclusive:
	    for n in self.startNodes:
		if dag.hasNode(n):
		    self.subgraph.addNode(n)
    def beforeNode(self, dag, node, path):
	if self.inclusive:
	    self.subgraph.addNode(node)
    def beforeEdge(self, dag, p, c, d, path):
	if self.inclusive or (self.subgraph.hasNode(p) and self.subgraph.hasNode(c)):
	    self.subgraph.addEdge(p,c,d)
    def getResults(self):
        return self.subgraph

#-------------------------------------------------------

class DAGMapper(Traversal):
    '''
    A traversal that generates a new dag by mapping the nodes and edges
    of the input dag. 
    Functions:
        dagMap(g)
	nodeMap(n)
	edgeMap(p,c,p2,c2,d)
    '''
    def __init__(self, dagMap = lambda g:DAG(), nodeFilt = lambda n:True, nodeMap = lambda n:n, edgeFilt = lambda p,c,d:True, edgeMap = lambda p,c,p2,c2,d:d ):
        self.dagMap = dagMap
	self.nodeFilt = nodeFilt
	self.nodeMap = nodeMap
	self.edgeFilt = edgeFilt
	self.edgeMap = edgeMap
	self.mappedNodes = {}
	self.mappedEdges = {}
	self.resultDag = None
    def beforeTraverse(self, srcDag):
        self.resultDag = self.dagMap(srcDag)
    def getMappedNode(self, node):
        if self.mappedNodes.has_key(node):
	    return self.mappedNodes[node]
	n2 = self.nodeMap(node)
	self.mappedNodes[node] = n2
	return n2
    def getMappedEdge(self, p, c, d):
        p2 = self.getMappedNode(p)
	c2 = self.getMappedNode(c)
	e = (p2,c2)
	if self.mappedEdges.has_key(e):
	    return self.mappedEdges(e)
	d2 = self.edgeMap(p, c, p2, c2, d)
	self.mappedEdges[e] = d2
	return d2
    def beforeNode(self, dag, node, path):
	if self.nodeFilt(node):
	    return self.resultDag.addNode(self.getMappedNode(node))
	return False
    def beforeEdge(self, dag, p, c, d, path):
	if self.edgeFilt(p,c,d):
	    p2 = self.getMappedNode(p)
	    c2 = self.getMappedNode(c)
	    return self.resultDag.addEdge(p2, c2, self.edgeMap(p,c,p2,c2,d))
	return False
    def getResults(self):
        return self.resultDag

    
#####################################################################

class CycleError(Exception):
    pass

#####################################################################

if __name__ == "__main__":
    def printeval(expr, env):
        print expr, eval(expr, env)

    print """
#
# Building this dag:
#     a
#    / \ 
#   b   c
#  / \ / \ 
# x   d   y
#
#
"""
    d = DAG()
    d.addEdge('a','b').addEdge('a','c').addEdge('b','d').addEdge('c','d')
    d.addEdge('b','x', 99).addEdge('c','y')
    print str(d)
    #
    env = {'d':d}
    printeval("d.hasNode('a')", env)
    printeval("d.getNode('a')", env)
    printeval("d.isRoot('a')", env)
    printeval("d.isLeaf('x')", env)
    printeval("list(d.iterLeaves())", env)
    printeval("d.getParents('b')", env)
    printeval("d.getChildren('b')", env)

    #
    pr=SimplePrinter()
    pr.go(d)

    #
    print
    print "Closure:"
    c = Closure().go(d)
    for (n,descs) in c.iteritems():
	print str(n), "->",
	for x in descs:
	    print str(x),
	print
    print
    print "Reverse Closure:"
    c = Closure().go(d, reversed=True)
    for (n,ancs) in c.iteritems():
	print str(n), "<-",
	for x in ancs:
	    print str(x),
	print
    print
    print "Ancestors of d:"
    print c['d']

    print
    print "Subgraph (c)"
    sg = SubgraphExtracter().go(d, 'c')
    pr.go(sg)
    print
    print "Subgraph (d reversed)"
    sg = SubgraphExtracter().go(d, 'd', reversed=True)
    pr.go(sg)
    print
    print "Clone:"
    d2 = d.clone()
    pr.go(d2)

    print
    print "Mapper (d reversed)"
    mg = DAGMapper(nodeMap=lambda n:"NODE:%s"%n, edgeMap=lambda p,c,p2,c2,d:"EDGE:%s->%s"%(p,c)).go(d, 'd', reversed=True)
    pr.go(mg)

    print
    print "Mapper + Filter"
    mg = DAGMapper(nodeMap=lambda n:"NODE:%s"%n, edgeMap=lambda p,c,p2,c2,d:"EDGE:%s->%s"%(p,c), nodeFilt = lambda n: n!='c', edgeFilt=lambda p,c,d: p!='b' or c!='x').go(d)
    pr.go(mg)

    print
    print "Prune:"
    p = SimplePruner(nodeFilt=lambda n:n=='c', edgeFilt=lambda p,c,d: p=='a').go(d)
    pr.go(d)

    print
    print "Clone unaffected by prune"
    pr.go(d2)


