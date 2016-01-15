#!/usr/bin/env python3
import argparse
import sys
#import codecs
from collections import defaultdict as dd
import re
import os.path
import gzip
from flask import Flask, url_for, request
import random
import utok
import tempfile
import os
import shutil
import atexit
import difflib
from subprocess import check_output, STDOUT, CalledProcessError, getoutput
scriptdir = os.path.dirname(os.path.abspath(__file__))

from flask_restful import Resource, Api
from flask.ext.cors import CORS
scriptdir = os.path.dirname(os.path.abspath(__file__))
archivedir = os.path.join(scriptdir, 'archive')

workdir = tempfile.mkdtemp(prefix=os.path.basename(__file__), dir=os.getenv('TMPDIR', '/tmp'))
def cleanwork():
    shutil.rmtree(workdir, ignore_errors=True)
atexit.register(cleanwork)

scrapefile=os.path.join(scriptdir, 'scrape.py')

app = Flask(__name__)

print("about to cors")
# this CORS wrapper is essential to prevent the ubiquitous CORS error!
CORS(app)
api = Api(app)

print("done with init")
class HelloWorld(Resource):
    def get(self):
        return {'hello': 'world'}

class NumberedLetters(Resource):
    def get(self):
        d = dd(lambda: dd(list))
        #d = dd(list)
        d['id-a']['grub']=[1,2]
        d['content']['blarg']='hello world'
#        d['foo']={}
        d['foo']['bar']=7
        return d


twokenizepath=os.path.join(scriptdir, 'twokenize.sh')
def twokenize(data):
    ''' kludgy wrap of cmu twokenize '''
    datafile, dfname=tempfile.mkstemp(prefix=os.path.basename(__file__), dir=workdir)
    datafile = open(dfname, 'wb')
    for line in data:
        datafile.write((line+"\n").encode('utf8'))
    datafile.close()
    cmd=twokenizepath+" "+dfname+" 2> /dev/null"
    tokres=check_output(cmd, shell=True).decode('utf8')
#    print(tokres)
    res = []
    for line in tokres.split('\n'):
        res.append(line.strip().split('\t')[0])
    os.remove(dfname)
    return res

cdectokpath=os.path.join(scriptdir, 'cdectok', 'tokenize-anything.sh')
def cdectok(data):
    ''' kludgy wrap of cmu cdectok '''
    datafile, dfname=tempfile.mkstemp(prefix=os.path.basename(__file__), dir=workdir)
    datafile = open(dfname, 'wb')
    for line in data:
        datafile.write((line+"\n").encode('utf8'))
    datafile.close()
    cmd=cdectokpath+" < "+dfname+" 2> /dev/null"
    tokres=check_output(cmd, shell=True).decode('utf8')
#    print(tokres)
    res = []
    for line in tokres.split('\n'):
        res.append(line.strip())
    os.remove(dfname)
    return res

tokenizations = [
    ('original', lambda x: x),
    ('utok', lambda x: list(map(utok.tokenize, x))),
    ('twokenize', twokenize),
    ('cdectok', cdectok)
]

seqmatch = difflib.SequenceMatcher()
def diffcodes(base, mod):
    ''' get list of list of opcodes '''
    ret = []
    for bstr, mstr in zip(base, mod):
        seqmatch.set_seqs(bstr, mstr)
        opcodes = seqmatch.get_opcodes()
        newopcodes = []
        for opcode in opcodes:
            substr = mstr[opcode[3]:opcode[4]]
            newopcodes.append(opcode+(substr,))
        ret.append(newopcodes)
    return ret

    
class SpecificSet(Resource):
    print("Class init")
    loaded = dd(lambda: dd(list))
    

    def setup(lang, date):
        if len(SpecificSet.loaded[date][lang]) == 0:
            print("Setting up %s/%s" % (date, lang))
            path=os.path.join(archivedir, date, lang, 'tweets.txt')
            fh = open(path, 'rb')
            lines = []
            for line in fh:
                SpecificSet.loaded[date][lang].append(line.decode('utf8').strip().split('\t')[2])
            print("%d lines read" % len(SpecificSet.loaded[date][lang]))

    def __init__(self, lang, date):
        self.lang = lang
        self.date = date
        SpecificSet.setup(lang, date)



    def get(self):
        print("Getting")
        d = dd(lambda: dd(list))
        lines = SpecificSet.loaded[self.date][self.lang]
        linelen=len(lines)
        numtweets=10
        selection = []
        for i in (range(numtweets)):
            choice = random.randint(0, linelen-1)
            item = lines[choice]
            selection.append(item)
        d['data']['length']=len(selection)
        for tokname, tokfun in tokenizations:
            tokres = tokfun(selection)
            d['data'][tokname]=tokres
            d['diffs'][tokname]=diffcodes(selection, tokres)

        return d

for thelang in ('Thai', 'Arabic', 'Indonesian', 'Spanish', 'Russian'):
    for thedate in ('20160103',):
        newurl = '%s_%s' % (thelang, thedate)
        api.add_resource(SpecificSet, '/'+newurl, endpoint=newurl, resource_class_args=(thelang, thedate))


api.add_resource(HelloWorld, '/')
api.add_resource(NumberedLetters, '/nl')

class GetWikis(Resource):
    def get(self):
        items = int(request.args.get('items'))
        lang = request.args.get('lang')
        if lang == 'random':
            langchoice = "--random"
        else:
            langchoice = "--code %s" % lang
        cmd=scrapefile+" --chars=140 %s --extracts=%d" % (langchoice, items)
        wikres = check_output(cmd, shell=True).decode('utf8')
        ret = []
        for line in wikres.split('\n'):
            toks = line.split('\t')
            if len(toks) >= 4:
                d = {'lang':toks[1], 'url':toks[2], 'text':toks[3]}
                selection = [toks[3],]
                tokresults = {}
                #print(selection[0])
                if len(selection[0]) == 0:
                    continue
                for tokname, tokfun in tokenizations[1:]:
                    tokres = tokfun(selection)
                    #print(tokres[0])
                    tokresults[tokname] = {}
                    tokresults[tokname]['data']=tokres[0]
                    tokresults[tokname]['diffs']=diffcodes(selection, tokres)[0]
                d['tokenizations']=tokresults
                ret.append(d)
        return ret

api.add_resource(GetWikis, '/wik')


    
if __name__ == '__main__':
    print("running")
    app.run(debug=True, host='0.0.0.0')

