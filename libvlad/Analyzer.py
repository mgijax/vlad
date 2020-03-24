#
# Analyzer.py
#

import types
import math
import sys

from . import DAG
from . import Stats

#-----------------------------------------------------

ENRICHMENT = "enrichment"
DEPLETION  = "depletion"
PERCENTAGE = "percentage"

#-----------------------------------------------------

class EnrichmentAnalyzer(object):
    #----------------------------------------------
    def __init__(self):
        self.cachedClosures = {}

    #----------------------------------------------
    def computeAnnotationClosure(self, ontology, namespace, annotations, excludeCodes, universe):
        '''
        Computes the closure of annotations over the given namespace.
        Returns a dictionary mapping each term
        to the set of objects (ids) annotated to that term or its
        descendants. Excludes "NOT" annotations and those
        whose evidence codes are in the excludCodes set. Closure
        computation only crosses "is_a" and "part_of" edges.
        Closures are cached and reused if possible.
        '''
        if universe is None:
            universe = []
        universe = frozenset(universe)
        excludeCodes = frozenset(excludeCodes)
        key = (ontology, namespace, id(annotations), excludeCodes, universe)
        ac = self.cachedClosures.get(key, None)
        if ac is None:
            def annotFilt(a):
                return a.getQualifier() != 'NOT' \
                   and a.getEvidenceCode() not in excludeCodes \
                   and (len(universe)==0 or a.getObjId() in universe)
            def edgeFilt(d):
                return d in ['is_a', 'part_of']
            startNodes = ontology.getRoot(namespace)
            ac = AnnotationClosure(annotations,annotFilt,edgeFilt).go(ontology, startNodes)
            self.cachedClosures[key] = ac
        return ac

    #----------------------------------------------
    def __analyze__(self, 
                qsid,           # string
                qset,           # set(string)
                universe,       # set(string)
                ontology,       # Ontology
                namespace,      # string
                annotations,    # AnnotationSet
                excludeCodes,   # set(string)
                termminmax,     # { term -> [minP, maxP] }
                analysis):      # "enrichment" or "depletion" or "percentage"
        '''
        Performs enrichment analysis for a given query set against a given 
        ontology+namespace, over a given annotation data set.
        Returns a tuple containing the set of query ids that were not found 
        in the annotation set, the list of results, and result statistics
        (e.g., counts and p-values).
        If analysis == "depletion", perform depletion analysis.
        If analysis == "percentage", simply computes the counts at each node and
        skips the rest (i.e., the hypergeometric calcs).
        '''
        # initialize results, universe set
        results = []
        # compute the annotation closure, a map from terms to all objects
        # annotated to terms or descendants
        annotClosure = self.computeAnnotationClosure(
                ontology,namespace,annotations,excludeCodes,universe)
        # universe set is set of objects annotated to the root
        uset = set()
        for sn in ontology.getRoot(namespace):
            uset |= annotClosure[sn]
        usize = len(uset)
        # {not found} = {query set} - {universe}
        notfound = qset - uset
        # actual qs size = number of found objects
        qssize = len(qset) - len(notfound)
        # compute results for every term...
        for (term, oset) in annotClosure.items():
            # all objects annotated to this term
            ossize = len(oset)
            if ossize == 0:
                # term has no annotations. skip...
                continue
            # subset of query items annotated to this term.
            aset = oset & qset
            assize = len(aset)
            if assize == 0:
                # no query items annotated to this term. Construct a "zero" record.
                # These are accumulated (in self.term2zeroResults) and added to
                # results later if needed. 
                pval = 1.0
                result = TermQSResult(qsid, term, [], qssize, ossize, usize,pval)
                self.term2zeroResults.setdefault(term,[]).append(result)
            else:
                # some query items are annotated to this term. Compute stats.
                # First, retrieve the db objects and sort them.
                alist = annotations.getDbObjects(aset)
                alist.sort(key=lambda x:x.symbol) # FIXME: symbol is hardcoded
                if DEPLETION.startswith(analysis):
                    # depletion analysis
                    pval = Stats.sum_hyperg2(len(alist), qssize, ossize, usize)
                elif ENRICHMENT.startswith(analysis):
                    # enrichment analysis
                    pval = Stats.sum_hyperg(len(alist), qssize, ossize, usize)
                elif PERCENTAGE.startswith(analysis):
                    # pct of query set annotated to term
                    pval = float(len(alist))/qssize

                # jer - 29 July 2011 - Add sanity check.
                # pval should never be identically 0 here, but it can be due
                # to machine precision limits. (Ought to be checked in Stats module.)
                if pval==0:
                    pval = Stats.MINFLOAT;

                # create the result record and append to results list
                result = TermQSResult( qsid, term, alist, qssize, ossize, usize, pval )
                results.append(result)
            # accumulate min/max p values for each term
            tmm = termminmax.setdefault(term, [1.0, 0.0])
            tmm[0] = min(tmm[0], result.pval)
            tmm[1] = max(tmm[1], result.pval)
            # end loop

        # Calculate Q-values from the P-values
        # First, sort by P-value.
        # Then compute Q-vals according to formula:
        #       Q[i] = (N * P[i]) / i
        # for i = 1 .. N, where N is number of P vals.
        if not analysis == "percents":
            results.sort(key = lambda x:x.pval)
            N = len(results)
            minx = 1.0
            for i in range(N,0,-1):
                r = results[i-1]
                x = (N*r.pval)/i
                minx = min(minx, x)
                r.qval = minx

        # return list of unfound items and list of result records.
        return (notfound,results)

    #----------------------------------------------
    def analyze(self, 
                qsets,          # [ set(id) ], query sets
                qsnames,        # [ string ], query set names
                universe,       # set(id), user-specified universe set, or None
                ontology,       # Ontology
                annotations,    # AnnotationSet
                excludeCodes=set(),  # set(string) - evidence codes to exclude
                analysis=ENRICHMENT ):
        '''
        Performs enrichment analysis for a list of query sets against a given ontology
        over a given set of annotations. 
        Returns a tuple, (notfound,results,term2results), where (1) notfound is a mapping 
        from namespace to list of sets of labels. The outer list contains one item
        per query set, a set of labels that were not found (id or symbol) in
        the AnnotationSet; (2) results is a mapping from namespace to a list of
        TermQSResult objects, sorted by term min p val;
        (3) term2results is a mapping from term to list of results.

        When there are multiple query sets, it will happen that for a given
        ontology term, some query sets will have annotations to that term
        and some query sets will have none. Vlad "fills in" result rows for 
        the "zero annotation" query sets, In other words, if a term has results
        for at least one query set, it will have results for all query sets.
        Vlad fills in "zero" records as necessary to make this happen. 
        Implementation: during analysis, we test whether a given term 
        has annotations (if k > 0). If k == 0, create a TermQSResult with
        zero counts (and a Pval of 1.0). These "zero result" records are
        stored in a mapping. After analyzing all query sets, go through
        list of "positive" results. For each term, if there are zero-result
        records in the mapping, add them to the results.
        '''
        notfound = {}   # { ns -> [ [string] ] }
        results = {}    # { ns -> [ TermQSResult ] }
        term2results={} # { ns -> { term -> [ TermQSResult ] } }
        termminmax = {} # { term -> [ minP, maxP ] }
        self.term2zeroResults = {} # { term -> [ TermQSResult(qsid,0) ] }
        #
        # first pass: for each ontology namespace (i.e., each dag) and query
        # set combination, analyze.
        #
        for ns in ontology.getNamespaces():
            notfound[ns] = []
            results[ns] = []
            term2results[ns] = t2r = {}
            for (i,qset) in enumerate(qsets):
                # analyze one query set against one namespace (DAG)
                qsnf, qsres = self.__analyze__(
                    qsnames[i], qset, universe, ontology,ns,annotations,excludeCodes,termminmax,analysis)
                notfound[ns].append(qsnf)
                results[ns] += qsres
                for r in qsres:
                    t2r.setdefault(r.term, []).append(r)
        #
        # second pass: add in "zero result" records, and
        # add term min/max pvals to every result.
        # Then sort results by min pval, term name, qsid.
        #
        for ns, nsresults in list(results.items()):
            toadd = []
            for r in nsresults:
                zrs = self.term2zeroResults.pop(r.term, None)
                if zrs is not None:
                    toadd.append(zrs)
            for ta in toadd:
                nsresults += ta
            for r in nsresults:
                tmm = termminmax[r.term]
                r.minpval = tmm[0]
                r.maxpval = tmm[1]
                r.pratio = r.minpval / r.maxpval
            nsresults.sort(key=lambda x: x.key(), reverse=(analysis==PERCENTAGE))

        # this can get pretty big, so make it avail for gc
        self.term2zeroResults = {}

        return (notfound, results, term2results)

