#!/usr/bin/python

import os, os.path, glob, sys, xml.parsers.expat, time, re, argparse
import traceback, stat, copy, struct, math, mmap, pprint, ctypes, weakref
import numpy as np
import pygame.image

from tokensets import *

DEFAULT_GRASS_COLOR = (2, 0, 1) # light-green

class ParseError(Exception):
    pass

class CompileError(Exception):
    pass
class ExpressionError(Exception):
    """ stack underflow or more than one value at end
        of material selector expression evaluation """

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
        self.enumc = []
        self.emap = {}
        self.emapc = {}
        self.gotit = False
        self.name = name
        self.parse(f)

    def start_element(self, tagname, attrs):
        if tagname == 'enum-type' and attrs['type-name'] == self.name:
            self.gotit = True
        elif tagname == 'enum-item' and self.gotit:
            try:
                self.enums.append(attrs['name'].upper())
                self.enumc.append(attrs['name'])
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
        i = 0
        for e in self.enumc:
            self.emapc[e] = i
            i += 1

    def __len__(self):
        return len(self.enums)

    def __getitem__(self, key):
        if type(key) in (long, int):
            try:
                return self.enums[key]
            except IndexError:
                return "-no-data-"
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

    @property
    def txsz(self):
        "returns txsz tuple"
        self.shrink()
        cw, ch = self.max_cdim
        wt, ht = self.album_w/cw, self.album_h/ch
        return (wt, ht, cw, ch)
    
    @property
    def data(self):
        "returns bytes for the resulting texture"
        return pygame.image.tostring(self.surf, 'RGBA')

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
            self.map[mat.name] = { tile.name: bframes }

    def __str__(self):
        rv = 'maxframe={}\n'.format(self.maxframe)
        for k,v in self.map.items():
            rv += "material:{}\n".format(k)
            for t,bfs in v.items():
                if len(bfs) == 1:
                    rv += "    tilename:{:<32} {}\n".format(t, bfs[0])
                else:
                    rv += "    tilename:{}\n".format(t)
                    for bf in bfs:
                        rv += " "*8 + str(bf) + "\n"
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
        celeffects[None] = lambda c: c # noneffect is none
        rv = ObjectCode(self.pageman, self.mapcolor, celeffects, maxframes)
        for materialset in materialsets:
            x = []
            for tileset in materialset.tilesets:
                x.append(tilesets[tileset])
            materialset.tilesets = x
            if len(materialset.tiles) > 0:
                d = TileSet('TILESET', ['__IMPLIED'])
                for tile in materialset.tiles:
                    d.add(tile)
                materialset.tilesets.append(d)

        for materialset in materialsets:
            for tileset in materialset.tilesets:
                tlist = tileset.tiles
                for o_tile in tlist:
                    for mat in materialset.materials:
                        tns = mat.parent.celrefs.keys()
                        if 'SHRUB' in tns or 'DEAD_SHRUB' in tns:
                            if 'TREE' in tns or 'DEAD_TREE' in tns or 'SAPLING' in tns or 'DEAD_SAPLING' in tns:
                                raise CryWolf
                            
                        continue
                        if mat.klass == 'SOAP':
                            # SOAPP! SKIPP ITT!
                            # (soap being hardmapped to a built-in mat in the renderer for now)
                            continue
                        
                        """
                        well. so we have single-tile materials like stone
                        and multi-tile materials like grass, shrubs and trees.
                        """
                        
                        if materialset.klass == 'STRUCTURAL':
                            tile = copy.deepcopy(o_tile)
                            if mat.parent.has('GRASS'): # structurals should always have parents
                                try:
                                    bli, ble = mat.parent.celdefs[tile.name[-6:]]
                                    tile.cel = Cel('CEL', ['STD', bli])
                                    tile.cel.frames[0].blend(ble)                                    
                                except KeyError:
                                    print "haz-grazzz; but skipping:", mat, tile.name#, mat.parent.celdefs
                                    
                                    # no correspoding celdef for the tile in the parent plant,
                                    # skip it
                                    continue
                            else:
                                if mat.parent.has('TREE'):
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
                                bli, ble =  mat.parent.celdefs.get(rawscelname, (None, None))
                                print tile.name, ": ", bli, ble, " for ",rawscelname, mat.parent, mat.parent.celdefs.keys()
                                if bli is None:
                                    bli = self.plant_tname_map[tile.name][1]
                                    bli = bli[0] + 16*bli[1]
                                if ble is None:
                                    ble = self.plant_tname_map[tile.name][2]
                                tile.cel = Cel('CEL', ['STD', bli])
                                tile.cel.frames[0].blend(ble)

                        else: # inorganic and the rest 
                            if o_tile.cel is None:
                                try:
                                    mtdef = mat.cref
                                except AttributeError:
                                    raise CompileError("material {} has no cref nor celdef".format(mat.name))
                                try:
                                    tile = Tile('TILE', [o_tile.name])
                                    tile.cel = Cel('CEL', ['STD', mtdef])
                                except:
                                    continue
                            else:
                                tile = o_tile
                        try:
                            rv.addtiles(mat, tile)
                        except:
                            print materialset.klass
                            raise
                        
        return rv

