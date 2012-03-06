#!/usr/bin/python

import os, os.path, glob, sys, xml.parsers.expat, time, math, mmap, pprint
import traceback, stat, copy
import numpy as np
import pygame.image

def parse_color(f):
    if len(f) == 3:
        r = int(f[0],16) << 4
        g = int(f[1],16) << 4
        b = int(f[2],16) << 4
    elif len(f) == 6:
        r, g, b = int(f[:2], 16), int(f[2:4], 16), int(f[4:6], 16)
    else:
        raise ValueError(f)
    return (r<<24)|(g<<16)|(b<<8)|0xff

class ParseError(Exception):
    pass

class CompileError(Exception):
    pass

class DfapiEnum(object):
    def __init__(self, dfapipath, name):
        names2files = {
            'tiletype': 'df.tile-types.xml',
            'building_type': 'df.buildings.xml',
            'furnace_type': 'df.buildings.xml',
            'workshop_type': 'df.buildings.xml',
            'construction_type': 'df.buildings.xml',
            'shop_type': 'df.buildings.xml',
            'siegeengine_type': 'df.buildings.xml',
            'trap_type': 'df.buildings.xml',
        }
        f = os.path.join(dfapipath, 'xml', names2files[name])
        self.enums = []
        self.emap = {}
        self.gotit = False
        self.name = name
        self.parse(f)

    def start_element(self, tagname, attrs):
        if tagname == 'enum-type' and attrs['type-name'] == self.name:
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
        i = 0
        for e in self.enums:
            if e is not None:
                self.emap[e] = i
            i += 1

    def __getitem__(self, key):
        if type(key) == int:
            return self.enums[key]
        else:
            return self.emap[key]
    
class Pageman(object):
    """ requires pygame.image to function. 
        just blits tiles in order of celpage submission to album_w/max_cdim[0] columns """
    def __init__(self, std_tileset, album_w = 2048, dump_fname = None):
        self.mapping = {}
        self.album = []
        self.album_w = self.album_h = album_w
        self.dump_fname = dump_fname
        self.surf = pygame.Surface( ( album_w, album_w ), pygame.SRCALPHA, 32)
        self.current_i = self.current_j = 0
        
        stdts = CelPage(None, ['std'])
        stdts.pdim = (16, 16)
        stdts.path = std_tileset
        stdts.surf = pygame.image.load(std_tileset)
        w,h = stdts.surf.get_size()
        stdts.cdim = (w/16, h/16)
        
        self.max_cdim = stdts.cdim
        
        self.i_span = self.album_w / self.max_cdim[0]
        
        self.eatpage(stdts)

    def eatpage(self, page):
        if page.cdim[0] != self.max_cdim[0] or page.cdim[1] != self.max_cdim[1]:
            raise ValueError("celpage {} has cels of other than std_cdim size({}x{} vs {}x{})".format(
                page.name, page.cdim[0], page.cdim[1], self.max_cdim[0], self.max_cdim[1]))
        page.load()
        for j in xrange(page.pdim[1]):
            for i in xrange(page.pdim[0]):
                self.mapping[(page.name, i, j)] = (self.current_i, self.current_j)
                dx, dy = self.current_i*self.max_cdim[0], self.current_j*self.max_cdim[1]
                sx, sy = i*page.cdim[0], j*page.cdim[1]
                cell = pygame.Rect(sx, sy, page.cdim[0], page.cdim[1])
                self.surf.blit(page.surf, (dx, dy), cell)
                self.current_i += 1
                if self.current_i == self.i_span:
                    self.current_i = 0
                    self.current_j += 1
                    if self.current_j * self.max_cdim[1] > self.album_h:
                        self.reallocate(1024)
        if self.dump_fname:
            f.close()
    def dump(self, fname):
        sk = self.mapping.keys()
        sk.sort()
        with file(fname + '.mapping', 'w') as f:
            for k in sk:
                f.write("{}:{}:{} -> {}:{} \n".format(
                        k[0], k[1], k[2], self.mapping[k][0], self.mapping[k][1]))
        pygame.image.save(self.surf, fname + '.png')
        
    def reallocate(self, plus_h):
        self.album_h  += plus_h
        surf = pygame.Surface( ( self.album_w, self.album_h  ), pygame.SRCALPHA, 32)
        self.surf.set_alpha(None)
        surf.blit(self.surf, (0, 0))
        self.surf = surf

    def maptile(self, page, ref):
        page = self.pages[pagename]
        if len(ref) == 1:
            try:
                tmp = int(ref[0])
            except ValueError: # must be a def
                s, t = page.defs[ref[0]]
            except TypeError: # must be an (s,t) tuple
                s, t  = map(int, ref)
            else: # it's an index.
                s = tmp % page.pdim[0]
                t = tmp / page.pdim[1]
    
        return self.mapping[(page, s, t)]

    def get_album(self):
        "returns txsz tuple and bytes for the resulting texture album"
        min_h = self.max_cdim[1]*(self.current_j + 1)
        if min_h < self.album_h:
            self.reallocate(min_h - self.album_h)
        cw, ch = self.max_cdim
        wt, ht = self.album_w/cw, min_h/ch
        return (wt, ht, tw, th), pygame.image.tostring(self.surf, 'RGBA')

