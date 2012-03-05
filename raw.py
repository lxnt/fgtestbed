#!/usr/bin/python

import os, os.path, glob, sys, xml.parsers.expat, time, math, mmap, pprint
import traceback, stat, copy
import numpy as np
import pygame.image

def parse_color(f):
    if f == 'MAT':
        return f
    if len(f) == 1 and len(f.split(',') == 3:
        #classic color.
        return f.split(',')
    elif len(f) == 3:
        r = int(f[0],16) << 4
        g = int(f[1],16) << 4
        b = int(f[2],16) << 4
        a = 0xff            
    elif len(f) == 4:
        r = int(f[0],16) << 4
        g = int(f[1],16) << 4
        b = int(f[2],16) << 4
        a = int(f[3],16) << 4
    elif len(f) == 6:
        r, g, b, a = int(f[:2], 16), int(f[2:4], 16), int(f[4:6], 16), 0xff
        a = 0xff
    elif len(f) == 8:
        r, g, b, a = int(f[:2], 16), int(f[2:4], 16), int(f[4:6], 16), int(f[6:8], 16)
    else:
        raise ValueError(f)
    return (r<<24)|(g<<16)|(b<<8)|a


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
    
class Mattiles(object):
    def __init__(self, matname, maxframe=1):
        assert matname is not None
        self.name = matname
        self.prelimo = []
        self.tiles = {}
        self._first_frame = True
        self._blit = self._blend = self._glow = None
        self._frame = 0
        self._tname = None
        self._keyframe_start = False
        self._maxframe = maxframe
        self._cut = False
        
    def xpand(self):
        frameseq = []
        white = (0xff, 0xff, 0xff, 0xff)
        for f in self.prelimo:
            blit, blend, glow, amt = f
            if blend is not None and glow is not None:
                # this is an old-school fg/bg blended tile.
                frameseq.append((blit, blend, glow))
                break
            
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
        assert tname is not None
        self._tname = tname
        
    def fin(self):
        if not self._keyframe_start:
            self.prelimo.append((self._blit, self._blend, self._glow, self._maxframe - self._frame))
        self.xpand()
        self._frame = 0
        self._cut = False
        
    def blit(self, t):
        if self._cut: return
        self._blit = t
        self._keyframe_start = False        
        
    def glow(self, rgba):
        if self._cut: return
        self._blend = None
        self._glow = rgba
        self._keyframe_start = False
        
    def blend(self, color):
        if self._cut: return
        if type(color) is tuple:
            self._blend, self._glow = color
        else:
            self._blend = color
            self._glow = None
        self._keyframe_start = False
        
    def key(self, frame):
        if self._cut: return
        if frame > self._maxframe:
            frame = self._maxframe
            self._cut = True
        if not self._keyframe_start:
            self.prelimo.append((self._blit, self._blend, self._glow, frame - self._frame))
        self._keyframe_start = True
        self._frame = frame


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
        try:
            tmp = int(ref[0])
        except ValueError:
            s, t = page.defs[ref[0]]
        else:
            if len(tail) == 1:
                s = tmp % page.pdim[0]
                t = tmp / page.pdim[1]
            else:
                s = tmp
                t = int(ref[1])
        
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

    def compile(self, materials, tilesets, celeffects, buildings):
        for material in materials:
            for emit in mat.emits:
                if type(emit) == Tileset:
                    tlist =  emit.tiles
                elif type(emit) == Tile:
                    tlist = [ emit ]
                else:
                    raise CompileError("unknown emit type '{}'".format(emit.__class__.__name__)
                for tile in tlist:
                    if mat.klass == 'NONE':
                        self._emit_none(tile)
                    elif mat.klass = 'INORGANIC':
                        self._emit_inorg(tile, mat)
                    elif mat.klass = 'PLANT':
                        self._emit_plant(tile, mat)
                    else:
                        raise CompileError("unknown mat class '{}'".format(mat.klass)
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
    
    def _emit_inorg(self, tile, mat):
        try:
            mt = self.matiles[mat.name]
        except KeyError:
            mt = Mattiles(mat.name)
            self.matiles[mat.name] = mt
    
            mt.tile(tile.name)
            
            if tdef is not None:
                if tdef[0] is None:
                    tdtile = mat.tiles[tdef[1]].tile
                    s, t = tdtile % 16, tdtile/16
                    color = mat.tiles[tdef[1]].color
                else:
                    s, t = tdef[0:2]
                    color = mat.color
                    
                if len(tdef) == 3:
                    color = self._apply_effect(name, tdef[2], color)
            else:
                s, t = mat.tile % 16, mat.tile/16
                color = mat.color
            mt.blit(self.pageman.maptile(mat.page, s, t))
            mt.blend(self.mapcolor(color))
        mt.fin()
    
    def _emit_plant(self, mat):
        try:
            mt = self.matiles[mat.name]
        except KeyError:
            mt = Mattiles(mat.name)
            self.matiles[mat.name] = mt
            
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

    def _emit_none(self, tile)
        pass
        
class mat_stub(object):
    def __init__(self, page, **kwargs):
        self.type = None
        if page is None:
            page = 'std'
        self.page = page
        for k,v in kwargs.items():
            setattr(self,k,v)


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
    
    def __init__(self, materials):
        self.all = []
        self.otype = None
        self.mat = None
        self.materials = materials
        
        self.plant_tile_types = (
            #'PICKED',
            #'DEAD_PICKED',
            'SHRUB',
            'TREE',
            'SAPLING',
            'DEAD_SHRUB',
            'DEAD_TREE',
            'DEAD_SAPLING' )
                
    def select(self, mat):
        for sel in self.materials:
            sel.match(mat)

    def parse_token(self, name, tail):
        if name == 'OBJECT':
            if tail[0] not in ['INORGANIC', 'PLANT', 'FULL_GRAPHICS']:
                raise StopIteration
            self.otype = tail[0]
            return

        if self.otype == 'INORGANIC':
            if name == 'INORGANIC':
                self.select(self.mat)
                self.mat = mat_stub('std', name = tail[0], klass=name)
            elif name == 'TILE':
                self.mat.tile = self.tileparse(tail[0])
            elif name == 'DISPLAY_COLOR':
                self.mat.color = map(int, tail)
            else:
                self.mat.others.append(name)
                
        elif self.otype == 'PLANT':
            if name == 'PLANT':
                self.select(self.mat)
                self.mat = mat_stub('std', name = tail[0], , klass=name, 
                                    tiles={}, colors={}, color = self.default_wood_color)
            elif name == 'GRASS_TILES':
                i = 0
                tiles = map(self.tileparse, tail)
                for tile in tiles:
                    try:
                        self.mat.tiles[i].tile = tile
                    except KeyError:
                        self.mat.tiles[i] = mat_stub('std', tile = tile)
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
                        self.mat.tiles[i] = mat_stub('std', color = color)
                    i += 1
            elif name == 'DISPLAY_COLOR':
                self.mat.color = map(int, tail)
                
            elif name.endswith('_TILE'):
                self.mat.others.append(name)
                ttype = name[:-5]
                tile = self.tileparse(tail[0])
                if ttype not in self.plant_tile_types:
                    return
                try:
                    self.mat.tiles[ttype].tile = tile
                except KeyError:
                    self.mat.tiles[ttype] = mat_stub('std', tile = tile, color = self.default_tree_color) # set default color
                        
            elif name.endswith('_COLOR'):
                self.mat.others.append(name)
                ttype = name[:-6]
                color = map(int, tail)
                try:
                    self.mat.tiles[ttype].color = color
                except KeyError:
                    self.mat.tiles[ttype] = mat_stub('std', color = color, tile = None)
            else:
                self.mat.others.append(name)
                    
            

    def get(self):
        self.select(self.mat)
        return self.mats


class Token(object):
    tokens = ()
    parses = ()
    contains = ()
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

class BlitInsn(Token):
    tokens = ( 'BLIT', 'BLEND', 'GLOW', 'KEY' )
    def __init__(self, name, tail):
        if name == 'BLIT':
            self.insn = 'blit'
            self.param = (tail[0], tail[1:])
        elif name == 'BLEND':
            self.insn = 'blend'
            self.param = parse_color(tail[0])
        elif name == 'GLOW':
            self.insn = 'glow'
            self.param = parse_color(tail[0])
        elif name == 'KEY':
            self.insn = 'key'
            self.param = int(tail[0])
        else:
            raise RuntimeError("wrong token got to BlitInsn: "+name)




class Cel(Token):
    tokens = ('CEL', )
    contains = BlitInsn.tokens
    
    def __init__(self, name, tail):
        self.framecount = 0
        self.prelimo = []
        self.effects = []
        self.no_add = False
        if len(tail) == 0:
            return
        elif len(tail) == 1: 
            if tail[0] != 'none':
                raise ParseError("short inline def '{}'".format(':'.join(tail)))
            self.prelimo = [ None ]
        elif len(tail) == 2: # just page, idx
            self.prelimo.append = ('blit', tail)
        elif len(tail) == 3: # page,s,t or page,idx,effect
            try:
                int(tail[2])
                self.prelimo.append('blit', tail)
            except ValueError:
                self.prelimo.append('blit', tail[:2])
                self.prelimo.append('effect', tail[2])
        else:
            self.prelimo.append('blit', tail:2])
            for e in tail[3:]:
                self.prelimo.append(e)
    
    def add(self, token):
        if type(token) == BlitInsn:
            self.prelimo.append(token.insn, self.param)
            return True

class Material(Token):
    tokens = ('MATERIAL', )
    parses = ('EMIT', 'COLOR_CLASSIC' )
    contains = ('TILE', )
    def __init__(self, name, tail):
        if tail[0] == 'none':
            self.nomat = True
            self.klass = 'nomat'
            return
        self.nomat = False
        if tail[0] not in ( 'INORGANIC', 'PLANT', 'NONE' ):
            raise ParseError("unknown material class " + tail[0])
        self.klass = tail[0]
        self.tokenset = tail[1:]
        self.emits = []
        self.mat_stubs = []
        
    def add(self, token):
        if type(token) == Tile:
            self.emits.append(token)
            return True

    def parse(self, name, tail):
        if name == 'EMIT':
            self.emits.append(tail)
            return True
        elif name == 'COLOR_CLASSIC':
            self.default_color = tail[0].split(',')

    def match(self, mat):
        if self.klass != mat.klass:
            return False
        for token in self.tokenset
            if token in mat.others:
                self.mat_stubs.append(mat)
                return True
        return False

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
        self.materials = []
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
        elif type(token) == Material:
            self.materials.append(token)
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
        loud = False
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

        if len(self.stack) == 1: # got root only.
            # insidious kludge. :(
            try:
                o = self.dispatch[name](name, tail)
            except KeyError:
                # NEH
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
    
    stdparser = TSParser()
    fgparser = AdvRawsParser( FullGraphics, CelEffect, Tile, Tileset, CelPage, Cel, BlitInsn, Building, Material )
    gsparser = AdvRawsParser( CreaGraphics, CreaGraphicsSet, CelPage )
    
    map(stdparser.eat, [stdraws])
    map(gsparser.eat, [stdraws])
    map(fgparser.eat, fgraws)
    
    mats = stdparser.get()
    fgdef = fgparser.get()
    cgset = gsparser.get()
    
    for page in fgdef.celpages: # + cgset.celpages: uncomment when creatures become supported
        self.pageman.eatpage(page)
    
    #print str(fgdef)
    #print "\n".join(map(lambda x: str(x), cgset.pages))
    compiler = TSCompiler(pageman, init.colortab)
    matiles = compiler.compile(mats, fgdef)
    
    if dumpfile:
        compiler.dump(dumpfile)
        pageman.dump(dumpfile)
    maxframe = 0
    return pageman, matiles, maxframe


def main():
    p,m,ma = work(sys.argv[1], sys.argv[2:], 'matidu') 
    

if __name__ == '__main__':
    main()