class RawsParser0(object):
    loud = False
    def parse_file(self, fna, handler):
        lnum = 0
        for l in file(fna):
            l = l.strip()
            lnum += 1
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

    @staticmethod
    def tileparse(t):
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

class InitParser(RawsParser0):
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




class RawsObject0(object):
    def __init__(self, name, klass):
        self.name = name
        self.klass = klass
        self._basic_mat = None        
        self.tokens = set()
        self.celdefs = {}

    def add(self, name):
        self.tokens.add(name)

    def __contains__(self, what):
        return what in self.tokens

    def __str__(self):
        return "{}({})".format(self.klass, self.name)

    def _addcref(self, tname, rawcref):
        cref = TSParser.tileparse(rawcref)
        try:
            self.celdefs[tname] = ( cref, self.celdefs[tname][1] )
        except KeyError:
            self.celdefs[tname] = ( cref, None )
        
    def _addcolor(self, tname, color):
        color = map(int, color)
        try:
            self.celdefs[tname] = ( self.celdefs[tname][0], color )
        except KeyError:
            self.celdefs[tname] = ( None, color )

class Plant(RawsObject0):
    """ a plant (and not a plant material) """
    def __init__(self, name):
        super(Plant, self).__init__(name, 'PLANT')

    @property
    def basic_mat(self):
        return self._basic_mat

    @basic_mat.setter
    def basic_mat(self, mat):
        assert self._basic_mat is None
        self._basic_mat = mat

    def token(self, name, tail):
        if name == 'GRASS_TILES':
            i = 0
            for t in tail:
                i += 1
                self._addcref("FLOOR{:d}".format(i), t)
        elif name == 'GRASS_COLORS':
            colors = map(int, tail)
            fgs = colors[0::3]
            bgs = colors[1::3]
            brs = colors[2::3]
            i = 0
            for fg in fgs:
                i += 1
                self._addcolor("FLOOR{:d}".format(i), (fg, bgs.pop(0), brs.pop(0)))        
        elif name.endswith('_TILE'):
            self._addcref(name[:-5], tail[0])
        elif name.endswith('_COLOR'):
            self._addcolor(name[:-6], tail)
        self.add(name)

class Inorganic(RawsObject0):
    """ an inorganic material """
    def __init__(self, name):
        super(Inorganic, self).__init__(name, 'INORGANIC')
        
    def token(self, name, tail):
        if name == 'DISPLAY_COLOR':
            self._dc = tail[0]
        self.add(name)

    def update(self, template):
        self.tokens.update(template.parsed)
        self._dc = template.display_color        

    @property
    def display_color(self):
        return self._dc

class Derived(object):
    """ a derived material """
    def __init__(self, parent, klass, template):
        self.klass = klass
        self.parent = parent
        self.tokens = set()
        
        self.tokens.update(template.parsed)
        self._dc = template.display_color

    def token(self, name, tail):
        if name == 'DISPLAY_COLOR':
            self._dc = map(int, tail)
        self.tokens.add(name)
    
    @property
    def name(self):
        return self.parent.name
    
    @property
    def display_color(self):
        return self._dc
    
    def __contains__(self, what):
        return what in self.tokens
    
    def __str__(self):
        return "{}:{}".format(self.klass, self.name)