""" raws fmt:
    [OBJECT:objtag] defines what tag defines an 'object'
    [objtag:objname] starts an object
    rest of tags belong to that object.

    assumes []: are never used in literals.
    don't see any examples to the contrary in 34. 2 raws

    [GRASS_TILES:'.':',':'`':''']
    [GRASS_COLORS:2:0:1:2:0:0:6:0:1:6:0:0]    
    [TREE_TILE:23][DEAD_TREE_TILE:255]
    [TREE_COLOR:2:0:1][DEAD_TREE_COLOR:6:0:0]
    [SAPLING_COLOR:2:0:1][DEAD_SAPLING_COLOR:6:0:0]
    [PICKED_TILE:3][DEAD_PICKED_TILE:182]
    [SHRUB_TILE:28][DEAD_SHRUB_TILE:28]
    [PICKED_COLOR:5:0:0]
    [SHRUB_COLOR:5:0:0][DEAD_SHRUB_COLOR:6:0:0] """

class TSCompiler(object):
    """ compiles parsed standard tilesets """
    def __init__(self, pageman, colortab):
        self.matiles = {}
        self.colortab = colortab
        self.pageman = pageman

    def mapcolor(self, color):
        try:
            return ( self.colortab[color[0]+8*color[2]], self.colortab[color[1]] )
        except IndexError:
            raise ValueError("unknown color {}".format(repr(color)))

    def compile(self, materialsets, tilesets, celeffects, buildings):
        for materialset in materialsets:
            x = []
            for tileset in materialset.tilesets:
                x.append(tilesets[tileset])
            materialset.tilesets = x
            if len(materialset.tiles) > 0:
                d = Tileset('TILESET', ['__IMPLIED'])
                for tile in materialset.tiles:
                    d.add(tile)
                materialset.tilesets.append(d)
                
        for materialset in materialsets:
            print "MATSET", materialset
            for tileset in materialset.tilesets:
                tlist =  tileset.tiles
                for tile in tlist:
                    if materialset.klass == 'NONE':
                        self._emit_none(tile)
                    elif materialset.klass == 'INORGANIC':
                        self._emit_inorg(tile, materialset)
                    elif materialset.klass == 'PLANT':
                        self._emit_plant(tile, materialset)
                    elif materialset.klass == 'DERIVED':
                        self._emit_inorg(tile, materialset)
                    else:
                        raise CompileError("unknown mat class '{}'".format(materialset.klass))
        return self.matiles
    
    def dump(self, fname):
        with file(fname + '.ir', "w") as f:
            if False:
                f.write(pprint.pformat(self.stone_tiles))
                f.write(pprint.pformat(self.soil_tiles))
                f.write(pprint.pformat(self.mineral_tiles))
                f.write(pprint.pformat(self.grass_tiles))
                f.write(pprint.pformat(self.constr_tiles))
                f.write("\n\n")
        
            for mat, mati in self.matiles.items():
                for tn, fs in mati.tiles.items():
                    blit = fs[0][0]
                    if len(fs[0]) == 3:
                        f.write("{} {} {} {:08x} {:08x}\n".format(mat, tn, blit, fs[0][1], fs[0][2]))
                    else:
                        f.write("{} {} {} {:08x}\n".format(mat, tn, blit, fs[0][1]))

                    

    def _apply_effect(self, effect, color):
        if type(effect) in (list,tuple) and len(effect) == 3:
            # modify classic color
            rv = effect
            efg, ebg, ebr = effect
            if efg == "fg":
                rv[0] = color[0]
            elif efg == "bg":
                rv[0] = color[1]
            if ebg == "fg":
                rv[1] = color[0]
            elif ebg == "bg":
                rv[1] = color[1]
            if ebr == 'br':
                rv[2] = color[2]
            return rv
        else:
            # return presumably rgba value
            return effect
    
    def _emit_inorg(self, tile, materialset):
        for mat in materialset.mat_stubs:
            try:
                mt = self.matiles[mat.name]
            except KeyError:
                mt = Mattiles(mat.name)
                self.matiles[mat.name] = mt

            mt.tile(tile.name)
            
            if tile.cel is None: # make celdef from material data
                tile.cel = Cel(None, [mat.page, mat.tile])
            mt.expand(tile.cel)
    
    def _emit_plant(self, tile, materialset):
        for mat in materialset.mat_stubs:
            try:
                mt = self.matiles[mat.name]
            except KeyError:
                mt = Mattiles(mat.name)
                self.matiles[mat.name] = mt
                
            print mt, mat, tile
            return
            for ttype, tdef in mat.tiles.items():
                mt.tile(self.plant_tile_types[ttype][0])
                if tdef.tile is None:
                    if tdef.page != 'std':
                        raise ValueError('default tiles work only in standard tileset')
                    s, t = self.plant_tile_types[ttype][1], self.plant_tile_types[ttype][2]
                else:
                    s, t = tdef.tile%16, tdef.tile/16
                
                mt.blit(self.pageman.maptile(mat.page, s, t))
                mt.blend(self.mapcolor(tdef.color))
            mt.fin()

    def _emit_none(self, tile):
        print 'nonemat', tile
        return
        
