#!/bin/env python

import sys
import types
import string
import os
import configparser

from libvlad import Vlad, VERSION

class VladInstaller(object):
    def __init__(self):
        self.srcDir = None
        self.dstConfigFile = None
        self.dstConfig = None
        self.logfd = sys.stderr

    def log(self, msg):
        self.logfd.write(msg)
        self.logfd.write('\n')

    def die(self, msg):
        self.log(msg)
        sys.exit(-1)

    def usage(self):
        self.die("usage: %s dest.cfg\n"%sys.argv[0])

    def readConfig(self, fname):
        cp = configparser.ConfigParser(defaults=os.environ)
        cp.read(fname)
        return cp

    def copy(self, src, target):
        asrc = os.path.abspath(src)
        atarget = os.path.abspath(target)
        if os.path.samefile(asrc, atarget):
            raise RuntimeError("Cannot copy %s to itself."%asrc)

    def system(self, cmd):
        self.log(cmd)
        os.system(cmd)

    def cp(self, src, dst, recursive=False, noclobber=False):
        r = ''
        if recursive:
            r = '-r'
        n = ''
        if noclobber:
            n = '-n'
        cmd = 'cp %s %s %s %s' % (r, n, src, dst)
        self.system(cmd)

    def ensureDirs(self, dirs):
        if type(dirs) is bytes:
            dirs = [dirs]
        for d in dirs:
            if not os.path.exists(d):
                self.log("Making directory: " + d)
                os.makedirs(d)

    def mkOntologyOptionList(self,oconfigs):
        opts = list(vars(oconfigs).values())
        opts.sort(key=lambda a:a.order)
        s = ''
        for o in opts:
            s += '<option value="%s"> %s (%s)</option>\n' % (o.name, o.label, o.name)
        return s

    def mkAnnotationSetOptionList(self, aconfigs):
        opts = list(vars(aconfigs).values())
        opts.sort(key=lambda a:a.order)
        s = ''
        for a in opts:
            selected = ''
            if s == "":
                selected = 'selected="true"'
            s += '<option value="%s:%s" %s> %s </option>\n' \
                % (a.name, a.ontology.name, selected, a.label)
        return s

    def mkEvidenceCodeSection(self, ecodes, id, dfltexclude):
        helpparts = []
        for i,e in enumerate(ecodes):
            helpparts.append(e+'; ')
            if i%3 == 2:
                helpparts.append('<br>')
        helpstring = ''.join(helpparts)
        tblParts = []
        for i,ec in enumerate(ecodes):
            if i%3 == 0:
                if tblParts:
                    tblParts.append('</tr>')
                tblParts.append('<tr>')
            parts = ec.split('=',1)
            code = parts[0]
            ckd = ''
            if code in dfltexclude:
               ckd='checked="true"'
            td = '<td><input name="eCodes" type="checkbox" %s value="%s">%s</td>' \
                % (ckd,code,code)
            tblParts.append(td)
        tblParts.append('</tr>')
        tblstring = '<table border="0">%s</table>'%(' '.join(tblParts))
        return (tblstring, helpstring)

    def mkColorList(self, config):
        clist = []
        if config.has_section('DOT') and config.has_option('DOT','qscolors'):
            clist = eval(config.get('DOT','qscolors'))
        return '\ncolorlist = ' + str(clist) + ';\n'

    def mkEvidenceCodeSections(self, oconfigs):
        '''
        Builds a JavaScript string which builds an object tree
        like this:
                obj
                   GO
                     tblString
                     helpString
                   MP
                     tblString
                     helpString
                   ...
        '''
        parts = ["var evidenceCodes = new Object();\n"]
        for oc in list(vars(oconfigs).values()):
            parts.append('evidenceCodes.%s = new Object();\n' % oc.name)
            if not hasattr(oc,'evidencecodes'):
                parts.append('evidenceCodes.%s.tblString = '';\n' % oc.name)
                parts.append('evidenceCodes.%s.helpString = '';\n' % oc.name)
            else:
                ecodes = [_f for _f in map(str.strip, oc.evidencecodes.split('\n')) if _f]
                dfltexclude = set()
                if hasattr(oc, 'defaultexcluded'):
                    dfltexclude = set(oc.defaultexcluded.split())
                t,h = self.mkEvidenceCodeSection(ecodes,oc.name, dfltexclude)
                parts.append("evidenceCodes.%s.tblString = '%s';\n" % (oc.name,t))
                parts.append("evidenceCodes.%s.helpString = '%s';\n" % (oc.name,h))
        parts.append('evidenceCodes.__upload__ = new Object();\n')
        parts.append("evidenceCodes.%s.tblString = '%s';\n" \
                % ("__upload__",'<br>&nbsp;<input type="text" name="eCodes">'))
        parts.append("evidenceCodes.%s.helpString = '%s';\n" \
                % ("__upload__","Enter list if codes separated by spaces and/or commas."))
        jsString = ''.join(parts)
        return jsString
            
    def writeCgi (self) :
        bash = self.dstConfig.get('VLAD', 'bash' )
        python = self.dstConfig.get('VLAD', 'python')
        cgiScriptFile = self.dstConfig.get('VLAD', 'scriptfile')
        cgiFile = os.path.join(self.dstCgiDir, cgiScriptFile)
        with open(cgiFile, 'w') as fd:
            fd.write('#!%s\nsource Configuration\n%s vlad.py\n' % (bash, python))
        os.chmod(cgiFile, 0o777)

    def main(self, argv):
        cfgfile = None
        installSamples = False
        if len(argv) == 2:
            cfgfile = argv[1]
        else:
            self.usage()

        self.srcDir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.srcLibDir = os.path.join(self.srcDir, "libvlad")
        self.srcStaticDir = os.path.join(self.srcDir, "www")
        self.srcConfiguration = os.path.join(self.srcDir, "Configuration")

        self.dstConfigFile = cfgfile
        self.dstConfig = self.readConfig(self.dstConfigFile)

        self.dstDir = self.dstConfig.get("VLAD","vladBuildDir")
        self.dstConfiguration = os.path.join(self.dstDir, "Configuration")

        self.dstCgiDir = self.dstConfig.get("VLAD","cgiDir")
        self.dstLibDir = os.path.join(self.dstCgiDir, "libvlad")
        self.dstOutputDir  = self.dstConfig.get("VLAD","outputDir")

        self.dstCgiUrl = self.dstConfig.get("VLAD","cgiUrl")

        if not os.path.exists(self.srcDir):
            die("source in not a directory:"+self.srcDir)

        if os.path.exists(self.dstDir) \
        and os.path.samefile(self.srcDir, self.dstDir):
            self.die("Cannot install vlad onto itself. Source " + \
                "and destination must be different. " + self.srcDir)

        self.ensureDirs( [
            self.dstDir,
            self.dstCgiDir,
            self.dstLibDir,
            self.dstOutputDir] )

        # make sure output directory is writable and readable
        if not os.access( self.dstOutputDir, os.F_OK|os.R_OK|os.W_OK|os.X_OK ):
            os.chmod(self.dstOutputDir, 0o777)

        # copy config file to installation dir
        dcf = os.path.join(self.dstCgiDir,"config.cfg")
        if not os.path.exists(dcf) \
        or not os.path.samefile(self.dstConfigFile, dcf):
            self.cp( self.dstConfigFile, dcf )
            self.cp( self.srcConfiguration, self.dstConfiguration )

        # copy the .py files from source lib dir to dest lib dir
        self.cp(os.path.join(self.srcLibDir, '*'), self.dstLibDir, recursive=True)

        # copy sample data files
        '''
        self.cp(
                os.path.join(self.srcDir, 'sampledata'), 
                os.path.join(self.dstDir, 'sampledata'), 
                recursive = True)
        '''

        # copy the static content files. Then read the index file
        # and substitute the correct cgi URL.
        self.cp(os.path.join(self.srcStaticDir, '*'), self.dstDir, recursive=True)
        self.writeCgi()
        self.cp(os.path.join(self.srcStaticDir, '.htaccess'), self.dstDir)

        fd = open(os.path.join(self.srcStaticDir, 'index.html'), 'r')
        content = fd.read()
        fd.close()

        v = Vlad()
        oconfigs = v.getOntologyConfig(self.dstConfig)
        aconfigs = v.getAnnotationSetConfig(self.dstConfig, oconfigs)
                    
        aol = self.mkAnnotationSetOptionList(aconfigs)
        ool = self.mkOntologyOptionList(oconfigs)
        jss = self.mkEvidenceCodeSections(oconfigs)
        jss += self.mkColorList(self.dstConfig)

        d = { 
            'vladVersion' : v.VERSION,
            'vladCgiUrl' : self.dstCgiUrl , 
            'vladAnnotationSetOptionList':aol,
            'vladJavaScriptString': jss,
            'vladOntologySelectList': ool,
            }
        content = content % d

        fd = open(os.path.join(self.dstDir, 'index.html'), 'w')
        fd.write(content)
        fd.close()
        self.log("wrote: " + fd.name)

#
if __name__ == "__main__":
    VladInstaller().main(sys.argv)