class TSParser(RawsParser0):
    def __init__(self, templates, materialsets, loud = False):
        self.loud = loud
        self.all = []
        self.otype = None
        self.mat = None
        self.derived_mat = None
        self.materialsets = materialsets
        self.templates = templates
    
    def select(self):
        if self.mat is not None:
            file('yoba/'+self.mat.name, 'w').write('\n'.join(self.mat.tokens))
            matched = False
            for sel in self.materialsets:
                if sel.match(self.mat):
                    matched = True
            if self.loud and not matched:
                print("no matset accepted {}".format(self.mat))
            self.mat = None

    def parse_inorganic(self, name, tail):
        if name == 'INORGANIC':
            self.select()
            self.mat = Inorganic(tail[0])
        elif name == 'USE_MATERIAL_TEMPLATE':
            self.mat.update(self.templates[tail[0]])
        elif name in INORGANIC_TOKENS:
            self.mat.token(name, tail)
        else:
            raise ParseError("Unrecognized inorganic material definition token:'{}'".format(name))

    def parse_plant(self, name, tail):
        if name == 'PLANT':
            self.select()
            self.plant = Plant(tail[0])
        elif name == 'USE_MATERIAL_TEMPLATE':
            if len(tail) != 2:
                raise ParseError('Non-2-parameter USE_MATERIAL_TEMPLATE in PLANT: WTF?')
            self.select()
            self.mat = Derived(self.plant, tail[0], self.templates[tail[1]])
        elif name in PLANT_TOKENS:
            self.plant.token(name, tail)
        elif name in MATERIAL_TOKENS:
            if not self.mat: # aw, WHA?
                raise ParseError("Unexpected material token '{}'".format(name))
            self.mat.token(name, tail)
        else:
            raise ParseError("Unrecognized plant token:'{}'".format(name))

    def parse_token(self, name, tail):
        if name == 'OBJECT':
            if tail[0] not in ['INORGANIC', 'PLANT']:
                raise StopIteration
            self.otype = tail[0]
            return
        elif name == 'VERSION':# skip phoebus' file in raw/graphics
            raise StopIteration
        try:
            if self.otype == 'INORGANIC':
                self.parse_inorganic(name, tail)
            elif self.otype == 'PLANT':
                self.parse_plant(name, tail)
        except KeyError:
            print self.templates
            raise

    def get(self):
        self.select()
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
        
class TileSet(Token):
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

class TileClass(Token):
    tokens = ('TILECLASS', )
    parses = ('TILE', )
    
    def __init__(self, name, tail):
        self.name = tail[0]
        try:
            self.value = int(tail[1])
        except ValueError:
            self.value = int(tail[1], 16)
        self.tiles = {}
        
    def parse(self, name, tail):
        if name == 'TILE':
            self.tiles[tail[0]] = tail[1:]
            return True

    def __str__(self):
        ts = ''
        return "TILECLASS({}({}): {})".format(self.name, self.value, ' '.join(self.tiles.keys()))

    def __repr__(self):
        return self.__str__()

class TcFlag(Token):
    tokens = ('TCFLAG', )
    def __init__(self, name, tail):
        self.name = tail[0]
        try:
            self.value = int(tail[1])
        except ValueError:
            self.value = int(tail[1], 16)

def TCCompile(tires, tcs, tcfs, loud=False):
    # rv format: list of ( uint16_t flags, uint16_t klassid )
    _tmp = [ (0, 0) ] * len(tires)
    rv = [ 0 ]  * len(tires)
    for tc in tcs:
        klassid = tc.value
        for tname, flags in tc.tiles.items():
            tnum = tires[tname]
            f = 0
            for flag in flags:
                f |= ( 1 << tcfs[flag].value )
            _tmp[tnum] = (f, klassid)
            rv[tnum] = f << 8 | klassid

    return rv
    """ use for texture-lookup/uniform BO
    rs = b''
    i = 0
    for f, k in _tmp:
        rs += struct.pack("<HH", f, k)
        if loud:
            print "{}: {} {}".format(tires[i], f, k)
            i += 1
    return rs """
    
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
    def __init__(self, codef, effect = None):
        self._effect_ref = effect
        
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
        
    def emit(self, material, colormap, effectmap):
        """ returns a triplet: mode, fg, bg. 
            mode is :
            0 - discard       (0, None, None)
            1 - no blending   (1, None, None)
            2 - classic fg/bg (2, fg, bg)
            3 - fg only       (3, fg, None)
            4 - ???
            5 - PROFIT!!!     (5, "PROFIT", "!!!")
        """

        if self.color == 'MAT':
            if material.display_color is not None:
                fg, bg = colormap(effectmap[self._effect_ref](material.display_color))
                return (2, fg, bg)
            else:
                return (1, None, None) # default blitmode AS_IS for materials w/o colors
        elif self.color == 'NONE' or self.color is None: # discard
            return (0, None, None) 
        elif type(self.color) == int:
            return (3, self.color, None)
        elif len(self.color) == 2:
            return (2, self.color[0], self.color[1])
        elif len(self.color) == 3:
            fg, bg = colormap(effectmap[self._effect_ref](self.color))
            return (2, fg, bg)