class mat_stub(object):
    def __init__(self, page, **kwargs):
        self.type = None
        if page is None:
            page = 'std'
        self.page = page
        for k,v in kwargs.items():
            setattr(self,k,v)
    def __str__(self):
        try:
            name = self.name
        except AttributeError:
            name = None
        return "{}:{}".format(self.klass, name)

class Rawsparser0(object):
    def parse_file(self, fna, handler):
        lnum = 0
        for l in file(fna):
            lnum += 1
            l = l.strip()
            tokens = l.split(']')[:-1]
            for token in tokens:
                if len(token) == 0:
                    continue
                if token[0] != '[':
                    break
                try:
                    name, tail = token.split(':', 1)
                    name = name[1:].upper()
                    tail = tail.split(':')
                    if name not in  ( 'FILE', 'FONT' ):
                        tail = map(lambda x:x.upper(), tail)
                except ValueError:
                    name = token[1:].upper()
                    tail = []
                try:
                    handler(name, tail)
                except StopIteration:
                    return
                except :
                    print "{}:{}".format(fna, lnum)
                    print l
                    traceback.print_exc(limit=32)
                    raise SystemExit

    def tileparse(self, t):
        try:
            return int(t)
        except ValueError:
            pass
        if  (len(t) != 3 and 
              (t[0] != "'" or t[2] != "'")):
            raise ValueError("invalid literal for tile: \"{}\"".format(t))
        return ord(t[1])

    def eat(self, *paths):
        final = []
        numit = 0
        limit = 1024
        nextpaths = [32]
        while len(nextpaths) > 0 and numit < limit:
            nextpaths = []
            for path in paths:
                numit += 1
                if stat.S_ISDIR(os.stat(path).st_mode):
                    nextpaths += glob.glob(os.path.join(path, '*'))
                elif path.endswith('.txt'):
                    final.append(path)
            paths = nextpaths

        if numit == limit:
            raise RuntimeError("{} paths scanned: something's wrong".format(numit))

        for f in final:
            self.parse_file(f, self.parse_token)
        self.fin()


    def fin(self):
        pass

class Initparser(Rawsparser0):
    def __init__(self, dfprefix):
        init = os.path.join(dfprefix, 'data', 'init', 'init.txt')
        colors = os.path.join(dfprefix, 'data', 'init', 'colors.txt')
        self.dfprefix = dfprefix
        self.colortab = [0xff]*16
        self.fontpath = None
        self.parse_file(init, self.init_handler)
        self.parse_file(colors, self.colors_handler)
    
    def colors_handler(self, name, tail):
        colorseq = "BLACK BLUE GREEN CYAN RED MAGENTA BROWN LGRAY DGRAY LBLUE LGREEN LCYAN LRED LMAGENTA YELLOW WHITE".split()
        cshift = { 'R': 24, 'G': 16, 'B': 8, 'A': 0 }        
        color, channel = name.split('_')
        self.colortab[colorseq.index(color)] = self.colortab[colorseq.index(color)] | int(tail[0])<< cshift[channel]
        
    def init_handler(self, name, tail):
        if name == 'FONT':
            self.fontpath = os.path.join(self.dfprefix, 'data', 'art', tail[0])
            raise StopIteration