#-------------------------------------------------------------------

class TermQSResult(object):
    '''
    Holds enrichment analysis results for one query set for one ontology term.
    '''
    def __init__(self, qsid, term, aList, qsSize, totAnnot, usSize, pval):
        self.qsid = qsid        # query set id
        self.term = term        # the ontology term
        self.aList = aList      # list of dbObjects annotated to this term
        self.k = len(self.aList)
        self.n = qsSize         # size of the query set
        self.K = totAnnot       # total num. of annotations to this term or desc.
        self.N = usSize         # size of universe set
        self.pval = pval        # my score
        self.qval = 1.0         # my FDR statistic (to be filled in later)
        self.e = pval > 0 and -math.log10(pval) or 0
        self.eRatio = 0.0       # self.e / global max e (to be filled in later)
        #
        self.minpval = self.pval # min/max over results for this term
        self.maxpval = self.pval # (replicated in each result for that term - ugh.)
        self.pratio = 1.0       # = min p / max p

    def key(self):
        return (self.minpval, self.term.name, self.qsid)

    def __cmp__(self, other):
        '''
        Define comparison fcn so that we can sort a list of results by P-value.
        Sort is multilevel:
            1. by min pval for the term
               2. by term name
                  3. by query set name
        '''
        delta = self.minpval - other.minpval
        if delta < 0:
            return -1
        elif delta == 0:
            nc = cmp(self.term.name, other.term.name)
            if nc != 0:
                return nc
            else:
                return cmp(self.qsid, other.qsid)
        else:
            return 1