class KeyFrame(object):
    def __init__(self, number, idef = []):
        self.no = number
        self._page = None # used for blit, but kept separate for being queried by objcode container
        self._glow = False # or True.
        self._inline = False # to throw errors if explicit celdef follows inline one (insanity via effects otherwise)
        if len(idef) == 0: return

        # parse inline celdef (only place where effects are allowed)
        #  -- moderately ugly hack.
        self._inline = True
        if idef[0] == 'MAT':
            self._page = 'STD'
            if len(idef) == 1:
                self._blit = ('MAT', 0) # (first) material-defined tile from the std tileset
                self._blend = Color('MAT')
            elif len(idef) == 2: # (MAT, effect) or (MAT, mdt_idx) # mdt = 'material-defined tile'
                try:
                    self._blit = ('MAT', int(idef[1]))
                    self._blend = Color('MAT')
                except ValueError:
                    self._blit = ('MAT', 0)
                    self._blend = Color('MAT', idef[1])
            elif len(idef) == 3: # (MAT, mdt_idx, effect)
                self._blit = ( 'MAT', int(idef[1]) )
                self._blend = Color('MAT', idef[2])
        elif idef[0] == 'NONE': # explicit discard
            self._page = None
            self._blit = None
            self._blend = (0, None, None)
            return
        elif len(idef) == 2: # ( page, idx)  or (page, def)
            self._page = idef[0]
            self._blend = Color('MAT')
            try:
                self._blit = ( int(idef[1]), )
            except ValueError:
                self._blit = ( idef[1], )
        elif len(idef) == 3: # ( page, s, t) or (page, idx, effect) or (page, def, effect)
            self._page = idef[0]
            try:
                self._blit = ( int(idef[1]), int(idef[2]) )
                self._blend = Color('MAT')
            except ValueError:
                try:
                    self._blit = ( int(idef[1]), )
                    self._blend = Color('MAT', idef[2])
                except ValueError:
                    self._blit = ( idef[1], )
                    self._blend = Color('MAT', idef[2])
        elif len(idef) == 4: # ( page, s, t, effect )
            self._page = idef[0]
            self._blit = ( int(idef[1]), int(idef[2]) )
            self._blend = Color('MAT', idef[3])

    @property
    def page(self):
        return self._page

    def blit(self, cref):
        assert type(cref) in ( list, tuple )
        assert not self._inline
        self.page = cref[0]
        self._blit = cref[1:]

    def blend(self, color):
        assert type(color) in ( list, tuple )
        
        #assert ( not self._inline or self._blend.color != 'MAT')
        self._blend = Color(color)
        
    def glow(self):
        assert not self._inline
        self._glow = True
        
    def __str__(self):
        return "page={} blit={} blend={}".format(self.page, self._blit, self._blend)


class BasicFrame(object):
    def __init__(self, blit, blend):
        self.blit = blit
        self.mode = blend[0]
        self.fg = blend[1]
        self.bg = blend[2]

    def __str__(self):
        if self.mode == 0:
            return "mode=discard"
        elif self.mode == 1:
            return "mode=as is   blit={:>2d}:{:<2d}".format(self.blit[0], self.blit[1])
        elif self.mode == 2:
            return "mode=classic blit={:>2d}:{:<2d} fg={:08x} bg={:08x}".format(self.blit[0], self.blit[1], self.fg, self.bg)
        elif self.mode == 3:
            return "mode=fg-only blit={:>2d}:{:<2d} fg={:08x}".format(self.blit[0], self.blit[1], self.fg)
        elif self.mode == 4:
            return "mode=???"
        elif self.mode == 6:
            return "mode=PROFIT!!!"

    def __repr__(self):
        return self.__str__()


