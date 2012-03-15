#!/usr/bin/python

import os, os.path, glob, sys, xml.parsers.expat, time, math, mmap, pprint
import traceback, stat, copy
import numpy as np
import pygame.image

DEFAULT_GRASS_COLOR = (2, 0, 1) # light-green

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
                self.enums.append(attrs['name'].upper())
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
        if type(key) in (long, int):
            return self.enums[key]
        else:
            return self.emap[key.upper()]
    
class Pageman(object):
    """ requires pygame.image to function. 
        just blits tiles in order of celpage submission to album_w/max_cdim[0] columns """
    def __init__(self, std_tileset, album_w = 2048, pages = []):
        self.mapping = {}
        self.pages = {}
        self.album_w = self.album_h = album_w
        self.surf = pygame.Surface( ( album_w, album_w ), pygame.SRCALPHA, 32)
        self.current_i = self.current_j = 0
        self.max_cdim = [0,0]
        
        self.i_span = self.album_w / 32 # shit
        
        for page in pages:
            self.eatpage(page)
        if 'STD' not in self.pages.keys():
            stdts = CelPage(None, ['std'])
            stdts.pdim = (16, 16)
            stdts.file = std_tileset
            stdts.surf = pygame.image.load(std_tileset)
            w,h = stdts.surf.get_size()
            stdts.cdim = (w/16, h/16)
            self.eatpage(stdts)

    def eatpage(self, page):
        if page.cdim[0] > self.max_cdim[0]:
            self.max_cdim[0] = page.cdim[0]
        if page.cdim[1] > self.max_cdim[1]:
            self.max_cdim[1] = page.cdim[1]
        page.load()
        for j in xrange(page.pdim[1]):
            for i in xrange(page.pdim[0]):
                self.mapping[(page.name.upper(), i, j)] = (self.current_i, self.current_j)
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
        self.pages[page.name.upper()] = page
        
    def dump(self, fname):
        sk = self.mapping.keys()
        sk.sort()
        with file(fname + '.mapping', 'w') as f:
            for k in sk:
                f.write("{}:{}:{} -> {}:{} \n".format(
                        k[0], k[1], k[2], self.mapping[k][0], self.mapping[k][1]))
        self.shrink()
        pygame.image.save(self.surf, fname + '.png')

    def shrink(self):
        min_h = self.max_cdim[1]*(self.current_j + 1)
        old_h = self.album_h
        if min_h < self.album_h:
            self.reallocate(min_h - self.album_h)
        
    def __str__(self):
        return 'pageman({})'.format(' '.join(self.pages.keys()))
        
    def reallocate(self, plus_h):
        self.album_h  += plus_h
        surf = pygame.Surface( ( self.album_w, self.album_h  ), pygame.SRCALPHA, 32)
        self.surf.set_alpha(None)
        surf.blit(self.surf, (0, 0))
        self.surf = surf

    def map(self, pagename, ref): # pagename comes in uppercased
        page = self.pages[pagename]
        if len(ref) == 1:
            try:
                tmp = int(ref[0])
            except ValueError: # must be a def
                s, t = page.defs[ref[0]]
            except TypeError:
                s, t = ref
            else: # it's an index.
                s = tmp % page.pdim[0]
                t = tmp / page.pdim[1]
        else:
            s, t = ref
        
        return self.mapping[(pagename, s, t)]

    def get_txsz(self):
        "returns txsz tuple"
        self.shrink()
        cw, ch = self.max_cdim
        wt, ht = self.album_w/cw, self.album_h/ch
        return (wt, ht, cw, ch)
        
    def get_data(self):
        "returns bytes for the resulting texture"
        return pygame.image.tostring(self.surf, 'RGBA')

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


