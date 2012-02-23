#!/usr/bin/python

import os, os.path, glob, sys, xml.parsers.expat, time
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

def hashit(tile, stone, ore = NOMAT, grass = NOMAT, gramount = NOMAT):
    #mildly esoteric in the presense of NOMAT.
    # it seems grass & layer stone are mutex by tiletype.
    # so we just do:
    if gramount:
        stone = grass
        ore = NOMAT
    # and define GrassWhatEver tiles within only plant materials
    
    # Also since we don't have a plan how to compose ore/cluster tiles yet:
    if ore != NOMAT:
        stone = ore
        ore = NOMAT

    return ( ( (ore +1) & 0x3ff ) << 20 ) | ( ( (stone + 1) & 0x3ff ) << 10 ) | ( ( tile & 0x3ff ) ) 

class mapdump:
    def __init__(self, fname):
        self.plant_ids = {}
        self.inorg_ids = {}
        self.plant_names = {}
        self.inorg_names = {}

        self._xdim = 96
        self._ydim = 96
        self._zdim = 16
        
        self._binary_form = np.zeros((self._xdim, self._ydim, self._zdim), "i4")
        self._dumb_list = []
        
        self._parse(fname)


    def _parse(self, mapfile):

        now_map = False
        origin = None
       
        for l in file(mapfile):
            if l == 'now map\n':
                now_map = True
                continue
            f = l.split()
            if not now_map:
                if f[1] == 'INORG':
                    self.inorg_names[int(f[0])] = ' '.join(f[2:])
                    self.inorg_ids[' '.join(f[2:])] = int(f[0])
                elif f[1] == 'PLANT':
                    self.plant_names[int(f[0])] = ' '.join(f[2:])
                    self.plant_ids[' '.join(f[2:])] = int(f[0])
                continue

            x,y,z, tiletype, stone, inorg, grass, gramount = map(lambda x: int(x, 16), f)
            if origin is None:
                origin = (x,y,z)
            self._dumb_list.append((tiletype, stone, inorg, grass, gramount))
            self._binary_form[x-origin[0], y-origin[1], z-origin[2]] = hashit(tiletype, stone, inorg, grass, gramount)
            

    def stats(self, tile_names):
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
        
    def xpand(self):
        frameseq = []
        white = (0xff, 0xff, 0xff, 0xff)
        for f in self.prelimo:
            blit, blend, glow, amt = f
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
        self.prelimo.append((self._blit, self._blend, self._glow, 128 - self._frame))
        #print repr(self.prelimo)
        self.xpand()
        #print repr(self.tiles[self._tname])
        #raise SystemExit
        
        
    def blit(self, tpage, s, t):
        self._blit = (tpage, s, t)
        
    def glow(self, rgba):
        self._blend = None
        self._glow = rgba
        
    def blend(self, rgba):
        self._blend = rgba
        self._glow = None
        
    def key(self, frames):
        self.prelimo.append((self._blit, self._blend, self._glow, frames - self._frame))
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
                r = int(f[0]) << 4
                g = int(f[1]) << 4
                b = int(f[2]) << 4
                a = 0xff
            elif len(f) == 6:
                r, g, b, a = int(f[:2], 16), int(f[2:4], 16), int(f[4:6], 16), 0xff
                a = 0xff
            elif len(f[1]) == 8:
                r, g, b, a = int(f[:2], 16), int(f[2:4], 16), int(f[4:6], 16), int(f[6:8], 16)
            else:
                raise ParseError
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

mapfile = 'fugr.dump'
matdir = 'objects'
fgrawdir = 'fgraws'
pngdir = 'png'
apidir = ''

