#!/usr/bin/env python

import sys
import os
import cgi
import cgitb; cgitb.enable()

import libvlad
import tempfile
import atexit

def removeTempFile(file):
    os.remove(file)

def writeTempFile(contents):
    fd,name = tempfile.mkstemp()
    fp = os.fdopen(fd, 'w')
    fp.write(contents)
    fp.close()
    atexit.register( removeTempFile, name )
    return name

def handleUploads(form, args):
    aname = writeTempFile(form['annotUploadFile'].value)
    args.append("-a")
    args.append(aname)
    oname = form['annotOntolSelect'].value
    if oname == '__upload__':
	oname = writeTempFile(form['ontolUploadFile'].value)
    args.append("-o")
    args.append(oname)

def runVlad(form):
    args = []

    # config file
    cfgfile = os.path.abspath(os.path.join(os.path.dirname(__file__), "config.cfg"))
    args.append("-g")
    args.append(cfgfile)

    # when running as CGI, clean out temp files
    args.append("--cleanTempFiles")

    # run name
    if form.has_key("runname"):
	args.append("-R")
	args.append(form["runname"].value)

    # analysis type
    if form.has_key("analysis"):
	args.append("-y")
	args.append(form["analysis"].value)

    # annotation set
    if form.has_key("annotationset"):
	aset = form["annotationset"].value
	aset = aset.split(":",1)[0]
	if aset == "__upload__":
	    handleUploads(form, args)
	else:
	    args.append("-a")
	    args.append(aset)

    # evidence codes
    if form.has_key("eCodes"):
	ecs = form.getlist("eCodes")
	if len(ecs) == 1:
	    ecs = ecs[0].replace(","," ").split()
	val = ",".join(ecs)
	args.append("-x")
	args.append(val)

    # query sets
    i=0
    while True:
	qsname = 'qs'+str(i)
	qsfname = qsname+'file'
	qssname = qsname+'name'
	qscname = qsname+'color'
        if not form.has_key(qsname):
	    break
	qs = form[qsname]
	qsf = form[qsfname]
	if qsf.filename:
	    args.append("-q")
	    args.append(qsf.value)
	elif qs.value:
	    args.append("-q")
	    args.append(qs.value)
	else:
	    break
	#
	qsn = form[qssname].value
	if qsn:
	    args.append("-n")
	    args.append(qsn)
	#
	qsc = form[qscname].value
	if qsc:
	    args.append("-c")
	    args.append(qsc)
	i += 1
	    
    # universe set
    if form.has_key('usfname') and form['usfname'].filename:
	args.append("-u")
	args.append(form['usfname'].value)
    elif form.has_key('usids'):
	args.append("-u")
	args.append(form['usids'].value)
        
    # spreadsheet output enable
    if form.has_key("tExcel"):
	args.append("--tExcel")
    if form.has_key("tHtml"):
	args.append("--tHtml")
    if form.has_key("tText"):
	args.append("--tText")

    # graphic output enable
    if form.has_key("gEnable"):
	args.append("--gEnable")
    else:
        args.append("--gDisable")

    if form.has_key("gBackground"):
        args.append("--gBackground")
	args.append(form.getvalue("gBackground"))

    if form.has_key("gNodeColor"):
        args.append("--gNodeColor")
	args.append(form.getvalue("gNodeColor"))

    if form.has_key("gROI"):
        args.append("--gROI")
	args.append(form.getvalue("gROI"))

    if form.has_key("gMaxImgSize"):
        args.append("--gMaxImgSize")
	args.append(form.getvalue("gMaxImgSize"))

    if form.has_key("gLabelEnable"):
        args.append("--gLabelEnable")
    else:
        args.append("--gLabelDisable")

    if form.has_key("gLimitBy"):
        limitby = form['gLimitBy'].value
	cutoff = form.getvalue("gValue")
	if limitby == "topn":
	    cutoff = str(abs(int(cutoff)))
	elif limitby == "topnlocal":
	    cutoff = str(-abs(int(cutoff)))
	elif limitby == "pval":
	    try:
		exp = -abs(int(cutoff))
		cutoff = str(10 ** exp)
	    except ValueError:
		cutoff = str(float(cutoff))
	args.append("--gCutoff")
	args.append(cutoff)

    if form.has_key("gCull"):
        args.append("--gCull")

    # write to stdout
    args.append("-O")
    args.append("-")

    try:
	libvlad.VladCGI().go(args)
    except:
	cgitb.handler()

def main():
    print "Content-type: text/html"
    print
    form = cgi.FieldStorage()
    if form.has_key('cmd'):
	cmd = form['cmd'].value
    else:
        raise RuntimeError("No command.")
    if cmd == "analyze":
        runVlad(form)
    else:
	raise RuntimeError("Vlad: unknown command: "+cmd)

#----------------------

main()
