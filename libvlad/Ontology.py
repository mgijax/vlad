#!/usr/bin/python
# Ontology.py
#
# Classes:
#       OboOntology
#       OboTerm
#       OboParser
#       OboLoader
#
# Feb 23, 2011
# Remove restriction that ontology has only one root. Newer OBO files
# will include some, but not all, terms from other ontologies. E.g.,
# the protein ontology contains some GO terms because some PRO terms
# reference GO terms.
#

#------------------------------------

import sys
import re
import string
import types
from . import DAG

#------------------------------------
#
# Base class for an OboTerm.
# Subclass this if you need more functionality for terms, and pass your subclass
#   to the OboOntology constructor.
#
class OboTerm(object):
    def __init__(self, id, name, ontol):
        self.id = id
        self.name = name
        self.namespace = None
        self.is_obsolete = False
        self.is_nsroot = False
        self.ontology = ontol

    def getUrl(self):
        tmplt = getattr(self.ontology.config, 'linkurl', None)
        if tmplt is None:
            return None
        return tmplt % self.id

    def __str__(self):
        return self.id + " " + self.name

#------------------------------------

class OboOntology(DAG.DAG):
    def __init__(self, nodeType=OboTerm):
        # nodeType should be a subclass of OboTerm
        super(OboOntology, self).__init__()
        self.id2term = {}
        self.namespaces = {}
        self.relationshipTypes = {}
        self.header = {}
        self.nsRoots = {}
        self.nodeType = nodeType

    def getNamespaces(self):
        return list(self.namespaces.keys())

    def setAttribute(self, attr, value):
        if type(value) is list:
            if len(value) == 0:
                value = ""
            elif len(value) == 1:
                value = value[0]
        self.header[attr] = value

    def getAttribute(self, attr, dflt=""):
        return self.header.get(attr,dflt)

    def addTerm(self, id, name):
        t = self.id2term.get(id,None)
        if t is None:
            t = self.nodeType(id,name,self)
            self.id2term[id] = t
            self.addNode(t)
        return t

    def hasTerm(self, id):
        return id in self.id2term

    def getTerm(self, id):
        return self.id2term[id]

    def setTermAttribute(self, term, attr, value):
        if attr == "id":
            raise Exception("Cannot set id attribute.")
        if attr == "namespace":
            # everyone shares the same string obj
            value = self.namespaces.setdefault(value,value)
        if type(term) is str:
            term = self.getTerm(term)
        setattr(term,attr,value)

    def addRelationship(self, child, rel, parent):
        rel = self.relationshipTypes.setdefault(rel,rel)
        child = self.getTerm(child)
        parent = self.getTerm(parent)
        self.addEdge(parent, child, rel, checkCycles=False)

    def getRoot(self, ns=None):
        if len(self.nsRoots) == 0:
            self.cacheRoots()
        if ns is None:
            return list(self.nsRoots.values())
        else:
            return self.nsRoots[ns]

    def cacheRoots(self):
        '''
        Find/cache the root nodes. Ensure that namespaces and root nodes
        correspond one-to-one.
        '''
        for t in self.iterNodes():
            t.is_nsroot = False
        self.nsRoots.clear()
        for r in self.iterRoots():
            if r.is_obsolete:
                continue
            ns = r.namespace
            self.nsRoots.setdefault(r.namespace,[]).append(r)
            r.is_nsroot = True

        for ns in self.getNamespaces():
            if not ns in self.nsRoots:
                raise Excpetion("ERROR: no root node found for namespace " + str(ns))

#------------------------------------

#
# OboParser
#
# Rudimentary parser for OBO format files. Parses lines into groups
# called stanzas. Passes each stanza to a provided function that processes
# the stanza. A stanza is simply a dict mapping string keys to list-of-strings 
# values. 
#
# Example. Here's a stanza from an OBO file:
#
# [Term]
# id: GO:0000001
# name: mitochondrion inheritance
# namespace: biological_process
# def: "The distribution of ..." [GOC:mcc, PMID:10873824, PMID:11389764]
# exact_synonym: "mitochondrial inheritance" []
# is_a: GO:0048308 ! organelle inheritance
# is_a: GO:0048311 ! mitochondrion distribution
#
# Here's the dict that would be passed to the processing function:
#
# {
# "__type__" : [ "Term" ]
# "id" : [ "GO:0000001" ]
# "name" : [ "mitochondrion inheritance" ]
# "namespace" : [ "biological_process" ]
# "def" : [ '"The distribution ..." [GOC:mcc, PMID:10873824, PMID:11389764]' ]
# "exact_synonym" : [ '"mitochondrial inheritance" []' ]
# "is_a" : [ "GO:0048308 ! organelle inheritance", "GO:0048311 ! mitochondrion distribution" ]
# }
#
# Things to note about the stanza:
#    The stanza's type is passed under the pseudo key "__type__".
#    (The header stanza has no type.)
#    Lines in the file having the same key are combined into a list under that
#    key. E.g., the two "is_a" lines in the example.
#    ALL values in the dict are lists, even if only a single value is allowed by OBO.
#    The stanza dict is reused for each new stanza. Thus the user's processing
#    function must copy any needed information out of the stanza before returning.
#