class TSParser(Rawsparser0):
    """ parses standard game raws 
        outputs whatever materials are defined there """
    template_delimiters = ( 'USE_MATERIAL_TEMPLATE', 'BASIC_MAT', 'EXTRACT_BARREL',
        'DRINK', 'SEED','MILL', 'TREE', 'LEAVES', 'EXTRACT_STILL_VIAL', 'THREAD',
        'EXTRACT_VIAL')
    def __init__(self, templates, materialsets):
        self.all = []
        self.otype = None
        self.mat = None
        self.base_mat = None
        self.materialsets = materialsets
        self.templates = templates
        #print templates
        #print materialsets

    def select(self, mat):
        for sel in self.materialsets:
            sel.match(mat)

    def parse_token(self, name, tail):
        if name == 'OBJECT':
            if tail[0] not in ['INORGANIC', 'PLANT']:
                raise StopIteration
            self.otype = tail[0]
            return

        if self.otype == 'INORGANIC':
            if name == 'INORGANIC':
                if self.mat:
                    self.select(self.mat)
                self.mat = mat_stub('std', name = tail[0], klass=name, others = [])
            elif name == 'TILE':
                self.mat.tile = self.tileparse(tail[0])
            elif name == 'DISPLAY_COLOR':
                self.mat.color = map(int, tail)
            elif name == 'USE_MATERIAL_TEMPLATE':
                if len(tail) != 1:
                    raise ParseError('2-parameter USE_MATERIAL_TEMPLATE in INORGANIC: WTF?.')
                self.mat.color =  self.templates[tail[0]].color
                self.mat.others = self.templates[tail[0]].others
            elif name not in self.mat.others:
                self.mat.others.append(name)
                
        elif self.otype == 'PLANT':
            if name == 'PLANT':
                if self.base_mat is not None:
                    raise ParseError('USE_MATERIAL_TEMPLATE delimiter missing.')
                if self.mat:
                    self.select(self.mat)
                self.mat = mat_stub('std', name = tail[0], klass=name, others = [], tiles={}, colors={}, color=None)
            elif name == 'GRASS_TILES':
                i = 0
                tiles = map(self.tileparse, tail)
                for tile in tiles:
                    try:
                        self.mat.tiles[i].tile = tile
                    except KeyError:
                        self.mat.tiles[i] = mat_stub('std', tile = tile, others = [])
                    i += 1
            elif name == 'GRASS_COLORS':
                i = 0
                colors = map(int, tail)
                fgs = colors[0::3]
                bgs = colors[1::3]
                brs = colors[2::3]
                for fg in fgs:
                    color = (fg,bgs.pop(0),brs.pop(0))
                    try:
                        self.mat.tiles[i].color = color
                    except KeyError:
                        self.mat.tiles[i] = mat_stub('std', color = color, others = [])
                    i += 1
            elif name == 'USE_MATERIAL_TEMPLATE':
                if len(tail) != 2:
                    raise ParseError('Non-2-parameter USE_MATERIAL_TEMPLATE in PLANT: WTF?.')
                if self.base_mat is not None:
                    #print "implicitly delimited template in {}, skipping".format(self.base_mat.name)
                    #self.mat.name = "{} {}".format(self.base_mat.name, 'SOAP')
                    #print 'emitted ', self.mat.name
                    #self.select(self.mat)
                    self.mat = self.base_mat
                self.base_mat = self.mat
                self.mat = mat_stub('std', klass = 'DERIVED', 
                    others = self.templates[tail[1]].others, 
                    color = self.templates[tail[1]].color)
            elif name in self.template_delimiters:
                if name == 'BASIC_MAT': # merge base_mat and mat
                    self.base_mat.others += self.mat.others
                    self.base_mat.color = self.mat.color
                else: # emit derived mat. 
                    self.mat.name = "{} {}".format(self.base_mat.name, name)
                    #print 'emitted ', self.mat.name
                    self.select(self.mat)
                    
                self.mat = self.base_mat
                self.base_mat = None
            elif name == 'DISPLAY_COLOR':
                self.mat.color = map(int, tail)
            elif name.endswith('_TILE'):
                self.mat.others.append(name)
                ttype = name[:-5]
                tile = self.tileparse(tail[0])
                #print 'base ', self.base_mat, 'mat', self.mat
                try:
                    self.mat.tiles[ttype].tile = tile
                except KeyError:
                    self.mat.tiles[ttype] = mat_stub('std', tile = tile, others = [])
            elif name == 'STATE_COLOR':
                return
            elif name.endswith('_COLOR'):
                self.mat.others.append(name)
                ttype = name[:-6]
                color = map(int, tail)
                try:
                    self.mat.tiles[ttype].color = color
                except KeyError:
                    self.mat.tiles[ttype] = mat_stub('std', color = color, 
                        tile = None, others = [])
            else:
                self.mat.others.append(name)
                    
            

    def get(self):
        self.select(self.mat)
        return self.materialsets


class Token(object):
    tokens = ()
    parses = ()
    contains = ()
    ignores_unknown = False
    def __init_(self, name, tail):
        self.name = name
        
    def add(self, token):
        pass
        
    def parse(self, name, tail):
        pass

class CelPage(Token):
    tokens = ('CEL_PAGE', 'TILE_PAGE')
    parses = ('FILE', 'CEL_DIM', 'TILE_DIM', 'PAGE_DIM', 'DEF')
    def __init__(self, name, tail):
        self.name = tail[0]
        self.file = None
        self.cdim = None
        self.pdim = None
        self.defs = {}
        self.surf = None
    def __str__(self):
        return '{}:{}:{}x{}:{}x{}'.format(self.name, self.file, 
            self.pdim[0], self.pdim[1], self.cdim[0], self.cdim[1])
    def parse(self, name, tail):
        if name == 'FILE':
            self.file = tail[0]
        elif name in ('CEL_DIM', 'TILE_DIM'):
            self.cdim = (int(tail[0]), int(tail[1]))
        elif name == 'PAGE_DIM':
            self.pdim = (int(tail[0]), int(tail[1]))
        elif name == 'DEF':
            if len(tail) == 4:
                self.page.defs[tail[2]] = (int(tail[0]), int(tail[1]))
            elif len(tail) == 3:
                idx = int(tail[0])
                s = idx % self.page.pdim[1]
                t = idx / self.page.pdim[0]
                self.defs[tail[1]] = ( s, t )
            else:
                raise ValueError("Incomprehensible DEF")
                
    def load(self):
        if not self.surf:
            surf = pygame.image.load(self.path)
            surf.convert_alpha()
            surf.set_alpha(None)
            self.surf = surf
        w,h = self.surf.get_size()
        if w != self.cdim[0]*self.pdim[0] or h != self.cdim[1]*self.pdim[1]:
            raise ValueError("size mismatch on {}: dim={}x{} pdim={}x{} cdim={}x{}".format(
                self.file, w, h, self.pdim[0], self.pdim[1], self.cdim[0], self.cdim[1]))