def interpolate_keyframes(thisframe, nextframe, material, pageman, colormap, celeffects):
    if thisframe._blit == 'MAT':
        try:
            thisframe._blit = ( material.tile, )
        except AttributeError:
            raise CompileError('no celdef in material {}'.format(material.name))

    elif thisframe._blit is None: # explicit discard or wha? animation bug here is likely
        if thisframe == nextframe:
            num = 1
        else:
            num = nextframe.no - thisframe.no
        return [ BasicFrame(None, (0, None, None)) ] * num

    if thisframe == nextframe: # single framedef as in inline celdefs
        return [ BasicFrame(pageman.map(thisframe.page, thisframe._blit), 
            thisframe._blend.emit(material, colormap, celeffects)) ]

    rv = []
    mode0, fg0, bg0 = thisframe._blend.emit(material, colormap, celeffects)
    if thisframe._glow:
        mode1, fg1, bg1 = nextframe._blend.emit(material, colormap, celeffects)
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
            self.frames.append(KeyFrame(0, tail))
            self.current_frame = None
        else:
            self.current_frame = KeyFrame(0)
    
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
            self.current_frame = KeyFrame(int(tail[0]))

    def expand(self, material, pageman, colormap, celeffects, maxframes):
        if self.current_frame is not None:
            self.frames.append(self.current_frame)
        
        self.stdpage = self.frames[0].page == 'STD'

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
class PoNoExpr(object):
    """
#     name:                 (alias)
#         mat                      - set of tokens (f.ex. to select metals)
#         mat.klass         (mk)   - structural, seed, etc
#         mat.name          (mn)   - name, same as for parent
#         mat.parent        (mp)   - set of tokens for the parent object (f.ex. to select various stones)
#         mat.parent.klass  (mpk)  - inorganic, plant, creature, none """
    aliases = {
        'mk': 'mat.klass',
        'mn': 'mat.name',
        'mp': 'mat.parent',
        'mpk': 'mat.parent.klass', }

    def __init__(self, expr):        
        self.expr = expr
        self.ops = { # arity, function
            'not': (1, lambda a   :   not a),
            'and': (2, lambda a, b: a and b),
            'or':  (2, lambda a, b: a  or b),
            'eq':  (2, lambda a, b: a  == b),
            'in':  (2, lambda a, b: a  in b),
            'mat':              (0, lambda: self.mat),
            'mat.klass':        (0, lambda: self.mat.klass ),
            'mat.name':         (0, lambda: self.mat.name ),
            'mat.parent':       (0, lambda: self.mat.parent ), 
            'mat.parent.klass': (0, lambda: self.mat.parent.klass ), }

        for alias, name in self.aliases.items():
            self.ops[alias] = self.ops[name]

    def __str__(self): 
        return ':'.join(self.expr).lower()

    def __call__(self, mat):
        stack = []
        def push(a): stack.append(a)
        def pop(): 
            try:
                return stack.pop()
            except IndexError:
                raise ExpressionError("{}: stack underflow".format(self))

        self.mat = mat
        for op in self.expr:
            try:
                arity, foo = self.ops[op.lower()]
            except KeyError:
                push(op) # a literal
                continue
            if arity == 0:
                push(foo())
            elif arity == 1:
                a = pop()
                push(foo(a))
            elif arity == 2:
                b = pop()
                a = pop()
                push(foo(a, b))
        self.mat = None
        if len(stack) != 1:
            raise ExpressionError("{}; stack={}".format(self, "\n".join(stack)))
        return pop()

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
            return
        self.nomat = False
        self.expr = PoNoExpr(tail)
        
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
        try:
            rv = self.expr(mat)
        except AttributeError: # attempt at mat.parent on inorganic mat
            return False
        assert type(rv) is bool
        if rv: self.materials.append(mat)
        return rv

    def __str__(self):
        rv =  "MaterialSet(selector={}, emits={})".format(self.expr, map(str, self.tilesets))
        if len(self.materials) == 0:
            return rv + " empty.\n"
        for m in self.materials:
            rv += "\n    " + str(m)
        return rv + "\n"
        
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
    contains = ( 'TILESET', 'EFFECT', 'CEL_PAGE', 'TILECLASS', 'TCFLAG',
                 'TILE_PAGE', 'MATERIAL', 'BUILDING' )
            
    def __init__(self, name, tail):
        if tail[0] != 'FULL_GRAPHICS':
            raise StopIteration
        self.toplevel_tileset = TileSet(None, '__toplevel__')
        self.tilesets = {}
        self.materialsets = []
        self.celpages = []
        self.celeffects = {}
        self.buildings = {}
        self.tileclasses = []
        self.tcflags = {}
        
    def add(self, token):
        if type(token) == TileSet:
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
        elif type(token) == TileClass:
            self.tileclasses.append(token)
        elif type(token) == TcFlag:
            self.tcflags[token.name] = token
        elif type(token) == FullGraphics:
            return False
        else:
            raise ParseError("unexpected token at top level: " + repr(token))
        return True
    
    def __str__(self):
        rv = ''
        rv += 'tilesets: {}\n'.format(' '.join(self.tilesets.keys()))
        rv += 'tileclasses: {}\n'.format(' '.join(map(str, self.tileclasses)))
        rv += 'tcflags: {}\n'.format(' '.join(self.tcflags.keys()))
        rv += 'celeffects: {}\n'.format(' '.join(self.celeffects.keys()))
        rv += 'celpages: {}\n'.format(' '.join(map(lambda x: x.name, self.celpages)))
        rv += 'materialsets: {}\n'.format(' '.join(map(str, self.materialsets)))
        rv += 'buildings: {}\n'.format(' '.join(self.buildings.keys()))
        
        return rv

class MaterialTemplates(Token):
    tokens = ('OBJECT',)
    contains = ('MATERIAL_TEMPLATE',)
                 
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
    parses = MATERIAL_TEMPLATE_TOKENS
    ignores_unknown = True

    def __init__(self, name, tail):
        self.name = tail[0]
        self.display_color = None
        self.parsed = set()
        
    def parse(self, name, tail):
        if name == 'DISPLAY_COLOR':
            self.display_color = map(int, tail)
        self.parsed.add(name)
        

