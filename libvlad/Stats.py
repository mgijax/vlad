#
# Stats.py
#
# Statistical functions for Vlad. The primary one is sum_hyperg, which
# will compute the score for a given node:
#	score = Stats.sum_hyperg(k, n, K, N)
# where:
#	k = number of annotations of query set items to that node or its children
#	n = size of the query set
#	K = total number of annotations to that node or its descendants
#	N = size of universe set
#

import sys
import math

#-------------------------------------------------------------
def smallestFloat():
    try:
	# python 2.6 and later
	return sys.float_info.min
    except:
	# python pre-2.6
        x = 1.0/2
	while 0.0 + x != 0.0:
	    smallest = x
	    x /= 2.0
	return smallest

#-------------------------------------------------------------
# Negative infinity.
NEGINF = float('-inf')
# Smallest floating point value
MINFLOAT=smallestFloat()

#-------------------------------------------------------------
def logSum( logs ):
    '''
    Returns the log of the sum of a list of numbers, given
    the logs of those numbers. For working in log space.
    Algorithm from Gary Churchill, 12/3/2003.
    Args:
        logs	list of floats. The logs of a list of numbers
    Returns:
        float	The log of the sum of those numbers.
    '''
    n = len(logs)
    if n == 0:
        return NEGINF
    elif n == 1:
        return logs[0]
    maxn = max(logs)
    sum = -1.0
    for x in logs:
        sum += math.exp(x-maxn)
    return maxn + math.log(1.0 + sum)

#-------------------------------------------------------------
# Maintain a cache of log values for ints 0..n.
#
LOGCACHE = [NEGINF] + map( math.log, xrange(1,5000) )
LENLOGCACHE = len(LOGCACHE)

# Also maintain a cache of the sum of log(i) for i from  n to m
SUMLOGCACHE = {}

def sumLogs(start,end):
    '''
    Returns the sum of the logs of integers in the range
    from start .. end.
    '''
    global LOGCACHE, LENLOGCACHE, SUMLOGCACHE
    if end >= LENLOGCACHE:
        for i in xrange( len(LOGCACHE), end+1000 ):
	    LOGCACHE.append(math.log(i))
	LENLOGCACHE = len(LOGCACHE)

    key = (start,end)
    sum = SUMLOGCACHE.get(key, None)

    if sum is not None:
        return sum

    # This function is often called in sequence. Check the ranges that
    # are +/- 1 on either end. (This can be a BIG win.)
    sum=SUMLOGCACHE.get((start+1,end),None)
    if sum is not None:
	sum += LOGCACHE[start]
	SUMLOGCACHE[key] = sum
	return sum

    sum=SUMLOGCACHE.get((start,end-1),None)
    if sum is not None:
	sum += LOGCACHE[end]
	SUMLOGCACHE[key] = sum
	return sum

    sum=SUMLOGCACHE.get((start-1,end),None)
    if sum is not None:
	sum -= LOGCACHE[start-1]
	SUMLOGCACHE[key] = sum
	return sum

    sum=SUMLOGCACHE.get((start,end+1),None)
    if sum is not None:
	sum -= LOGCACHE[end+1]
	SUMLOGCACHE[key] = sum
	return sum

    # sigh...OK, if we must, we must...
    sum = 0.0
    for i in xrange(start, end+1):
	sum += LOGCACHE[i]
    SUMLOGCACHE[key] = sum
    return sum

#-------------------------------------------------------------

def log_nCm(n, m):
    '''
    Returns the log of n choose m. That is, returns
        log(n! / (m! (n-m)!))
    '''
    if n < 0 or m < 0:
        raise Exception("n and m must be >= 0")

    # By defn, if m>n, C(n,m) == 0, so return log(0)
    if m > n:
        return NEGINF

    # Simplify formula to one of two equivalents.
    # (Picks the one with fewer terms.)
    #    (n*(n-1)* ... *(n-m+1))/m!
    #    (n*(n-1)* ... *(m+1))/(n-m)!
    if m < n/2:
        return sumLogs( n-m+1, n ) - sumLogs( 1, m )
    else:
        return sumLogs( m+1, n ) - sumLogs( 1, n-m )

#-------------------------------------------------------------

def nCm(n, m):
    '''
    Returns n choose m, that is:
        n! / (m! (n-m)!)
    '''
    return math.exp(log_nCm(n,m))

#-------------------------------------------------------------

def log_hyperg( k, n, K, N ):
    '''
    Returns the log of the hypergeometric probability of having k out of n,
    given a population statistic of K out of N.
    Args:
        k	(int) Number of 'successes' in query set.
	n	(int) Size of the query set.
	K	(int) Number of successes in universe set.
	N	(int) Size of universe set.
    '''
    return log_nCm(K,k) + log_nCm(N-K, n-k) - log_nCm(N,n)

#-------------------------------------------------------------

def hyperg( k, n, K, N ):
    '''
    Returns the hypergeometric probability of having k out of n,
    given a population statistic of K out of N.
    Args:
        k	(int) Number of 'successes' in query set.
	n	(int) Size of the query set.
	K	(int) Number of successes in universe set.
	N	(int) Size of universe set.
    '''
    return math.exp( log_hyperg(k, n, K, N) )

#-------------------------------------------------------------

def sum_hyperg( k, n, K, N ):
    '''
    Returns the hypergeometric probability of having AT LEAST
    k out of n, given a population statistic of K out of N.
    '''
    if k == 0:
        return 1.0
    maxk = min(n,K)
    logProbs = (maxk-k+1)*[0.0]
    for i in xrange( k, maxk+1 ):
        logProbs[i-k] = log_hyperg( i, n, K, N )
    return math.exp(logSum(logProbs))

#-------------------------------------------------------------

def sum_hyperg2( k, n, K, N ):
    '''
    Returns the hypergeometric probability of having AT MOST
    k out of n, given a population statistic of K out of N.
    '''
    logProbs = (k+1)*[0.0]
    for i in xrange( k+1 ):
        logProbs[i] = log_hyperg( i, n, K, N )
    return math.exp(logSum(logProbs))

#-------------------------------------------------------------
def _test():
    k = int(sys.argv[1])
    n = int(sys.argv[2])
    K = int(sys.argv[3])
    N = int(sys.argv[4])
    print "hyperg(%d,%d,%d,%d) ="%(k,n,K,N), math.exp(log_hyperg(k,n,K,N))
    print "sum_hyperg(%d,%d,%d,%d) ="%(k,n,K,N), sum_hyperg(k,n,K,N)
    print "sum_hyperg2(%d,%d,%d,%d) ="%(k,n,K,N), sum_hyperg2(k,n,K,N)
    
#-------------------------------------------------------------
if __name__ == "__main__":
    _test()