TYPE = "__type__"

class OboParser(object):
    def __init__(self, stanzaProcessor):
        self.fd = None
        self.count = 0
        self.stanza = {}
        self.stanzaProcessor = stanzaProcessor

    def parseFile(self, file):
        if type(file) is str:
            self.fd = open(file, 'U')
        else:
            self.fd = file
        self.__go__()
        if type(file) is str:
            self.fd.close()

    def __finishStanza__(self):
        if len(self.stanza) > 0:
            self.count += 1
            if self.count == 1 and TYPE not in self.stanza:
                self.stanza[TYPE] = ["Header"]
            self.stanzaProcessor(self.stanza)
            self.stanza = {}

    def __parseLine__(self, line):
        if line.startswith("["):
            j = line.find("]",1)
            return (TYPE, line[1:j])
        else:
            j = line.find(":")
            return (line[0:j], line[j+1:].strip())

    def __addToStanza__(self, line):
        k,v = self.__parseLine__(line)
        self.stanza.setdefault(k, []).append(v)
        
    def __go__(self):
        self.stanza = {}
        self.count = 0
        for line in self.fd:
            if len(line.strip()) == 0:
                self.__finishStanza__()
            else:
                self.__addToStanza__(line)
        self.__finishStanza__()

#-----------------------------------
#
# An OboLoader parses an OBO file and returns the corresponding DAG.
#
class OboLoader(object):

    def __init__(self):
        self.parser = OboParser(self.processStanza)
        self.ontology = None
        self.cullObsolete = False
        self.loadMinimal = False
        self.defaultNamespace = "ontology." + str(id(self))
        self.nodeType = None

    def loadFile(self, file, cullObsolete=False, loadMinimal=False, config=None, nodeType=OboTerm):
        self.cullObsolete = cullObsolete
        self.loadMinimal = loadMinimal
        self.nodeType = nodeType
        self.ontology = OboOntology(nodeType=self.nodeType)
        self.ontology.config = config
        self.parser.parseFile(file)

        # Prune out any edges that cross namespaces.
        # (GO is going to start including edges between process 
        # and function at some point).
        def efilt(p,c,d):
            return p.namespace is not c.namespace
        DAG.SimplePruner(edgeFilt=efilt).go(self.ontology)

        return self.ontology

    def processStanza(self, stanza):
        stype = stanza["__type__"][0]
        if stype == "Term":
            self.processTerm(stanza)
        elif stype == "Header":
            self.processHeader(stanza)

    def processHeader(self,stanza):
        for (n,v) in stanza.items():
            self.ontology.setAttribute(n,v)
        self.defaultNamespace = stanza.get(
              'default-namespace', [self.defaultNamespace] )[0]


    def processTerm(self, stanza):
        is_obsolete = (stanza.get('is_obsolete',False)==['true'])
        if is_obsolete and self.cullObsolete:
            return
        id = stanza['id'][0]
        name = stanza['name'][0]
        t = self.ontology.addTerm(id,  stanza['name'][0])
        t.name = name
        t.is_obsolete = is_obsolete
        self.ontology.setTermAttribute(t,'namespace',stanza.get('namespace',[self.defaultNamespace])[0])
        for isa in stanza.get("is_a", []):
            (id2,name2) = list(map(str.strip,isa.split("!",1)))
            self.ontology.addTerm(id2, name2)
            self.ontology.addRelationship(id, "is_a", id2)
        for reln in stanza.get("relationship", []):
            tokens = reln.split("!",1)
            if len(tokens) != 2:
                continue
            (id2,name2) = list(map(str.strip, tokens))
            tokens = id2.split()
            if len(tokens) != 2:
                continue
            (rel,id2) = tokens
            if rel == "part_of" or "regulates" in rel:
                self.ontology.addTerm(id2, name2)
                self.ontology.addRelationship(id, rel, id2)
        if self.loadMinimal:
            return
        for attr, val in stanza.items():
            if attr not in ['id','name','namespace','relationship','is_a']:
                self.ontology.setTermAttribute(t, attr, val)

#------------------------------------
__loader__ = OboLoader( )
load = __loader__.loadFile

#------------------------------------

if __name__ == "__main__":
    o = load(sys.argv[1], True)