class ObjectCode(object):
    def __init__(self, pageman, mapcolor, celeffects, maxframes):
        self.map = {}
        self.buildings = {}
        self.items = {}
        self.maxframe = 0
        self.maxframes = maxframes
        self.pageman = pageman
        self.mapcolor = mapcolor
        self.celeffects = celeffects

    def addtiles(self, mat, tile):
        bframes = tile.cel.expand(mat, self.pageman, self.mapcolor, self.celeffects, self.maxframes)
        if len(bframes) > self.maxframe + 1:
            self.maxframe = len(bframes) - 1
        try:
            if tile.name in self.map[mat.name]: # KeyError if mat hasn't been emitted, False if tile wasn't emitted yet
                # here if we've got the tile emitted already
                if tile.cel.stdpage:
                    return
            self.map[mat.name][tile.name] = bframes # add or overwrite it
        except KeyError:
            if mat.name == 'MICROCLINE':
                print mat.name, bframes
            self.map[mat.name] = { tile.name: bframes }
   
    def __str__(self):
        rv = 'maxframe={}\n'.format(self.maxframe)
        for k,v in self.map.items():
            rv += "material:{}\n".format(k)
            for t,bfs in v.items():
                rv += "    tilename:{}\n".format(t)
                for bf in bfs:
                    rv += "        blit={} fg={} bg={} mode={}\n".format(bf.blit, bf.fg, bf.bg, bf.mode)
        return rv

class TSCompiler(object):
    """ compiles parsed standard tilesets """
    plant_tname_map = { # blit/blend from standard tileset
        'TREE':         ('TREE',         (5,  0), (2, 0, 1)), 
        'SAPLING':      ('SAPLING',      (7, 14), (2, 0, 1)),
        'TREEDEAD':     ('DEAD_TREE',    (6, 12), (6, 0, 0)),
        'SAPLINGDEAD':  ('DEAD_SAPLING', (7, 14), (6, 0, 0)),
        'SHRUBDEAD':    ('DEAD_SHRUB',   (2,  2), (6, 0, 0)),
        'SHRUB':        ('SHRUB',        (2,  2), (2, 0, 1)),
    }
    shrub_tnames = ( 'SHRUBDEAD', 'SHRUB' )
    def __init__(self, pageman, colortab, loud = []):
        self.loud = 'compiler' in loud
        self.matiles = {}
        self.colortab = colortab
        self.pageman = pageman

    def mapcolor(self, color):
        try:
            return ( self.colortab[color[0]+8*color[2]], self.colortab[color[1]] )
        except IndexError:
            raise ValueError("unknown color {}".format(repr(color)))

    def compile(self, materialsets, tilesets, celeffects, buildings, maxframes=24):
        """ output:
            map: { material: { tiletype: [ basicframe, basicframe, ... ], ... }, ... }
            building: { material : {buildingtype: { state: [  basicframe, basicframe, ... ], ... }, ... }
        """
        rv = ObjectCode(self.pageman, self.mapcolor, celeffects, maxframes)
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
            for tileset in materialset.tilesets:
                tlist = tileset.tiles
                for o_tile in tlist:
                    for mat in materialset.materials:
                        if materialset.klass in ( 'DERIVED', 'INORGANIC', 'NONE' ):
                            if o_tile.cel is None:
                                try:
                                    mtdef = mat.stdcref
                                except AttributeError:
                                    raise CompileError("material {} has no stdcref nor celdef".format(mat.name))
                                try:
                                    tile = Tile('TILE', [o_tile.name])
                                    tile.cel = Cel('CEL', ['STD', mtdef])
                                except:
                                    continue
                            else:
                                tile = o_tile
                        elif materialset.klass == 'PLANT':
                            tile = copy.deepcopy(o_tile)
                            if mat.has('GRASS'):
                                try:
                                    bli, ble = mat.celdefs[tile.name[-6:]]
                                    tile.cel = Cel('CEL', ['STD', bli])
                                    tile.cel.frames[0].blend(ble)
                                except KeyError:
                                    pass
                            else:
                                if mat.has('TREE'):
                                    if tile.name in self.shrub_tnames:
                                        continue
                                else:
                                    if tile.name not in self.shrub_tnames:
                                        continue
                                try:
                                    rawscelname = self.plant_tname_map[tile.name][0]
                                except KeyError:
                                    print "non-vegetation tile '{}' defined for material '{}'".format(tilename, mat_name)
                                    continue # just skip it
                                bli, ble =  mat.celdefs.get(rawscelname, (None, None))                                        
                                if bli is None:
                                    bli = self.plant_tname_map[tile.name][1]
                                    bli = bli[0] + 16*bli[1]
                                if ble is None:
                                    ble = self.plant_tname_map[tile.name][2]
                                tile.cel = Cel('CEL', ['STD', bli])
                                tile.cel.frames[0].blend(ble)
                            
                        else:
                            print 'unknown matclass {}'.format(materialset.klass)
                            continue
                        rv.addtiles(mat, tile)
                        
        return rv