class CelEffect(Token):
    tokens = ('EFFECT', )
    parses = ('COLOR', )
    
    def __init__(self, name, tail):
        self.name = tail[0]

    def parse(self, name, tail):
        if name == 'COLOR':
            self.color = tail[0].split(',')
            return True
            
    def apply(self, color):
        rv = []
        for k in self.color:
            if k == 'fg':
                rv.append(color[0])
            elif k == 'bg':
                rv.append(color[1])
            elif k == 'br':
                rv.append(color[2])
            else:
                ev.append(int(k))

class Tile(Token):
    tokens = ( 'TILE', )
    contains = ( 'CEL', )

    def __init__(self, name, tail):
        self.name = tail.pop(0)
        self.cel = None
        if len(tail) > 0: # embedded celdef
            self.add(Cel(None, tail))
            
    def add(self, token):
        if type(token) == Cel:
            self.cel = token
            return True
            
    def __str__(self):
        return "TILE({}, {})".format(self.name, str(self.cel))
        
        
class Tileset(Token):
    tokens = ('TILESET', )
    contains = ('TILE', )
    
    def __init__(self, name, tail):
        self.name = tail[0]
        self.tiles = []
        
    def add(self, token):
        if type(token) == Tile:
            self.tiles.append(token)
            return True

    def __str__(self):
        return "TILESET({})".format(self.name)

class Keyframe(object):
    def __init__(self, number, idef = []):
        self.no = number
        self.page = None # used for blit, but kept separate
        self.blit = None # or idx (int), or s,t (int, int) , or def (str)
        self.effect = None # or str
        self.blend = 'MAT' # or None, or fg,bg,br (int, int, int) or rgbx,rgbx (int,int) or rgbx value (int)
        self.glow = False # or True.
        
        # parse inline celdef
        if len(idef) == 1:
            if idef[0] == 'MAT':
                self.blit = 'MAT' # material-defined tile from std tileset
            elif idef[0] != 'NONE':
                raise ParseError("bad inline celdef '{}'".format(idef[0]))
        elif len(idef) == 2:# ( page, idx or def) or (mat, effect)
            if idef[0] == 'MAT':
                self.blit = 'MAT'
                self.effect = idef[1]
            else:
                self.page = idef[0]
                try:
                    self.blit = int(idef[1])
                except ValueError:
                    self.blit = idef[1]
        elif len(idef) == 3: # page, s, t or page, idx, effect
            self.page = idef[0]
            try:
                self.blit = ( int(idef[1]), int(idef[2]) )
            except ValueError:
                self.blit = int(idef[1])
                self.effect = idef[2]
        elif len(idef) == 4: # page, s, t, effect
            self.page = idef[0]
            self.blit = ( int(idef[1]), int(idef[2]) )
            self.effect = idef[3]

    def blit(self, cref):
        assert type(color) in ( list, tuple )
        self.page = cref[0]
        self.blit = cref[1:]

    def blend(self, color):
        assert type(color) in ( list, tuple )
        if len(color) == 1:
            self.blend = parse_rgba(color[0])
        elif len(color) == 2:
            self.blend = (parse_rgba(color[0]), parse_rgba(color[1]))
        elif len(color) == 3:
            self.blend = map(int, color)
        
    def glow(self):
        self.glow = True


def emit_basic_frame(blit, blend):
    return ''

def interpolate_keyframes(self, thisframe, nextframe, material, pageman, colormap):    
    frameseq = []
    white = (0xff, 0xff, 0xff, 0xff)
    length = nextframe.no - thisframe.no
    no = 0
    while no < length:
        no += 1
    for f in self.prelimo:
        blit, blend, glow, amt = f
        
        if len(self.prelimo) > 1:
            nextble, nextglo= self.prelimo[1][1:3]
        else:
            nextble, nextglo = self.prelimo[0][1:3]
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

class Cel(Token):
    tokens = ('CEL', )
    parses = ( 'BLIT', 'BLEND', 'GLOW', 'KEY' )
    
    def __init__(self, name, tail):
        self.frames = []
        if len(tail) != 0:
            self.frames.append(Keyframe(0, tail))
            self.current_frame = None
        else:
            self.current_frame = Keyframe(0)
    
    def parse(self, name, tail):
        if name == 'BLIT':
            self.current_frame.blit(tail)
        elif name == 'BLEND':
            self.current_frame.blend(tail)
        elif name == 'GLOW':
            self.current_frame.glow()
        elif name == 'KEY':
            frameno = int(tail[0])
            if frameno < self.current_frame.no:
                raise ParseError("can't go backwards in time")
            self.frames.append(self.current_frame)
            self.current_frame = Keyframe(int(tail[0]))

    def expand(self, material, pageman, colormap, maxframes):
        # loop cel's frames to get maxframes frames
        rv = []
        frameno = 0
        
        while frameno < len(self.frames):
            f = self.frames[frameno]
            try:
                nextf = self.frames[frameno+1]
            except IndexError:
                nextf = self.frames[-1]
            rv += interpolate_frames(f, nextf, material, pageman, colormap)
            frameno += 1

        while  len(rv) < maxframes:
            rv += rv
        return rv[:maxframes]
                
            

    def __str__(self):
        return "CEL({} frames)".format( len(self.frames) )

