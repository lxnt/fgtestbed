#!/usr/bin/python

import os, os.path, glob, sys, xml.parsers.expat, time, math, mmap
import numpy as np
NOMAT = 0xFFFFFFFF

class enumparser(object):
    def __init__(self, dfapipath):
        f = os.path.join(dfapipath, 'xml', 'df.tile-types.xml')
        self.enums = []
        self.gotit = False
        self.parse(f)

    def start_element(self, tagname, attrs):
        if tagname == 'enum-type' and attrs['type-name'] == 'tiletype':
            self.gotit = True
        elif tagname == 'enum-item' and self.gotit:
            try:
                self.enums.append(attrs['name'])
            except KeyError:
                self.enums.append(None)
                        
    def end_element(self, tagname):
        if tagname == 'enum-type' and self.gotit:
            self.gotit = False
            
    def char_data(self, data):
        pass

    def parse(self, fle):
        self.p = p = xml.parsers.expat.ParserCreate()
        p.StartElementHandler = self.start_element
        p.EndElementHandler = self.end_element
        p.CharacterDataHandler = self.char_data
        p.Parse(file(fle).read())
        #print "max(tile_id) = {0}".format(len(self.enums))

def scan_mats(path):
    inorgs = []
    plants = []
    for f in glob.glob(os.path.join(path, '*.txt')):
        for l in file(f):
            if l[0] != '[':
                continue
            try:
                tag, tail = l[1:].split(':', 1)
            except ValueError:
                continue
            
            if tag == 'INORGANIC':
                inorgs.append(tail[:-2])
            elif tag == 'PLANT':
                plants.append(tail[:-2])
    
    
    #print "{0} inorgs, {1} plants".format(len(inorgs), len(plants))
    return (inorgs, plants) 



"""
class mapdump:
    def __init__(self, matsfile, tilesfile):
        self.plant_ids = {}
        self.inorg_ids = {}
        self.plant_names = {}
        self.inorg_names = {}



    def __str__(self):
        rv = ""
        z = 0
        uni = np.unique(self._binary_form)

        tab = {}
        i = 0
        for u in uni:
            tab[u] = "{:02x} ".format(i)
            i += 1
        print i
        for x in xrange(self._xdim):
            for y in xrange(self._ydim):
                rv += tab[self._binary_form[x,y,z]]
            rv += "\n"
        return rv

    def stats(self, tile_names):
        raise Broken
        mathash = {}
        grasshash = {}
        matseen = {}
        tileseen = {}
        now_map = False
        bofma = 0
        ttboth = {}
        totgra = 0
        totina = 0
        void = 0
        stone = 0
        nosto = 0 
        parti = {}

        for t in self._dumb_list:
            tiletype, stone, inorg, grass, gramount = t

            tt = tile_names[tiletype]
            grass_mat, inorg_mat, stone_mat = (None, None, None)
            if inorg != NOMAT:
                totina += 1
                inorg_mat = self.inorg_names[inorg]
                try:
                    matseen[inorg_mat] += 1
                except KeyError:
                    matseen[inorg_mat] = 1
            if stone != NOMAT:
                stone_mat = self.inorg_names[stone]
                try:
                    matseen[stone_mat] += 1
                except KeyError:
                    matseen[stone_mat] = 1
            else:
                nosto += 1
            if grass != NOMAT and gramount > 0:
                totgra += 1
                grass_mat = self.plant_names[grass]
                try:
                    matseen[grass_mat] += 1
                except KeyError:
                    matseen[grass_mat] = 1
            else:
                grass = NOMAT
            try:
                tileseen[tt] += 1
            except KeyError:
                tileseen[tt] = 1
            try:
                parti[(tt, stone_mat, inorg_mat, grass_mat)] += 1
            except KeyError:
                parti[(tt, stone_mat, inorg_mat, grass_mat)] = 1
                
            
        def print_totals(a_name, a_dict):
            print a_name
            a_idx = a_dict.keys()
            a_idx.sort(cmp=lambda x,y: cmp(a_dict[x], a_dict[y]))
            for k in a_idx:
                print k, a_dict[k]
        
        print_totals("tiles", tileseen)
        print_totals("inorgs/plants", matseen)
        print_totals("inorgs+plants", ttboth)
        print_totals("particulars", parti)
        print void, stone, nosto, bofma, totgra, totina
"""
    
class tilepage:
    def __init__(self, tpname):
        self.name = tpname
        self.file = None
        self.tdim = None
        self.pdim = None
        self.defs = {}