class AdvRawsParser(RawsParser0):
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
        
    def __init__(self, *klasses, **kwargs):
        self.loud = kwargs.get('loud', False)
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
                    print "dropped unknown token {}, stack: {}".format(name, map(lambda x: x.__class__.__name__, self.stack))
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

class MapObject(object):
    def __init__(self, dfprefix,  fgraws=[], apidir='', cutoff = 0, loud=[]):
        self.dispatch_dt = np.dtype({  # GL_RG16UI - 32 bits, all used.
            'names': 's t'.split(),
            'formats': ['u2', 'u2' ],
            'offsets': [ 0, 2 ],
            'titles': ['blitcode s-coord', 'blitcode t-coord'] })

        self.blitcode_dt = np.dtype({ # GL_RGBA32UI - 128 bits. 16 bits unused.
            'names': 'un2 un1 t s mode fg bg'.split(),
            'formats': ['u1', 'u1', 'u1', 'u1', 'u4', 'u4', 'u4'],
            'offsets': [ 0, 1, 2, 3, 4, 8, 12 ] })
        
        self.data_dt = np.dtype({ # GL_RGBA32UI - 128 bits. 16 bits unused.
            'names': 'stoti bmabui grass designation'.split(),
            'formats': ['u4', 'u4', 'u4', 'u4'],
            'offsets': [ 0, 4, 8, 12 ] })
        self._mmap_fd = None
        self.loud = loud
        self.cutoff = cutoff
        
        self.tileresolve = DfapiEnum(apidir, 'tiletype')
        self.building_t = DfapiEnum(apidir, 'building_type')
        
        self._parse_raws(dfprefix, fgraws)

    def use_dump(self, dumpfname, irdump):
        self._parse_dump(dumpfname)
        self._assemble_blitcode(self._objcode, irdump)
        self._map_dump(dumpfname)
        
    def _parse_raws(self, dfprefix, fgraws):
        maxframes = self.cutoff + 1
        # maxframes here define for how many frames to extend
        # cel's final framesequence 
        # while cutoff is something else. (TODO: fix all this)
        
        init = InitParser(dfprefix)
      
        stdraws = os.path.join(dfprefix, 'raw')
        
        mtparser = AdvRawsParser( MaterialTemplates, MaterialTemplate, loud = 'mtparser' in self.loud)
        fgparser = AdvRawsParser( FullGraphics, Tile, TileSet, TileClass, TcFlag, 
            CelEffect, CelPage, Cel, Building, MaterialSet, loud = 'fgparser' in self.loud )
        gsparser = AdvRawsParser( CreaGraphics, CreaGraphicsSet, CelPage, loud = 'gsparser' in self.loud )
        
        mtparser.eat(stdraws)
        gsparser.eat(stdraws)
        map(fgparser.eat,  fgraws)
        
        mtset = mtparser.get()
        fgdef = fgparser.get()
        cgset = gsparser.get()
        
        if "fgdef" in self.loud:
            print fgdef
        
        stdparser = TSParser(mtset.templates, fgdef.materialsets, loud = 'stdparser' in self.loud)
            
        map(stdparser.eat, [stdraws])
        materialsets = stdparser.get()

        if 'materialset' in self.loud:
            for ms in materialsets:
                print ms

        self._pageman = Pageman(init.fontpath, pages = fgdef.celpages) 
            # + cgset.celpages) uncomment when creatures become supported
        self.txsz = self._pageman.txsz
        self.fontptr = self._pageman.data
        
        compiler = TSCompiler(self._pageman, init.colortab, self.loud)
        self._objcode = compiler.compile(materialsets, fgdef.tilesets, 
            fgdef.celeffects, fgdef.buildings, maxframes)
        self.tcptr = TCCompile(self.tileresolve, fgdef.tileclasses, fgdef.tcflags)
        if 'objcode' in self.loud:
            print self._objcode
        
        

    def _map_dump(self, dumpfname):
        if self._mmap_fd:
            self._tiles_mmap.close()
            os.close(self._mmap_fd)
        
        fsize = os.stat(dumpfname).st_size
        if os.name == 'nt':
            self._map_fd = os.open(dumpfname, os.O_RDONLY|os.O_BINARY)
        else:
            self._map_fd = os.open(dumpfname, os.O_RDONLY)
        try:
            self._tiles_mmap = mmap.mmap(self._map_fd, self.tiles_size, 
                offset = self.tiles_offset, access = mmap.ACCESS_READ)
        except ValueError:
            print "fsize: {} tiles {},{} effects: {}".format(fsize, 
                self.tiles_offset, self.tiles_size, self.effects_offset )
            raise

        print "mapdata: {}x{}x{} {}M".format(self.xdim, self.ydim, self.zdim, self.tiles_size >>20)
        

    def _parse_dump(self, dumpfname):
        self.mat_ksk = {}
        self.mat_ids = {}
        HEADER_SIZE = 264
        dumpf = file(dumpfname)
        self.max_mat_id = -1
        # read header
        l = dumpf.readline()
        if not l.startswith("origin:"):
            raise TypeError("Wrong trousers " + l )
        x, y, z = l[7:].strip().split(':')
        self.xorigin, self.yorigin, self.zorigin = map(int, [x, y, z])
        self.xorigin *= 16
        self.yorigin *= 16
        
        l = dumpf.readline()
        if not l.startswith("extent:"):
            raise TypeError("Wrong trousers " + l )
        x, y, z = l[7:].strip().split(':')
        self.xdim, self.ydim, self.zdim = map(int, [x, y, z])
        self.xdim *= 16
        self.ydim *= 16
        
        l = dumpf.readline()
        if not l.startswith("tiles:"):
            raise TypeError("Wrong trousers " + l )
        self.tiles_offset, self.tiles_size = map(int, l[6:].split(':'))
        
        l = dumpf.readline()
        if not l.startswith("effects:"):
            raise TypeError("Wrong trousers " + l )
        self.effects_offset = int(l[8:])
        
        # read and combine all of plaintext
        lines = dumpf.read(self.tiles_offset - dumpf.tell()).split("\n")
        
        dumpf.seek(self.effects_offset)
        lines += dumpf.read().split("\n")
        
        # parse plaintext
        sections = [ 'materials', 'buildings', 'building_defs', 'constructions', 'effects', 'units', 'items' ]
        section = None
        for l in lines:
            l = l.strip()
            if l == '':
                continue
            if l.startswith('section:'):
                unused, section = l.split(':')
                section = section.lower()
                if section not in sections:
                    section = None
                continue
            if section == 'materials':
                s = re.split("([a-z]+)=", l)
                id = int(s[0])
                if self.max_mat_id < id:
                    self.max_mat_id = id 
                rest = s[1:]
                i = 0
                subklass = None
                for k in rest[::2]:
                    k = k.strip()
                    v = rest[1::2][i].strip()
                    i += 1 
                    if k == 'id':
                        name = v
                    elif k == 'subklass':
                        subklass = ' ' + v
                    elif k == 'klass':
                        klass = v

                self.mat_ksk[id] = (name, klass, subklass)
                self.mat_ids[(klass, subklass)] = id
                self.mat_ids[name] = id

    def _assemble_blitcode(self, objcode, irdump=None):
        # all used data is available before first map frame is to be
        # rendered in game.
        # eatpage receives individual tile pages and puts them into one big one
        # maptile maps pagename, s, t into tiu, s, t  that correspond to the big one
        # tile_names map tile names in raws to tile_ids in game
        # inorg_ids and plant_ids map mat names in raws to effective mat ids in game
        # (those can change every read of raws)
        cutoff = self.cutoff
        
        if cutoff > objcode.maxframe:
            cutoff = objcode.maxframe
        self.codedepth = cutoff + 1
        tcount = 0
        for mat, tset in objcode.map.items():
            tcount += len(tset.keys())
        if tcount > 65536:
            raise TooManyTilesDefinedCommaManCommaYouNutsZedonk
        self.codew = int(math.ceil(math.sqrt(tcount)))
        
        self.matcount = self.max_mat_id + 1
        self.tiletypecount = len(self.tileresolve)
        
        dispatch = np.zeros((self.tiletypecount, self.matcount ), dtype=self.dispatch_dt)
        
        blitcode = np.zeros((cutoff+1, self.codew, self.codew), dtype=self.blitcode_dt)
        nf = (cutoff+1) * self.codew * self.codew
        tc = 1

        # 'link' map tiles
        for mat_name, tileset in objcode.map.items():
            try:
                mat_id = self.mat_ids[mat_name]
            except KeyError:
                mat_id = 0
                
            for tilename, frameseq in tileset.items():
                x = int (tc % self.codew)
                y = int (tc / self.codew)
                tc += 1
                try:
                    tile_id = self.tileresolve[tilename]
                except KeyError:
                    print "unk tname {} in mat {}".format(tilename, mat_name)
                    raise

                hx = mat_id
                hy = tile_id
                dispatch[hy, hx]['s'] = x
                dispatch[hy, hx]['t'] = y               
                frame_no = 0
                for frame in frameseq:
                    blitcode[frame_no, y, x]['mode'] = frame.mode
                    if frame.mode == 0:
                        continue
                    blitcode[frame_no, y, x]['s'] = frame.blit[0]
                    blitcode[frame_no, y, x]['t'] = frame.blit[1]
                    if frame.mode == 1:
                        continue
                    blitcode[frame_no, y, x]['fg'] = frame.fg
                    if frame.mode == 3:
                        continue
                    assert frame.mode == 2
                    blitcode[frame_no, y, x]['bg'] = frame.bg
                    if irdump:
                        irdump.write("{:03d}:{:03d} {}:{} {} {} {}\n".format(mat_id, tile_id, x, y, mat_name, tilename, frame))
                    frame_no += 1
                    if frame_no > cutoff:
                        break
        self.dispatch, self.blitcode = dispatch, blitcode
        print "objcode: {1} mats  {0} defined tiles, cutoff={2}".format(tcount, len(objcode.map.keys()), cutoff)
        print "dispatch: {}x{}, {} bytes".format(self.matcount,  self.tiletypecount, self.matcount*self.tiletypecount*4)
        print "blitcode: {}x{}x{} {} units, {} bytes".format(self.codew, self.codew, cutoff+1, nf, nf*16 )

    @property
    def codeptr(self):
        return ctypes.c_void_p(self.blitcode.__array_interface__['data'][0])

    @property
    def disptr(self):
        file('dispatch.dump', 'w').write(self.dispatch.tostring())
        return ctypes.c_void_p(self.dispatch.__array_interface__['data'][0])

    @property
    def mapptr(self):
        """ will crash on python debug build """
        PyObject_HEAD = [ ('ob_refcnt', ctypes.c_size_t), ('ob_type', ctypes.c_void_p) ]
        class mmap_mmap(ctypes.Structure):
            _fields_ = PyObject_HEAD + [ ('data', ctypes.c_void_p), ('size', ctypes.c_size_t) ]
        guts = mmap_mmap.from_address(id(self._tiles_mmap))
        return ctypes.c_void_p(guts.data) # WTF??

    def gettile(self, posn):
        x, y, z = posn
        offs = 16*(self.xdim*self.ydim*z + y*self.xdim + x)
        stoti, bmabui, grass, designation = struct.unpack("IIII", self._tiles_mmap[offs:offs+16])
        tile_id  = stoti & 0xffff
        mat_id   = stoti >> 16
        btile_id = bmabui & 0xffff # can also hold building_type+768
        bmat_id  = bmabui >> 16 
        grass_id = grass & 0xffff
        grass_amount = ( grass >> 16 ) & 0xff

        tilename = self.tileresolve[tile_id]
        btilename = self.tileresolve[btile_id]

        matname, matklass, matsubklass = self.mat_ksk.get(mat_id, None)
        bmatname, bmatklass, bmatsubklass = self.mat_ksk.get(bmat_id, None)
        grassname, grassklass, grasssubklass = self.mat_ksk.get(grass_id, None)
        
        return ( (mat_id, matname),   (tile_id, tilename),
                 (bmat_id, bmatname), (btile_id, btilename),
                 (grass_id, grassname, grass_amount), 
                  designation )
    
    def inside(self, x, y, z):
        return (  (x < self.xdim) and (x >= 0 ) 
                and  ( y < self.ydim) and (y >= 0)
                and (z < self.zdim) and (z>= 0))