class preparer:
    def __init__(self):
        unused, self.tile_names = enumaps(apidir)
        self.gr = graphraws(fgrawdir) # read raws
        self.madpump = mapdump(mapfile) # read map, but only use 

    def eatpage(self, page):
        pass
    
    def maptile(self, blit):
        return 1, blit[1], blit[2], 0
    
    def first_stage(self):
        # all used data is available before first map frame is to be
        # rendered in game.
        # eatpage receives individual tile pages and puts them into one big one
        # maptile maps pagename, s, t into tiu, s, t  that correspond to the big one
        # tile_names map tile names in raws to tile_ids in game
        # inorg_ids and plant_ids map mat names in raws to effective mat ids in game
        # (those can change every read of raws)
        eatpage = self.eatpage
        maptile = self.maptile
        
        inorg_ids, plant_ids = self.madpump.inorg_ids, self.madpump.plant_ids
        
        _dt = np.dtype({
            'names': 'tiu s t un r g b a'.split(),
            'formats': ['u1', 'u1', 'u1', 'u1', 'u1', 'u1', 'u1', 'u1' ],
            'offsets': [0, 1, 2, 3, 4, 5, 6, 7 ],
            'titles': ['texture image unit', 's-coord in tiles', 't-coord in tiles', 'unused',
                       'blend-red', 'blend-blue', 'blend-green', 'blend-alpha']
                       })
        _dt = np.dtype({
            'names': 'tileidx r g b a'.split(),
            'formats': ['u4', 'u1', 'u1', 'u1', 'u1' ],
            'offsets': [0, 4, 5, 6, 7 ],
            'titles': ['tile index',
                       'blend-red', 'blend-blue', 'blend-green', 'blend-alpha']
                       })
        pages, mats = self.gr.get()
        
        for page in pages:
            eatpage(page)
        
        tcount = 0
        for mat in mats:
            tcount += len(mats[mat].tiles.keys())
        #print "{1} mats with {0} defined tiles".format(tcount, len(mats.keys()))
        if tcount <256:
            tx = 16
            ty = 16
            tz = 128
        else:
            return
        
        blitcode = np.zeros((tx, ty, tz), _dt)
        blithash = np.zeros((1024,1024), np.int32)
        tc = 0
            
        for name, mat in mats.items():
            if name in inorg_ids:
                mat_id = inorg_ids[name]
            elif name in plant_ids:
                mat_id = plant_ids[name]
            else:
                print  "no per-session id for mat '{0}'".format(name)
                continue
            for tname, frameseq in mat.tiles.items():
                tile_id = self.tile_names[tname]
                x = tc % tx
                y = tc / tx
                z = 0
                h = hashit(tile_id, mat_id) # not used with shader-based blithash
                blitcode_index = x << 16 | ( y & 0xFFFF )
                blithash[tile_id, mat_id] = blitcode_index # that's what each map frame shall consist of
                #print "mat: {0} tname: {1} len(frameseq): {2}".format(name, tname, len(frameseq))
                for insn in frameseq:
                    blit, blend = insn
                    tiu, s, t, un = maptile(blit)
                    r,g,b,a = blend
                    blitcode[x,y,z]['tileidx'] = tc
                    #blitcode[x,y,z]['s'] = s
                    #blitcode[x,y,z]['t'] = t
                    #blitcode[x,y,z]['un'] = un
                    blitcode[x,y,z]['r'] = r
                    blitcode[x,y,z]['g'] = g
                    blitcode[x,y,z]['b'] = b
                    blitcode[x,y,z]['a'] = a
                    z += 1
                tc += 1

        self.tx, self.ty, self.tz, self.blithash, self.blitcode = tx, ty, tz, blithash, blitcode

    def second_stage(self, z):    
        tx, ty, tz, blithash, blitcode = self.tx, self.ty, self.tz, self.blithash, self.blitcode
       
        # okay ...
        # that's how preparing frame for rendering should look like
        hashedview = self.madpump._binary_form # acquire map data, flatten and hash it..
        
        # the hash lookup is to be done in the shader.
        # decide if it's worth it moving it into separate render pass
        # esp since it's to be needed for multiple layers.
        def domap(a, b):
            return b.get(a, 0)
        vdomap = np.vectorize(domap, otypes=[np.int32])
        t = time.time()
        zview = hashedview[::,::,z]
        ready_frame = vdomap(zview, blithash)
        #print "domap: {0:.4f} sec".format(time.time() -t )
        return ready_frame   
    

if __name__ == '__main__':
    if sys.argv[1] == 'rep':
        enums, emap = enumaps(apidir)
        map = mapdump(mapfile)
        map.stats(enums)
    elif sys.argv[1] == 'parse':
        gr = graphraws(fgrawdir)
    elif sys.argv[1] == 'prep':
        p = preparer()
        p.first_stage()
        # upload texpages and the blitcode here.        
        f = p.second_stage(2)
        # render muthafuka!
        print f.shape
        
