class MaterialSet(Token):
    tokens = ('MATERIAL', )
    parses = ('TILESETS', 'CLASSIC_COLOR', 'BUILDINGS' )
    contains = ('TILE', )
    def __init__(self, name, tail):
        if tail[0] == 'none':
            self.nomat = True
            self.klass = 'nomat'
            return
        self.nomat = False
        if tail[0] not in ( 'INORGANIC', 'PLANT', 'NONE', 'DERIVED' ):
            raise ParseError("unknown material class " + tail[0])
        self.klass = tail[0]
        self.tokenset = tail[1:]
        self.tiles = []
        self.tilesets = []
        self.mat_stubs = []
        self.default_color = None
        self.buildings = False
        
    def add(self, token):
        if type(token) == Tile:
            self.tiles.append(token)
            return True

    def parse(self, name, tail):
        if name == 'TILESETS':
            self.tilesets += tail
            return True
        elif name == 'BUILDINGS':
            self.buildings = True
        elif name == 'COLOR_CLASSIC':
            self.default_color = tail[0].split(',')

    def match(self, mat):
        if self.klass != mat.klass:
            return False
        matched = False
        for token in self.tokenset:
            if token[0] == '!':
                if token[1:] in mat.others:
                    return False
            elif token in mat.others:
                matched = True
        if matched:
            self.mat_stubs.append(mat)
        return matched

    def __str__(self):
        rv =  "MATERIAL(class={}, tokenset={}, defcolor={}, emits={})\n".format(
            self.klass, self.tokenset, self.default_color, map(str, self.tilesets) )
        for m in self.mat_stubs:
            rv += "  "+m.name
        return rv

class Building(Token):
    tokens = ('BUILDING', )
    parses = ('DIM', 'COND', 'STATE')
    contains = ('CEL', )
    def __init__(self, name, tail):
        self.name = tail[0]
        self.current_def = []
        self.dim = (1,1)
        
    def add(self, token):
        if type(token) == Cel:
            self.current_def.append(token)
            return True
        
    def parse(self, name, tail):
        if name == 'DIM':
            pass
    
class CustomWorkshop(Token):
    """this is to handle DF's custom workshops (building_custom.txt)"""
    tokens = ('BUILDING_WORKSHOP',)
    parses = ('DIM', 'NAME', 'NAME_COLOR', 'WORK_LOCATION',
                'BUILD_LABOR', 'BUILD_KEY', 'BUILD_ITEM', 
                'BLOCK', 'TILE', 'COLOR')

    def __init__(self, name, tail):
        self.type = tail[0]
        
    def parse(self, name, tail):
        pass
        
class FullGraphics(Token):
    tokens = ('OBJECT',)
    contains = ( 'TILESET', 'EFFECT', 'CEL_PAGE', 
                 'TILE_PAGE', 'MATERIAL', 'BUILDING' )
            
    def __init__(self, name, tail):
        if tail[0] != 'FULL_GRAPHICS':
            raise StopIteration
        self.toplevel_tileset = Tileset(None, '__toplevel__')
        self.tilesets = {}
        self.materialsets = []
        self.celpages = []
        self.celeffects = {}
        self.buildings = {}
        
    def add(self, token):
        if type(token) == Tileset:
            self.tilesets[token.name] = token
        elif type(token) == Tile:
            self.toplevel_tileset.add(token)
        elif type(token) == CelEffect:
            self.celeffects[token.name] = token
        elif type(token) == CelPage:
            self.celpages[token.name] = token
        elif type(token) == MaterialSet:
            self.materialsets.append(token)
        elif type(token) == Building:
            self.buildings[token.name] = token
        elif type(token) == FullGraphics:
            return False
        else:
            raise ParseError("unexpected token at top level: " + repr(token))
        return True
    
    def __str__(self):
        rv = ''
        rv += 'tilesets: {}\n'.format(' '.join(self.tilesets.keys()))
        rv += 'celeffects: {}\n'.format(' '.join(self.celeffects.keys()))
        rv += 'celpages: {}\n'.format(' '.join(map(lambda x: x.name, self.celpages)))
        rv += 'materials: {}\n'.format(' '.join(map(lambda x: x.klass, self.materials)))
        rv += 'buildings: {}\n'.format(' '.join(self.buildings.keys()))
        
        return rv

class MaterialTemplates(Token):
    tokens = ('OBJECT',)
    contains = ( 'MATERIAL_TEMPLATE',)
                 
    def __init__(self, name, tail):
        if tail[0] != 'MATERIAL_TEMPLATE':
            raise StopIteration
        self.templates = {}
    
    def add(self, token):
        if type(token) == MaterialTemplate:
            self.templates[token.name] = token    
    
class MaterialTemplate(Token):
    tokens = ('MATERIAL_TEMPLATE',)
    parses = ('DISPLAY_COLOR', 'IS_METAL','WOOD','BONE', 'LEATHER', 'SOAP')
    ignores_unknown = True

    def __init__(self, name, tail):
        self.name = tail[0]
        self.color = None
        self.others = []
        
    def parse(self, name, tail):
        if name == 'DISPLAY_COLOR':
            self.color = map(int, tail)
        elif name in self.parses:
            self.others.append(name)
        