def main():
    ap = argparse.ArgumentParser(description = 'full-graphics raws parser/compiler')
    ap.add_argument('-irdump', metavar='dfile', help="dump intermediate representation here")
    ap.add_argument('-aldump', metavar='fname', help="dump texture album here, creates fname.png and fname.mapping")
    ap.add_argument('dfprefix', metavar="../df_linux", help="df directory to get base tileset and raws from")
    ap.add_argument('-dump', nargs='?', metavar="dump-file", help="dump file name")
    ap.add_argument('-loud', nargs='*', help="spit lots of useless info", default=[])
    ap.add_argument('-cutoff-frame', metavar="frameno", type=int, default=96, help="frame number to cut animation at")        
    ap.add_argument('rawsdir', metavar="raws/dir", nargs='*', help="FG raws dir to parse", default=['fgraws'])
    pa = ap.parse_args()

    if pa.irdump:
        irdump = file(pa.irdump, 'w')
    else:
        irdump = None
    
    pygame.display.init()
    
    mo = MapObject(     
        dfprefix = pa.dfprefix,
        fgraws = pa.rawsdir,
        apidir = '',
        loud = pa.loud )

    if pa.irdump is not None:
        mo.use_dump(pa.dump, file(pa.irdump, 'w'))

if __name__ == '__main__':
    main()