class Rawsparser0(object):
    loud = False
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
        if self.loud:
            print "{} parsed {}".format(self.__class__.__name__, fna)

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
                elif path.lower().endswith('.txt'):
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



class Material(object):
    def __init__(self, name, klass):
        self.name = name
        self.klass = klass
        self.stdcref = None # this is wall cref for stones/minerals
        self.color = None # this is display_color
        self.celdefs = {} # tiletype :  ( std:celref, color )
        self.others = [] # 'other' tokens
        
    def addcref(self, tname, cref):
        try:
            self.celdefs[tname] = ( cref, self.celdefs[tname][1] )
        except KeyError:
            self.celdefs[tname] = ( cref, None )
        
    def addcolor(self, tname, color):
        try:
            self.celdefs[tname] = ( self.celdefs[tname][0], color )
        except KeyError:
            self.celdefs[tname] = ( None, color )

    def __str__(self):
        try:
            name = self.name
        except AttributeError:
            name = None
        return "{}:{}".format(self.klass, name)
    
    def has(self, what):
        return what in self.others


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

    def parse_inorganic(self, name, tail):
        if name == 'INORGANIC':
            if self.mat:
                self.select(self.mat)
            self.mat = Material(tail[0], 'INORGANIC')
        elif name == 'TILE':
            self.mat.stdcref = self.tileparse(tail[0])
        elif name == 'DISPLAY_COLOR':
            self.mat.color = map(int, tail)
        elif name == 'USE_MATERIAL_TEMPLATE':
            if len(tail) != 1:
                raise ParseError('2-parameter USE_MATERIAL_TEMPLATE in INORGANIC: WTF?.')
            self.mat.color =  self.templates[tail[0]].color
            self.mat.others = copy.copy(self.templates[tail[0]].others)
        elif name not in self.mat.others:
            self.mat.others.append(name)

    def parse_plant(self, name, tail):
        if name == 'PLANT':
            if self.base_mat is not None:
                raise ParseError('USE_MATERIAL_TEMPLATE delimiter missing.')
            if self.mat:
                self.select(self.mat)
            self.mat = Material(tail[0], 'PLANT')        
        elif name == 'GRASS_TILES':
            i = 0
            for t in map(self.tileparse, tail):
                i += 1
                self.mat.addcref("FLOOR{:d}".format(i), t)
        elif name == 'GRASS_COLORS':
            self.mat.color = DEFAULT_GRASS_COLOR
            colors = map(int, tail)
            fgs = colors[0::3]
            bgs = colors[1::3]
            brs = colors[2::3]
            self.mat._colors = []
            i = 0
            for fg in fgs:
                i += 1
                self.mat.addcolor("FLOOR{:d}".format(i), (fg,bgs.pop(0),brs.pop(0)) )
        elif name == 'USE_MATERIAL_TEMPLATE':
            if len(tail) != 2:
                raise ParseError('Non-2-parameter USE_MATERIAL_TEMPLATE in PLANT: WTF?.')
            if self.base_mat is not None:
                if self.loud:
                    print "implicitly delimited {} in {}".format( self._current_template_name, self.base_mat.name)
                self.select(self.mat)
                self.mat = self.base_mat
            self._current_template_name = tail[1]
            self.base_mat = self.mat
            self.mat = Material('DERIVED', None)
            self.mat.others += self.templates[tail[1]].others, 
            self.mat.color = self.templates[tail[1]].color
        elif name in self.template_delimiters:
            if name == 'BASIC_MAT': # merge base_mat and mat
                self.base_mat.others += self.mat.others
                self.base_mat.color = self.mat.color
            else: # emit derived mat. 
                self.mat.name = "{} {}".format(self.base_mat.name, name)
                self.select(self.mat)
                
            self.mat = self.base_mat
            self.base_mat = None
        elif name == 'DISPLAY_COLOR':
            self.mat.color = map(int, tail)
        elif name.endswith('_TILE'):
            self.mat.addcref(name[:-5], self.tileparse(tail[0]))
        elif name == 'STATE_COLOR':
            return
        elif name.endswith('_COLOR'):
            self.mat.addcolor(name[:-6], map(int, tail))
        self.mat.others.append(name)

    def parse_token(self, name, tail):
        if name == 'OBJECT':
            if tail[0] not in ['INORGANIC', 'PLANT']:
                raise StopIteration
            self.otype = tail[0]
            return
        if self.otype == 'INORGANIC':
            self.parse_inorganic(name, tail)
        elif self.otype == 'PLANT':
            self.parse_plant(name, tail)

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

    def __repr__(self):
        return self.__str__()            
            
    def parse(self, name, tail):
        if name == 'FILE':
            self.file = tail[0]
        elif name in ('CEL_DIM', 'TILE_DIM'):
            self.cdim = (int(tail[0]), int(tail[1]))
        elif name == 'PAGE_DIM':
            self.pdim = (int(tail[0]), int(tail[1]))
        elif name == 'DEF':
            if len(tail) == 3:
                self.defs[tail[0]] = (int(tail[1]), int(tail[2]))
            elif len(tail) == 2:
                idx = int(tail[1])
                s = idx % self.pdim[1]
                t = idx / self.pdim[0]
                self.defs[tail[0]] = ( s, t )
            else:
                raise ValueError("Incomprehensible DEF")
                
    def load(self):
        if not self.surf:
            self.surf = pygame.image.load(self.file)
            # do not use per-pixel alpha when assembling the album
            self.surf.set_alpha(None)
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
            
    def __call__(self, color):
        rv = []
        for k in self.color:
            if k == 'FG':
                rv.append(color[0])
            elif k == 'BG':
                rv.append(color[1])
            elif k == 'BR':
                rv.append(color[2])
            else:
                rv.append(int(k))
        return rv
        #print "effect {}:{}  {}->{}".format(self.name, self.color, color, rv)

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

    def __repr__(self):
        return self.__str__()        
        
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
        return "TILESET({}: {})".format(self.name, ' '.join(map(str, self.tiles)))

    def __repr__(self):
        return self.__str__()