class AdvRawsParser(Rawsparser0):
    """ container tokens:
        
        toplevel: tile tileset material building effect
        
        x cel_page: file page_dim tile_dim cel_dim def
        x cel: blit blend glow key
        x tile: cel
        x tileset: tile
        x effect: color
        material: emit tile
        building: cel dim state c
        
        non-container tokens:
        color c state dim blit blend glow key emit file page_dim tile_dim cel_dim def """
        
    def __init__(self, *klasses):
        self.dispatch = {}
        self.stack = []
        self.set = []
        self.root = None
        self.loud = False
        for klass in klasses:
            for tokname in klass.tokens:
                self.dispatch[tokname] = klass

    def parse_token(self, name, tail):
        self.loud = False
        if name == 'VERSION': # ugly kludge
            return
        if len(self.stack) == 0:
            # it will be our root object
            try:
                if not self.root:
                    self.root = self.dispatch[name](name, tail)
            except KeyError:
                # unknown root token in a file: skip whole file
                raise StopIteration
            self.stack.append(self.root)
            return True
        
        # see if current object can handle the token itself.        
        if name in self.stack[-1].parses:
            self.stack[-1].parse(name, tail)
            return True
        
        if self.loud: print "{} does not parse {}".format(self.stack[-1].__class__.__name__, name)
        
        # see if current object is eager to contain it
        if name in self.stack[-1].contains:
            o = self.dispatch[name](name, tail)
            self.stack.append(o)
            if self.loud: print "{} contains {}".format(self.stack[-1].__class__.__name__, name)
            return True
        
        if self.loud: print "{} does not contain {}".format(self.stack[-1].__class__.__name__, name)
        
        if self.loud: print 'stack: {}'.format( ' '.join(map(lambda x: x.__class__.__name__, self.stack)))

        # so it's an unknown token for this level. see if we're to ignore it
        if self.stack[-1].ignores_unknown:
            een = False
            for s in self.stack:
                if name in s.tokens:
                    een = True
            if not een:
                return not een

        if len(self.stack) == 1: # got root only.
            # insidious kludge. :(
            try:
                o = self.dispatch[name](name, tail)
            except KeyError:
                # NEH aka HFS
                raise ParseError("unknown token '{}'".format(name))
            if type(o) == type(self.root):
                return True
            raise ParseError("WTF")

        o = self.stack.pop(-1)
        if self.stack[-1].add(o):
            if self.loud: print "{} accepted {}".format(self.stack[-1].__class__.__name__, o.__class__.__name__) 
        else:
            if self.loud: print "{} did not accept {}".format(self.stack[-1].__class__.__name__, o.__class__.__name__) 
        
        # continue unwinding stack until we've put the token somewhere.
        self.parse_token(name, tail)
        return
        """        
        if self.stack:
            print "{} not in {}'s parses".format(name, self.stack[-1].__class__.__name__)
        try: 
            # either stack is empty, or its top object
            # refused to parse it.
            # see if the token is to generate an object
            o = self.dispatch[name](name, tail)
        except KeyError:
            # unknown token: ignore it.
            print "ignoring " + name
            return
        
            
        if type(o) == type(self.root):
            # special case for OBJECT tokens
            # reset stack to contain root only
            self.stack = [ self.root ]
            return
        
        #print self.stack[-1].__class__.__name__, name
        # show the object to the top object on the stack,
        # maybe it's interested.
        orig_stack = copy.copy(self.stack)
        try:
            while not self.stack[-1].add(o):
                self.stack.pop(-1)
        except IndexError:
            print 'stack: {}'.format( ' '.join(map(lambda x: x.__class__.__name__, orig_stack)))
            raise
            
        # add() returns True if the object is ok to be contained, 
        # so push it onto the stack
        
        self.stack.append(o)
        """

    def fin(self):
        if self.loud: print 'fin stack: {}'.format( ' '.join(map(lambda x: x.__class__.__name__, self.stack)))
        
        try:
            self.stuff = self.stack[0]
        except IndexError:
            self.stuff = None

    def get(self):
        return self.stuff