#-------------------------------------------------------------------

class AnnotationClosure(DAG.Traversal):
    '''
    A traversal subclass that computes the closure of annotations to each
    term and its descendents. The result is a mapping from term to the
    set of annotated object ids. The traversal can be customized to avoid
    crossing certain edges and/or including certain annotations. To avoid
    crossing specific edges, specify edgeFilter in the constructor call.
    This is a function, f(p,c,d), which is passed each edge before crossing.
    The edge is passed as p=parent node, c=child node, d=edge data. The
    function should return True to cross the edge and False to not cross.
    Similarly, specific annotations can be excluded by passing annotFilter,
    a function, f(a), that is passed each annotation and returns True to
    include the annotation and False to exclude it.
    '''
    def __init__(self, 
                annots, 
                annotFilter = lambda x:True, 
                edgeFilter = lambda e: True):
        self.annots = annots
        self.annotFilter = annotFilter
        self.edgeFilter = edgeFilter
        self.term2objs = {}

    def beforeNode(self, dag, term, path):
        oset = set()
        for a in self.annots.getAnnotsForTerm(term.id):
            if self.annotFilter(a):
                oset.add(a.getObjId())
        self.term2objs[term] = oset

    def beforeEdge(self, dag, p, c, d, path):
        return self.edgeFilter(d)

    def afterEdge(self, dag, p, c, d, path):
        self.term2objs[p] |= self.term2objs[c]

    def getResults(self):
        return self.term2objs

#-------------------------------------------------------------------

__analyzer__  = EnrichmentAnalyzer()
analyze = __analyzer__.analyze
