#
# dumpMPAnnotations.py
#
# Dumps a set of annotations from MGI in GAF format (which is
# the TAB-delimited format used for GO annotations.
#
# Usage:
#    python dumpMPAnnotations.py [-gene | -genotype] > outputfile
#
'''
    DB                  = 0     MGI
    DB_Object_ID        = 1     MGI:012345
    DB_Object_Symbol    = 2     Abc1r1
    Qualifier           = 3     blank or "NOT"
    GO_ID               = 4     MP:6543210
    DB_Reference        = 5     MGI:MGI:33445522
    Evidence_code       = 6     IMP
    With                = 7     ?
    Aspect              = 8     MP
    DB_Object_Name      = 9     Abc receptor beta 1
    DB_Object_Synonym   = 10
    DB_Object_Type      = 11    allele
    Taxon               = 12    taxon:10090
    Date                = 13    <date>
    Assigned_by         = 14    MGI
'''


import sys
import db
import time

if len(sys.argv) != 2 or sys.argv[1] not in ["-gene","-genotype"]:
    print("usage: %s -(gene|genotype)")
    sys.exit(-1)

which = sys.argv[1][1:]

date = time.asctime(time.localtime(time.time()))

HEADER = '''!gaf-version: 1.0
!
!Submission Date: %s
!Project_name: Mouse Genome Informatics (MGI)
!URL: http://www.informatics.jax.org/
!Contact Email: mgi-help@informatics.jax.org
!Funding: NHGRI of US National Institutes of Health
!
! NOTE: This file contains annotations of phenotype terms to genes.
! It is important to realize that phenotypic effects can depend on
! genetic background, and that the data in this file represent an
! aggregation of the actual data in MGI. 
!'''

if which == "gene":
    cmd = '''
    select distinct
        'MGI' as db,
        aa.accid as dboid,
        mm.symbol as dbosym,
        vav.qualifier as qualifier,
        vav.accID as termid,
        vev.jnumID as dbref,
        vev.evidenceCode as ecode,
        vev.inferredFrom as awith,
        'MP' as aspect,
        mm.name as dboname,
        '' as dbosyn,
        'gene' as dbotype,
        'taxon:10090' as taxon,
        vev.creation_date as adate,
        'MGI' as aby
    from 
        VOC_Annot_View vav,
        VOC_Evidence_View vev,
        MRK_Marker mm,
        ACC_Accession aa
    where
        vav._AnnotType_key = 1015
    and vav._Annot_key = vev._Annot_key
    and vav._Object_key = mm._marker_key
    and mm._marker_key = aa._object_key
    and aa._mgitype_key = 2
    and aa._logicaldb_key = 1
    and aa.preferred = 1
    and aa.private = 0
    order by aa.accid, vav.accID
    '''
else: # which == "genotype"
    cmd = '''
    select distinct
        'MGI' as db,
        gg._Genotype_key as dboid,
        gg._Genotype_key as dbosym,
        vav.qualifier as qualifier,
        vav.accID as termid,
        vev.jnumID as dbref,
        vev.evidenceCode as ecode,
        vev.inferredFrom as awith,
        'MP' as aspect,
        gg._Genotype_key as dboname,
        '' as dbosyn,
        'genotype' as dbotype,
        'taxon:10090' as taxon,
        vev.creation_date as adate,
        'MGI' as aby
    from 
        VOC_Annot_View vav,
        VOC_Evidence_View vev,
        GXD_Genotype gg
    where
        vav._AnnotType_key = 1002
    and vav._Annot_key = vev._Annot_key
    and vav._Object_key = gg._genotype_key
    ''' 

results = db.sql(cmd)
print(HEADER%date)
for r in results:
    row = [
        r['db'],
        r['dboid'],
        r['dbosym'],
        r['qualifier'] and r['qualifier'] or "",
        r['termid'],
        r['dbref'],
        r['ecode'],
        r['awith'] and r['awith'] or "",
        r['aspect'],
        r['dboname'],
        r['dbosyn'],
        r['dbotype'],
        r['taxon'],
        r['adate'],
        r['aby'],
        ]
    print('\t'.join(map(str,row)))