def parse_rgb(f):
    if len(f) == 3:
        r = int(f[0],16) << 4
        g = int(f[1],16) << 4
        b = int(f[2],16) << 4
    elif len(f) == 6:
        r, g, b = int(f[:2], 16), int(f[2:4], 16), int(f[4:6], 16)
    else:
        raise ValueError(f)
    return r,g,b,1

class Color(object):
    def __init__(self, codef):
        if codef == 'NONE':
            self.color = None
        elif codef == 'MAT':
            self.color = 'MAT'
        elif len(codef) == 1:
                self.color = parse_rgb(codef[0])
        elif len(codef) == 2:
            self.color = (parse_rgb(codef[0]), parse_rgb(codef[1]))
        elif len(codef) == 3:
            self.color = map(int, codef)
        else:
            raise ParseError("can't parse colordef {}".format(':'.join(color)))
        
    def __str__(self):
        return "({})".format(self.color)
        
    def emit(self, material, colormap, effect = None):
        """ returns a triplet: mode, fg, bg. 
            mode is :
           -1 - discard 
            0 - no blending
            1 - classic fg/bg
            2 - fg only
            3 - ???
            4 - PROFIT!!!
        """
        def noeffect(c): return c
        if effect is None:
            effect = noeffect

        if self.color == 'MAT':
            if material.color is None:
                return (0,0,0)
            else:
                fg, bg = colormap(effect(material.color))
            return (1, fg, bg)
        elif self.color == 'NONE' or self.color is None:
            return (0,0,0)
        elif type(self.color) == int:
            return (2, self.color, 0)
        elif len(self.color) == 2:
            return (1, self.color[0], self.color[1])
        elif len(self.color) == 3:
            fg, bg = colormap(effect(self.color))
            return (1, fg, bg)