class CreaGraphics(Token):
    tokens = ('CREATURE_GRAPHICS',)
    parses = tuple(
        """ADMINISTRATOR ADVISOR ALCHEMIST ANIMAL_CARETAKER ANIMAL_DISSECTOR
           ANIMAL_TRAINER ARCHITECT ARMORER AXEMAN BABY BARON BARON_CONSORT
           BEEKEEPER BLACKSMITH BLOWGUNMAN BONE_CARVER BONE_SETTER BOOKKEEPER
           BOWMAN BOWYER BREWER BROKER BUTCHER CAPTAIN CAPTAIN_OF_THE_GUARD
           CARPENTER CHAMPION CHEESE_MAKER CHIEF_MEDICAL_DWARF CHILD CLERK
           CLOTHIER COOK COUNT COUNT_CONSORT CRAFTSMAN CROSSBOWMAN DEFAULT
           DIAGNOSER DIPLOMAT DOCTOR DRUID DRUNK DUKE DUKE_CONSORT DUNGEON_KEEPER
           DUNGEON_LORD DUNGEONMASTER DUNGEON_MASTER DUNGEON_NASTER DYER
           ENGINEER ENGRAVER EXECUTIONER FARMER FISH_CLEANER FISH_DISSECTOR
           FISHERMAN FISHERY_WORKER FORCED_ADMINISTRATOR FURNACE_OPERATOR
           GEM_CUTTER GEM_SETTER GENERAL GHOST GLASSMAKER GLAZER GRAND_TREASURER
           GUILDREP HAMMERMAN HERBALIST HIGH_PRIEST HOARDMASTER HUNTER JEWELER
           KING KING_CONSORT LASHER LEADER LEATHERWORKER LIEUTENANT LYE_MAKER
           MACEMAN MANAGER MASON MASTER_AXEMAN MASTER_BLOWGUNMAN MASTER_BOWMAN
           MASTER_CROSSBOWMAN MASTER_HAMMERMAN MASTER_LASHER MASTER_MACEMAN
           MASTER_PIKEMAN MASTER_SPEARMAN MASTER_SWORDSMAN MASTER_THIEF
           MASTER_WRESTLER MAYOR MECHANIC MERCHANT MERCHANTBARON MERCHANTPRINCE
           METALCRAFTER METALSMITH MILITIA_CAPTAIN MILITIA_COMMANDER MILKER
           MILLER MINER MONARCH OUTPOSTLIAISON OUTPOST_LIAISON 
           PHILOSOPHER PIKEMAN PLANTER POTASH_MAKER POTTER PRESSER PRIEST PRISONER
           PSYCHIATRIST PUMP_OPERATOR RANGER RECRUIT SHEARER SHERIFF SHOPKEEPER
           SIEGE_ENGINEER SIEGE_OPERATOR SKELETON SLAVE SOAP_MAKER SPEARMAN SPINNER
           STANDARD STONECRAFTER STONEWORKER STRAND_EXTRACTOR SURGEON SUTURER SWORDSMAN
           TANNER TAXCOLLECTOR TAX_COLLECTOR THIEF THRESHER TRADER TRAINED_HUNTER
           TRAINED_WAR TRAPPER TREASURER WAX_WORKER WEAPONSMITH WEAVER WOOD_BURNER
           WOODCRAFTER WOODCUTTER WOODWORKER WRESTLER ZOMBIE""".split())

    def __init__(self, name, tail):
        self.race = tail[0]
        self.default = {}
        self.tax_escort = {}
        self.skeleton = {}
        self.law_enforce = {}
        self.zombie = {}
        self.ghost = {}
        
    def parse(self, name, tail):
        ctype = name
        variant = tail.pop(-1)
        asis = tail.pop(-1)
        cel = tail
        if variant == "DEFAULT":
            self.default[ctype] = (cel, asis)
        elif variant == "TAX_ESCORT":
            self.tax_escort[ctype] = (cel, asis)
        elif variant == "LAW_ENFORCE":
            self.law_enforce[ctype] = (cel, asis)
        elif variant == "SKELETON":
            self.skeleton[ctype] = (cel, asis)
        elif variant == "ZOMBIE":
            self.zombie[ctype] = (cel, asis)
        elif variant == "GHOST":
            self.ghost[ctype] = (cel, asis)
        else:
            raise ValueError("unknown variant '{}'".format(variant))

class CreaGraphicsSet(Token):
    tokens = ( 'OBJECT', )
    contains = ('CREATURE_GRAPHICS', 'TILE_PAGE', 'CEL_PAGE')

    def __init__(self, name, tail):
        if tail[0] != 'GRAPHICS':
            raise StopIteration
        self.pages = []
        self.cgraphics = {}
            
    def add(self, token):
        if type(token) == CelPage:
            self.pages.append(token)
            return True
        elif type(token) == CreaGraphics:
            self.cgraphics[token.race] = token
            return True

def work(dfprefix, fgraws, dumpfile=None):
    init = Initparser(dfprefix)
    stdraws = os.path.join(dfprefix, 'raw')
    pageman = Pageman(init.fontpath)
    
    mtparser = AdvRawsParser( MaterialTemplates, MaterialTemplate )
    fgparser = AdvRawsParser( FullGraphics, CelEffect, Tile, Tileset, CelPage, Cel, Building, MaterialSet )
    gsparser = AdvRawsParser( CreaGraphics, CreaGraphicsSet, CelPage )
    
    map(mtparser.eat, [stdraws])
    map(gsparser.eat, [stdraws])
    map(fgparser.eat, fgraws)
    
    mtset = mtparser.get()
    fgdef = fgparser.get()
    cgset = gsparser.get()
    
    stdparser = TSParser(mtset.templates, fgdef.materialsets)
    map(stdparser.eat, [stdraws])
    materialsets = stdparser.get()
    
    
    for page in fgdef.celpages: # + cgset.celpages: uncomment when creatures become supported
        self.pageman.eatpage(page)
    
    #print str(fgdef)
    #print "\n".join(map(lambda x: str(x), cgset.pages))
    compiler = TSCompiler(pageman, init.colortab)
    matiles = compiler.compile(materialsets, fgdef.tilesets, fgdef.celeffects, fgdef.buildings)
    
    if dumpfile:
        compiler.dump(dumpfile)
        pageman.dump(dumpfile)
    maxframe = 0
    return pageman, matiles, maxframe


def main():
    p,m,ma = work(sys.argv[1], sys.argv[2:], 'matidu') 
    

if __name__ == '__main__':
    main()