class matiles:
    def __init__(self, matname):
        self.name = matname
        self.prelimo = []
        self.tiles = {}
        self._first_frame = True
        self._blit = self._blend = self._glow = None
        self._frame = 0
        self._tname = None
        self._keyframe_start = False
        
    def xpand(self):
        frameseq = []
        white = (0xff, 0xff, 0xff, 0xff)
        for f in self.prelimo:
            
            blit, blend, glow, amt = f
            #print chr(blit[1] + blit[2]*16)
            #print repr(blit)
            
            if len(self.prelimo) > 1:
                nextbli, nextglo= self.prelimo[1][1:3]
            else:
                nextbli, nextglo = self.prelimo[0][1:3]
            if glow is not None:
                if nextbli is None:
                    if nextglo is None:
                        glow_to = white
                    else:
                        glow_to = nextglo
                else:
                    glow_to = nextbli
                dr = ( glow_to[0] - glow[0] ) / float(amt)
                dg = ( glow_to[1] - glow[1] ) / float(amt)
                db = ( glow_to[2] - glow[2] ) / float(amt)
                da = ( glow_to[3] - glow[3] ) / float(amt)
            for fno in xrange(amt):
                if blend is not None:
                    frameseq.append((blit, blend))
                elif glow is not None:
                    frameseq.append( (blit, 
                        ( glow[0] + dr*fno, 
                          glow[1] + dg*fno, 
                          glow[2] + db*fno, 
                          glow[3] + da*fno ) ) )
                else:
                    frameseq.append((blit, white))
        self.tiles[self._tname] = frameseq
        self.prelimo = []
    
    def tile(self, tname):
        if self._tname is not None:
            self.fin()
        self._tname = tname
        
    def fin(self):
        #print "fin(): {0} {1} {2} {3}".format(self.name, self._tname, len(self.prelimo), self._frame)
        if not self._keyframe_start:
            self.prelimo.append((self._blit, self._blend, self._glow, 128 - self._frame))
        #print repr(self.prelimo)
        self.xpand()
        #print repr(self.tiles[self._tname])
        #raise SystemExit
        self._frame = 0
        
    def blit(self, tpage, s, t):
        self._blit = (tpage, s, t)
        self._keyframe_start = False        
        
    def glow(self, rgba):
        self._blend = None
        self._glow = rgba
        self._keyframe_start = False
        
    def blend(self, rgba):
        self._blend = rgba
        self._glow = None
        self._keyframe_start = False
        
    def key(self, frames):
        if not self._keyframe_start:
            self.prelimo.append((self._blit, self._blend, self._glow, frames - self._frame))
        self._keyframe_start = True
        #print self._frame, frames
        self._frame = frames

class graphraws(object):
    def __init__(self, path):
        self.defs = {}
        self.pages = {}
        self.matiles = {}
        fl = glob.glob(os.path.join(path, '*.txt'))
        fl.sort()
        for f in fl:
            self._parseraw(file(f))
            
    def _tagparse(self, l):
        l = l.strip()
        if len(l) < 1 or l[0] != '[':
            return None
        l, unused = l[1:].split(']', 1)

        return l.split(':')
        
    def _parseraw(self, flo):
        def parse_rgba(f):
            if len(f) == 3:
                r = int(f[0],16) << 4
                g = int(f[1],16) << 4
                b = int(f[2],16) << 4
                a = 0xff
            elif len(f) == 6:
                r, g, b, a = int(f[:2], 16), int(f[2:4], 16), int(f[4:6], 16), 0xff
                a = 0xff
            elif len(f) == 8:
                r, g, b, a = int(f[:2], 16), int(f[2:4], 16), int(f[4:6], 16), int(f[6:8], 16)
            else:
                raise ValueError(f)
            return (r,g,b,a)
        defs = self.defs
        mats = self.matiles
        pagename = None
        tiledim = None
        pagedim = None
        matname = None
        in_tilepage = False
        in_material = False
        tilename = None
        tilecode = []
        skip_all = True
        for l in flo:
            f = self._tagparse(l)
            if f is None: 
                continue
            tag = f[0].upper()
            if tag == 'OBJECT':
                skip_all = f[1].upper() != 'FULL_GRAPHICS'
                
            if skip_all:
                matname = None
                continue
            
            if tag== 'TILE_PAGE':
                if matname is not None:
                    mats[matname].fin()
                    matname = None
                    mat = None
                in_tilepage = True
                pagename = f[1]
                self.pages[pagename] = tilepage(pagename)
                continue
            elif tag == 'MAT':
                in_material = True
                in_tilepage = False
                if matname is not None:
                    mats[matname].fin()
                matname = f[1].upper()
                mat = mats[matname] = matiles(matname)
                continue
            if in_tilepage:
                if tag == 'FILE':
                    self.pages[pagename].file = f[1]
                elif tag == 'TILE_DIM':
                    self.pages[pagename].tdim = (int(f[1]), int(f[2]))
                elif tag == 'PAGE_DIM':
                    self.pages[pagename].pdim = (int(f[1]), int(f[2]))
                elif tag == 'DEF':
                    if f[3] == '':
                        continue
                    elif len(f) == 4:
                        self.pages[pagename].defs[f[3]] = (int(f[1]), int(f[2]))
                    elif len(f) == 3:
                        idx = int(f[1])
                        s = idx % self.pages[pagename].pdim[1]
                        t = idx / self.pages[pagename].pdim[0]
                        self.pages[pagename].defs[f[2]] = ( s, t )
                    else:
                        raise ParseError
            elif in_material:
                if tag == 'TILE':
                    mat.tile(f[1])
                elif tag == 'BLIT':
                    if len(f) == 4:
                        pagename, s, t = f[1:]
                        s = int(s) ; t = int(t)
                    elif len(f) == 3:
                        pagename, defname = f[1:]
                        s, t = self.pages[pagename].defs[defname]
                    mat.blit(pagename, s, t)
                elif tag == 'BLEND':
                    mat.blend(parse_rgba(f[1]))
                elif tag == 'GLOW':
                    mat.glow(parse_rgba(f[1]))
                elif tag == 'KEY':
                    mat.key(int(f[1]))
        if matname is not None:
            mats[matname].fin()
        #print mats.keys()
        #for p in self.pages:
        #    print "{0}: {1:d} keys".format (p, len(self.pages[p].defs.keys()))

    def get(self):
        return self.pages, self.matiles

def enumaps(apidir):
    enums = enumparser(apidir).enums
    i = 0
    emap = {}
    for e in enums:
        if e is not None:
            emap[e] = i
        i += 1
    return enums, emap