class Keyframe(object):
    def __init__(self, number, idef = []):
        self.no = number
        self.page = None # used for blit, but kept separate
        self._blit = None # or idx (int), or s,t (int, int) , or def (str)
        self.effect = None # or str
        self._blend = Color('MAT') # or None, or fg,bg,br (int, int, int) or rgbx,rgbx (int,int) or rgbx value (int)
        self._glow = False # or True.
        
        # parse inline celdef
        if len(idef) == 0:
            return
        if idef[0] == 'MAT':
            self.page = 'STD'
            if len(idef) == 1:
                self._blit = ( 'MAT', 0 ) # (first) material-defined tile from the std tileset
            elif len(idef) == 2: # (mat, effect) or (mat, mdt_idx)
                try:
                    self._blit = ( 'MAT', int(idef[1]) )
                except ValueError:
                    self._blit = ( 'MAT', 0 )
                    self.effect = idef[1]
            elif len(idef) == 3: # (mat, mdt_idx, effect)
                self._blit = ( 'MAT', int(idef[1]) )
                self.effect = idef[2]
        elif idef[0] == 'NONE':
            self._blend = None
            return
        elif len(idef) == 2:# ( page, idx)  or (page, def) 
            self.page = idef[0]
            try:
                self._blit = ( int(idef[1]), )
            except ValueError:
                self._blit = ( idef[1], )
        elif len(idef) == 3: # ( page, s, t) or (page, idx, effect) or (page, def, effect)
            self.page = idef[0]
            try:
                self._blit = ( int(idef[1]), int(idef[2]) )
            except ValueError:
                try:
                    self._blit = ( int(idef[1]), )
                    self.effect = idef[2]
                except ValueError:
                    self._blit = ( idef[1], )
                    self.effect = idef[2]
        elif len(idef) == 4: # ( page, s, t, effect )
            self.page = idef[0]
            self._blit = ( int(idef[1]), int(idef[2]) )
            self.effect = idef[3]

    def blit(self, cref):
        assert type(cref) in ( list, tuple )
        self.page = cref[0]
        self._blit = cref[1:]

    def blend(self, color):
        assert type(color) in ( list, tuple )
        self._blend = Color(color)
        
    def glow(self):
        self._glow = True
        
    def __str__(self):
        return "page={} blit={} blend={}".format(self.page, self._blit, self._blend)


class BasicFrame(object):
    def __init__(self, blit, blend):
        self.blit = blit
        if blend is None:
            blend = (-1, None, None)
        self.mode = blend[0]
        self.fg = blend[1]
        self.bg = blend[2]
    def __str__(self):
        if self.mode == -1:
            return "-- mode -1: no drawing --"
        if self.fg is None:
            fg = '--------'
        else:
            fg = "{:08x}".format(self.fg)
        if self.bg is None:
            bg = '--------'
        else:
            bg = "{:08x}".format(self.bg)
        
        if self.blit is None:
            blit = '--:--'
        else:
            blit = '{:02x}:{:02x}'.format(self.blit[0], self.blit[1])
        return "{} fg={} bg={} mode={}".format(blit, fg, bg, self.mode)

    def __repr__(self):
        return self.__str__()


def interpolate_keyframes(thisframe, nextframe, material, pageman, colormap, celeffects):
    if thisframe._blit == 'MAT':
        try:
            thisframe._blit = ( material.tile, )
        except AttributeError:
            raise CompileError('no celdef in material {}'.format(material.name))
    if thisframe._blit is None:
        if thisframe == nextframe:
            num = 1
        else:
            num = nextframe.no - thisframe.no
        return [ BasicFrame(None, None) ] * num
    if thisframe == nextframe:
        return [ BasicFrame(pageman.map(thisframe.page, thisframe._blit), 
            thisframe._blend.emit(material, colormap, celeffects.get(thisframe.effect, None) )) ]

    rv = []
    mode0, fg0, bg0 = thisframe._blend.emit(material, colormap, celeffects.get(thisframe.effect, None))
    if thisframe._glow:
        mode1, fg1, bg1 = nextframe._blend.emit(material, colormap, celeffects.get(nextframe.effect, None))
        if mode1 != mode0:
            raise CompileError("can't glow between two diffected blend modes")
    else:
        mode0, fg0, bg0 = mode1, fg1, bg1
        
    def _delta(a, b, amt):
        return ( (b[0]-a[0])/amt, (b[1]-a[1])/amt, (b[2]-a[2])/amt, 0 )

    def _advance(base, delta, amt):
        return ( base[0] + delta[0]*amt, base[1] + delta[1]*amt, base[2] + delta[2]*amt, 1 )
    
    dfg = _delta(fg0, fg1, float(nextframe.no - thisframe.no))
    dbg = _delta(bg0, bg1, float(nextframe.no - thisframe.no))
    
    for no in xrange(0, nextframe.no - thisframe.no):
        if thisframe.glow:
            blend = (mode0, _advance(fg0, dfg, no), _advance(bg0, dbg, no))
        else:
            blend = thisframe.blend.emit()
        self.rv.append(BasicFrame(thisframe._blit, blend))
    return rv

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
        self.stdpage = False
    
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

    def expand(self, material, pageman, colormap, celeffects, maxframes):
        if self.current_frame is not None:
            self.frames.append(self.current_frame)
        
        if self.frames[0].page == 'STD':
            self.stdpage = True

        # loop cel's frames to get maxframes frames
        rv = []
        frameno = 0
        if len(self.frames) > 1:
            while frameno < len(self.frames) - 1:
                rv += interpolate_keyframes(self.frames[frameno], self.frames[frameno+1], material, pageman, colormap, celeffects)
            lafra = self.frames[-1]    
            
            if lafra.blit is None and lafra.blend is None: #loop back to 0th keyframe:
                lafra.blit = self.frames[0].blit
                lafra.blend = self.frames[0].blend
                rv += interpolate_keyframes(self.frames[-1], lafra, material, pageman, colormap)
        else:
            rv += interpolate_keyframes(self.frames[0], self.frames[0], material, pageman, colormap, celeffects)

        while  len(rv) < maxframes:
            rv += rv
        return rv[:maxframes]

    def __str__(self):
        try:
            f = self.frames[0]
        except IndexError:
            f = None
        return "CEL({} frames), first=({})".format( len(self.frames), f)

