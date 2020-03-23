#
# Annotation.py
#

import sys
import types
import string

#------------------------------------------------------------------

# Define constants to make accessing specific fields a little easier.

class Annotation(object):

    DB			= 0
    DB_Object_ID	= 1
    DB_Object_Symbol	= 2
    Qualifier		= 3
    GO_ID		= 4
    DB_Reference	= 5
    Evidence_code	= 6
    With		= 7
    Aspect		= 8
    DB_Object_Name	= 9
    DB_Object_Synonym	= 10
    DB_Object_Type	= 11
    Taxon		= 12
    Date		= 13
    Assigned_by		= 14

    def __init__(self, tokens):
        self.tokens = tokens
	self.tokens[ self.Evidence_code ] = self.tokens[ self.Evidence_code ].upper()

    def getDb(self):
        return self.tokens[ self.DB ]

    def getObjId(self):
        return self.tokens[ self.DB_Object_ID ]

    def getObjSymbol(self):
        return self.tokens[ self.DB_Object_Symbol ]

    def getQualifier(self):
        return self.tokens[ self.Qualifier ]

    def getTermId(self):
        return self.tokens[ self.GO_ID ]

    def getEvidenceCode(self):
	return self.tokens[ self.Evidence_code ]

#------------------------------------------------------------------

class DBObject(object):
    '''
    An object that is the subject of an annotation. One distinct DBOject
    is created for each annotated object in an annotation set.
    '''
    def __init__(self, annot):
        self.db = annot.getDb()
	self.id = annot.getObjId()
	self.symbol = annot.getObjSymbol()

    def getId(self):
        return self.id

    def getDb(self):
        return self.db

    def getSymbol(self):
        return self.symbol

#------------------------------------------------------------------

class AnnotationSet(list):
    def __init__(self):
        list.__init__(self)
	self.attributes = {}
	self.comments = []
	self.id2dbobj = {}
	self.symbol2id = {}
	self.termid2annots = {}

    def getAttribute(self, attr, dflt="???"):
        return self.attributes.get(attr, dflt)

    def append(self, a):
        list.append(self, a)
	oid = a.getObjId()
	if oid not in self.id2dbobj:
	    dbo = DBObject(a)
	    self.id2dbobj[oid] = dbo
	    self.symbol2id[dbo.symbol] = oid
	self.termid2annots.setdefault(a.getTermId(), []).append(a)

    def getAnnotsForTerm(self, termid):
        return self.termid2annots.get(termid,[])

    def resolve(self, labels):
	'''
	Resolves a collection of ids and/or symbols (possibly with duplicates)
	into a set of distinct ids. Returns a tuple (ids, notfound), where
	ids is the set of distinct ids, and notfound is the set of labels
	that could not be resolved.
	'''
	ids = set()
	notfound = set()
        for lbl in labels:
	    if lbl in self.id2dbobj:
		# label is an id; add it to set.
	        ids.add(lbl)
	    elif lbl in self.symbol2id:
		# label is a symbol. add its id to set
	        ids.add(self.symbol2id[lbl])
	    else:
		# not found. add to notfound set
	        notfound.add(lbl)
	return (ids, notfound)

    def getDbObjects(self, idset):
	'''
	Gets the symbols corresponding to a set if ids. Returns a list of
	tuples of the form (id, symbol).
	'''
        lst = []
	for id in idset:
	    lst.append( self.id2dbobj[id] )
	return lst

#------------------------------------------------------------------

class AnnotationParser(object):
    '''
    Parser for GO annotation file format. This is a TAB-delimited ASCII
    file. Lines beginning with a "!" are either comments (if the second
    character is a space), attributes, or empty. E.g.:
 
    !Submission Date: 10/16/2009
    !
    ! The above "Submission Date" is when the annotation project provided ...

    All other lines are data lines having 15 columns. Details can be found here:

       http://www.geneontology.org/GO.format.annotation.shtml

    The user instantiates the parser with up to three callback functions:
       commentHandler(c)     - Called with the contents of each comment line (string).
       attributeHandler(n,v) - Called with each name, value attribute (string, string).
       annotHandler(a)       - Called with the parsed contents of each annotation line (list of 15 strings).
    '''
    def __init__(self, annotHandler=None, attributeHandler=None, commentHandler=None):
        self.annotHandler = annotHandler
	self.commentHandler = commentHandler
	self.attributeHandler = attributeHandler

    def parseFile(self, file):
        if type(file) is types.StringType:
	    self.fd = open(file, 'U')
	else:
	    self.fd = file
	self.__go__()
	if type(file) is types.StringType:
	    self.fd.close()

    def __parseannot__(self, line):
        tokens = line.split('\t')
	tokens[-1] = tokens[-1].strip()
	return Annotation(tokens)

    def __go__(self):
	for line in self.fd:
	    if line.startswith('! '):
	        self.commentHandler and self.commentHandler( line[2:] )
	    elif line.startswith('!'):
		if len(line) > 2 and self.attributeHandler:
		    try:
		        (n,v) = map(string.strip, line[1:].split(":",1))
		        self.attributeHandler(n,v)
		    except:
		        pass
	    elif self.annotHandler:
		self.annotHandler(self.__parseannot__(line))

#------------------------------------------------------------------

class AnnotationLoader(object):
    def __init__(self):
        self.parser = AnnotationParser(
	    annotHandler=self.__handleAnnot__,
	    attributeHandler=self.__handleAttribute__,
	    commentHandler=self.__handleComment__)

    def loadFile(self, file, config = None):
	self.annotations = AnnotationSet()
	self.annotations.config = config
        self.parser.parseFile(file)
	return self.annotations

    def __handleComment__(self, c):
        self.annotations.comments.append(c)

    def __handleAttribute__(self, attr, value):
	self.annotations.attributes[attr]=value

    def __handleAnnot__(self, annot):
	self.annotations.append(annot)

#------------------------------------------------------------------

__loader__ = AnnotationLoader()
load = __loader__.loadFile

#------------------------------------------------------------------

if __name__ == "__main__":
    a = load(sys.argv[1])