class MaterialSet(Token):
    tokens = ('MATERIAL', )
    parses = ('TILESETS', 'CLASSIC_COLOR', 'BUILDINGS' )
    contains = ('TILE', )
    def __init__(self, name, tail):
        self.tiles = []
        self.tilesets = []
        self.materials = []
        self.buildings = False
        if tail[0] == 'NONE':
            self.nomat = True
            self.klass = 'NONE'
            self.materials = [ Material('NONE', 'no-material') ]
            self.tokenset = []
            return
        self.nomat = False
        if tail[0] not in ( 'INORGANIC', 'PLANT', 'NONE', 'DERIVED' ):
            raise ParseError("unknown material class " + tail[0])
        self.klass = tail[0]
        self.tokenset = tail[1:]
        
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
        elif name == 'CLASSIC_COLOR':
            self.default_color = tail[0].split(',')

    def match(self, mat):
        if self.klass != mat.klass:
            return False
        for token in self.tokenset:
            if token.startswith('=') and mat.name == token[1:]:
                self.materials.append(mat)
                return True
        # invert default if we have only negative conditions
        matched = ( ''.join(self.tokenset).count('!') == len(self.tokenset) )
        #print "selector: {}:{} matched={} !={} len={}".format(matched, mat.klass, mat.name, ''.join(self.tokenset).count('!'), len(self.tokenset) )
        for token in self.tokenset:
            if token[0] == '!' and mat.has(token[1:]):
                matched = False
            elif mat.has(token):
                matched = True
        #print "selector: match={} {}:{} to {}:{}".format(matched, mat.klass, mat.name,  self.klass, self.tokenset)
        if matched:
            self.materials.append(mat)
           
        return matched

    def __str__(self):
        rv =  "MaterialSet(class={}, selector={}, materials={}, emits={})\n".format(
            self.klass, self.tokenset, map(str, self.materials), map(str, self.tilesets))
        return rv
        
    def __repr__(self):
        return self.__str__()

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
            self.celpages.append(token)
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
        rv += 'materialsets: {}\n'.format(' '.join(map(str, self.materialsets)))
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
            return True
    
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
        for klass in klasses:
            for tokname in klass.tokens:
                self.dispatch[tokname] = klass

    def parse_token(self, name, tail):
        if name == 'VERSION': # ugly kludge
            return
        if len(self.stack) == 0:
            # it will be our root object
            try:
                if not self.root:
                    self.root = self.dispatch[name](name, tail)
            except KeyError:
                if self.loud:
                    print "unknown root token {}".format(name)
                # unknown root token in a file: skip whole file
                raise StopIteration
            self.stack.append(self.root)
            return True
        
        # see if current object can handle the token itself.        
        if name in self.stack[-1].parses:
            if self.loud:
                print "{} parses {}".format(self.stack[-1].__class__.__name__, name)
            self.stack[-1].parse(name, tail)
            return True
        
        # see if current object is eager to contain it
        if name in self.stack[-1].contains:
            if self.loud: 
                print "{} contains {}".format(self.stack[-1].__class__.__name__, name)
            o = self.dispatch[name](name, tail)
            self.stack.append(o)
            return True
        

        # so it's an unknown token for this level. see if we're to ignore it
        if self.stack[-1].ignores_unknown:
            een = False
            for s in self.stack:
                if name in s.tokens:
                    een = True # someone in the stack knows what to do with it
                    
            if not een:
                if self.loud:
                    print "dropped unknown token {}".format(name)
                return not een # completely unknown token, just drop it

        if len(self.stack) == 1: # got root only.
            # insidious kludge. :(
            try:
                o = self.dispatch[name](name, tail)
            except KeyError:
                # NEH aka HFS
                raise ParseError("unknown token '{}'".format(name))
            if type(o) == type(self.root):
                if self.loud:
                    print "accepted next root token {}:{}".format(name, tail[0])
                return True
            raise ParseError("WTF")
            
        if self.loud: 
            print 'unwinding stack: {} for {}'.format(' '.join(map(lambda x: x.__class__.__name__, self.stack)), name)

        o = self.stack.pop(-1)
        if self.stack[-1].add(o):
            if self.loud: 
                print "{} accepted {}".format(self.stack[-1].__class__.__name__, o.__class__.__name__) 
        else:
            if self.loud: 
                print "{} did not accept {}".format(self.stack[-1].__class__.__name__, o.__class__.__name__) 
        
        # continue unwinding stack until we've put the token somewhere.
        self.parse_token(name, tail)
        return

    def fin(self):
        while len(self.stack) > 1:
            if self.loud: 
                print 'fin(): unwinding stack: {}'.format( ' '.join(map(lambda x: x.__class__.__name__, self.stack)))
            o = self.stack.pop(-1)
            if self.stack[-1].add(o):
                if self.loud: 
                    print "fin(): {} accepted {}".format(self.stack[-1].__class__.__name__, o.__class__.__name__) 
            else:
                if self.loud: 
                    print "fin(): {} did not accept {}".format(self.stack[-1].__class__.__name__, o.__class__.__name__) 
            
        if self.loud: 
            print 'fin(): stack: {}'.format( ' '.join(map(lambda x: x.__class__.__name__, self.stack)))
        
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
        if len(tail) == 4:
            variant = 'DEFAULT'
        else:
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
            raise ValueError("unknown variant '{}'".format(tail))

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

def work(dfprefix, fgraws, loud=()):
    init = Initparser(dfprefix)
    stdraws = os.path.join(dfprefix, 'raw')
    
    mtparser = AdvRawsParser( MaterialTemplates, MaterialTemplate )
    fgparser = AdvRawsParser( FullGraphics, CelEffect, Tile, Tileset, CelPage, Cel, Building, MaterialSet )
    gsparser = AdvRawsParser( CreaGraphics, CreaGraphicsSet, CelPage )
    
    if 'parser' in loud:
        fgparser.loud = True
        
    map(mtparser.eat, [stdraws])
    map(gsparser.eat, [stdraws])
    map(fgparser.eat, [fgraws])
    
    mtset = mtparser.get()
    fgdef = fgparser.get()
    cgset = gsparser.get()
    
    if "parser" in loud:
        print fgdef
    
    stdparser = TSParser(mtset.templates, fgdef.materialsets)
    if 'parser' in loud:
        stdparser.loud = True
        
    map(stdparser.eat, [stdraws])
    materialsets = stdparser.get()

    if 'materialset' in loud:
        print materialsets

    pageman = Pageman(init.fontpath, pages = fgdef.celpages) # + cgset.celpages) uncomment when creatures become supported
    
    compiler = TSCompiler(pageman, init.colortab, loud)
    objcode = compiler.compile(materialsets, fgdef.tilesets, fgdef.celeffects, fgdef.buildings, 1)

    return pageman, objcode


def main():
    dfpfx, fgraws, loud = sys.argv[1],sys.argv[2], sys.argv[3:]
    pygame.display.init()
    p,m = work(dfpfx, fgraws, loud)
    if 'pageman' in loud:
        print p
    if 'objcode' in loud:
        print m
    

if __name__ == '__main__':
    main()

