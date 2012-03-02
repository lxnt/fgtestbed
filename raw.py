#!/usr/bin/python

import os, os.path, glob, sys, xml.parsers.expat, time, math, mmap, pprint
import numpy as np
import pygame.image

__all__ = [ 'enumparser', 'tilepage', 'matiles', 'graphraws', 'enumaps', 'TSCompiler' ]

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
    
class Tilepage(object):
    def __init__(self, tpname):
        self.name = tpname
        self.path = None
        self.tdim = None
        self.pdim = None
        self.defs = {}
        self.surf = None
        
    def load(self):
        if not self.surf:
                surf = pygame.image.load(self.path)
                surf.convert_alpha()
                surf.set_alpha(None)
                self.surf = surf
        w,h = self.surf.get_size()
        if w != self.tdim[0]*self.pdim[0] or h != self.tdim[1]*self.pdim[1]:
            raise ValueError("size mismatch on {}: dim={}x{} pdim={}x{} tdim={}x{}".format(
                self.file, w, h, self.pdim[0], self.pdim[1], self.tdim[0], self.tdim[1]))


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
        just blits tiles in order of tilepage submission to album_w/max_tdim[0] columns """
    def __init__(self, std_tileset, album_w = 2048, dump_fname = None):
        self.mapping = {}
        self.album = []
        self.album_w = self.album_h = album_w
        self.dump_fname = dump_fname
        self.surf = pygame.Surface( ( album_w, album_w ), pygame.SRCALPHA, 32)
        self.current_i = self.current_j = 0
        
        stdts = Tilepage('std')
        stdts.pdim = (16, 16)
        stdts.path = std_tileset
        stdts.surf = pygame.image.load(std_tileset)
        w,h = stdts.surf.get_size()
        stdts.tdim = (w/16, h/16)
        
        self.max_tdim = stdts.tdim
        
        self.i_span = self.album_w / self.max_tdim[0]
        
        self.eatpage(stdts)

    def eatpage(self, page):
        if page.tdim[0] != self.max_tdim[0] or page.tdim[1] != self.max_tdim[1]:
            raise ValueError("tilepage {} has tiles of other than std_tdim size({}x{} vs {}x{})".format(
                page.name, page.tdim[0], page.tdim[1], self.max_tdim[0], self.max_tdim[1]))
        page.load()
        for j in xrange(page.pdim[1]):
            for i in xrange(page.pdim[0]):
                self.mapping[(page.name, i, j)] = (self.current_i, self.current_j)
                dx, dy = self.current_i*self.max_tdim[0], self.current_j*self.max_tdim[1]
                sx, sy = i*page.tdim[0], j*page.tdim[1]
                cell = pygame.Rect(sx, sy, page.tdim[0], page.tdim[1])
                self.surf.blit(page.surf, (dx, dy), cell)
                self.current_i += 1
                if self.current_i == self.i_span:
                    self.current_i = 0
                    self.current_j += 1
                    if self.current_j * self.max_tdim[1] > self.album_h:
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

    def maptile(self, page, s, t):
        return self.mapping[(page, s, t)]

    def get_album(self):
        "returns txsz tuple and bytes for the resulting texture album"
        min_h = self.max_tdim[1]*(self.current_j + 1)
        if min_h < self.album_h:
            self.reallocate(min_h - self.album_h)
        tw, th = self.max_tdim
        wt, ht = self.album_w/tw, min_h/th
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
        self.plant_tile_types = { # and default tile - set to '?' for the time being
            #'PICKED':        ( 'Shrub',       2,  2 ), # tile type guessed
            #'DEAD_PICKED':   ( 'ShrubDead',   2,  2 ), # tile type guessed
            'SHRUB':         ( 'Shrub',       2,  2 ), 
            'TREE':          ( 'Tree',       15,  3 ), 
            'SAPLING':       ( 'Sapling',     7, 14 ), 
            'DEAD_SHRUB':    ( 'ShrubDead',  15, 12 ),
            'DEAD_TREE':     ( 'TreeDead',   15, 15 ),
            'DEAD_SAPLING':  ( 'SaplingDead', 7, 14 ), 
        }
        # formats:
        # 1. (x,y) - reference to 16x16 tilepage
        # 2. (x,y,e) - same, but apply effect 'e'
        # 3. (None, i, e) - use tiledef variant i, apply effect 'e'
        #
        # effects are most likely something like lightening/darkening the color.
        #
        self.grass_tiles = {
            'Grass1StairUD':        ( 8,  5),
            'Grass1StairD':         (14,  3),
            'Grass1StairU':         (12,  3),
            'Grass2StairUD':        ( 8,  5),
            'Grass2StairD':         (14,  3),
            'Grass2StairU':         (12,  3),
            'GrassDryRamp':         ( 0,  0, 'dry'),
            'GrassDeadRamp':        (14,  1, 'dead'),
            'GrassLightRamp':       (14,  1, 'light'),
            'GrassDarkRamp':        (14,  1, 'dark'),
            'GrassDarkFloor1':      (None,  0, 'dark'), # None,0 means replace with tile variant 0
            'GrassDarkFloor2':      (None,  1, 'dark'),
            'GrassDarkFloor3':      (None,  2, 'dark'),
            'GrassDarkFloor4':      (None,  3, 'dark'),
            'GrassDryFloor1':       (None,  0, 'dry'),
            'GrassDryFloor2':       (None,  1, 'dry'),
            'GrassDryFloor3':       (None,  2, 'dry'),
            'GrassDryFloor4':       (None,  3, 'dry'),
            'GrassDeadFloor1':      (None,  0, 'dead'),
            'GrassDeadFloor2':      (None,  1, 'dead'),
            'GrassDeadFloor3':      (None,  2, 'dead'),
            'GrassDeadFloor4':      (None,  3, 'dead'),
            'GrassLightFloor1':     (None,  0, 'light'),
            'GrassLightFloor2':     (None,  1, 'light'),
            'GrassLightFloor3':     (None,  2, 'light'),
            'GrassLightFloor4':     (None,  3, 'light'), }
        
        self.soil_tiles = {
            'SoilWall':              None, # must be defined in raws.
            'SoilStairUD':          ( 8,  5, 'ramp'),
            'SoilStairD':           (14,  3, 'ramp'),
            'SoilStairU':           (12,  3, 'ramp'),
            'SoilRamp':             (14,  1, 'ramp'),
            'SoilFloor1':           ( 7,  2, 'floor'),
            'SoilFloor2':           (12,  2, 'floor'),
            'SoilFloor3':           (14,  2, 'floor'),
            'SoilFloor4':           ( 0,  6, 'floor'),
            'SoilWetFloor1':        ( 7,  2, 'wetfloor'),
            'SoilWetFloor2':        (12,  2, 'wetfloor'),
            'SoilWetFloor3':        (14,  2, 'wetfloor'),
            'SoilWetFloor4':        ( 0,  6, 'wetfloor'), }
        self.stone_tiles = {
            'StoneWall':             None,  # must defined in raws.
            # following just inherit DISPLAY_COLOR from raws
            # 'None' ones are replaced with question mark. (15,  3)
            'StoneStairUD':        ( 8,  5, 'ramp'),
            'StoneStairD':         (14,  3, 'ramp'),
            'StoneStairU':         (12,  3, 'ramp'),
            'StoneWallSmoothRD2':  ( 5, 13), # sse
            'StoneWallSmoothR2D':  ( 6, 13), # see
            'StoneWallSmoothR2U':  ( 4, 13), # nee
            'StoneWallSmoothRU2':  ( 3, 13), # nne 
            'StoneWallSmoothL2U':  (14, 11), # nww
            'StoneWallSmoothLU2':  (13, 11), # nnw
            'StoneWallSmoothL2D':  ( 8, 11), # sww
            'StoneWallSmoothLD2':  ( 7, 11), # ssw
            'StoneWallSmoothLRUD': (14, 12), # nsew | xx
            'StoneWallSmoothRUD':  (12, 12), # nse  | nnssee
            'StoneWallSmoothLRD':  (11, 12), # sew  | sseeww
            'StoneWallSmoothLRU':  (10, 12), # new  | nneeww
            'StoneWallSmoothLUD':  ( 9, 11), # nsw  | nnssww
            'StoneWallSmoothRD':   ( 9, 12), # se   | ssee
            'StoneWallSmoothRU':   ( 8, 12), # ne   | nnee
            'StoneWallSmoothLU':   (12, 11), # nw   | nnww
            'StoneWallSmoothLD':   (11, 11), # sw   | ssww
            'StoneWallSmoothUD':   (10, 11), # ns   | nnss
            'StoneWallSmoothLR':   (13, 12), # ew   | eeww
            'StoneFloor1':         ( 7,  2, 'floor'), 
            'StoneFloor2':         (12,  2, 'floor'),
            'StoneFloor3':         (14,  2, 'floor'),
            'StoneFloor4':         ( 0,  6, 'floor'),
            'StoneFloorSmooth':    (11,  2, 'floor'),
            'StoneBoulder':        (12, 14, 'ramp'),
            'StonePebbles1':       ( 7,  2, 'floor'), # same
            'StonePebbles2':       (12,  2, 'floor'), # as
            'StonePebbles3':       (14,  2, 'floor'), # floor
            'StonePebbles4':       ( 0,  6, 'floor'), 
            'StoneWallWorn1':      ( 0, 11),
            'StoneWallWorn2':      ( 0, 12),
            'StoneWallWorn3':      ( 0, 13),
            'StonePillar':         ( 7, 12),
            'StoneFortification':  (14, 12),
            'StoneRamp':           (14,  1, 'ramp')}
        
        self.mineral_tiles = {}
        for n,t in self.stone_tiles.items():
            self.mineral_tiles['Mineral' + n[5:]] = t
            
        self.constr_tiles = {}
        for n,t in self.stone_tiles.items():
            if n[5:] in ( 'Floor', 'Fortification','Ramp', 'Pillar'):
                self.constr_tiles['Constructed' + n[5:]] = t
            elif n.startswith('StoneWallSmooth'):
                self.constr_tiles['ConstructedWall' + n[len('StoneWallSmooth'):]] = t

    def mapcolor(self, color):
        try:
            return ( self.colortab[color[0]+8*color[2]], self.colortab[color[1]] )
        except IndexError:
            raise ValueError("unknown color {}".format(repr(color)))

    def compile(self, pages, mats):
        for page in pages:
            self.pageman.eatpage(page)
    
        for mat in mats:
            if mat is None:
                continue
            elif mat.type == 'stone':
                self._emit(self.stone_tiles, mat)
                self._emit(self.constr_tiles, mat)
            elif mat.type == 'soil':
                self._emit(self.soil_tiles, mat)
            elif mat.type == 'mineral':
                self._emit(self.mineral_tiles, mat)
                self._emit(self.constr_tiles, mat)
            elif mat.type == 'gem':
                self._emit(self.mineral_tiles, mat)
            elif mat.type == 'grass':
                self._emit(self.grass_tiles, mat)
            elif mat.type == 'plant':
                self._emit_plant(mat)
            elif mat.type == 'tree':
                self._emit_plant(mat) # fixes up color, must be first
                self._emit(self.constr_tiles, mat)
            elif mat.type == 'constr':
                self._emit(self.constr_tiles, mat)
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

                    

    def _apply_effect(self, tname, effect, color):
        if effect == 'floor':
            if tname.startswith('Stone'):
                return (0, 0, 1)
            return (color[0], 0, 0)
        elif effect == 'ramp':
            return (color[0], 0, 0)
        elif effect == 'wetfloor':
            return color
        elif effect == 'light':
            return color
            return (color[0], color[1], 1)
        elif effect == 'dark':
            return color
            return (color[0], color[1], 0)
        elif effect == 'dry':
            return color
            return (6, 6, 0)
        elif effect == 'dead':
            return (6, 6, 0)
        raise ValueError("Unknown effect '{}'".format(effect))
    
    def _emit(self, what, mat):
        try:
            mt = self.matiles[mat.name]
        except KeyError:
            mt = Mattiles(mat.name)
            self.matiles[mat.name] = mt
    
        for name, tdef in what.items():
            mt.tile(name)
            
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
        assert mat.name is not None            
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
            if len(l) == 0 or l[0] != '[':
                continue
            tags = l.split(']')[:-1]
            for tag in tags:
                try:
                    name, tail = tag.split(':', 1)
                    name = name[1:]
                    tail = tail.split(':')
                except ValueError:
                    name = tag[1:]
                    tail = []
                try:
                    handler(name, tail)
                except StopIteration:
                    return
                except :
                    print fna, lnum
                    print l
                    raise

    def tileparse(self, t):
        try:
            return int(t)
        except ValueError:
            pass
        if  (len(t) != 3 and 
              (t[0] != "'" or t[2] != "'")):
            raise ValueError("invalid literal for tile: \"{}\"".format(t))
        return ord(t[1])

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
        outputs whatever fgtestbed::mapobject expects,
        which is an object with the following attributes:
            self.pages = {}
            self.matiles = {}
        pages map pagenames to:
                class tilepage:
                    def __init__(self, tpname):
                        self.name = tpname
                        self.file = None
                        self.tdim = None
                        self.pdim = None
                        self.defs = {}

        matiles map material names to matiles objects,
            which have:
                self.tiles = {}
            which maps tilenames to """
    
    def __init__(self):
        self.mats = []
        self.otype = None
        self.mat = None
        self.default_grass_color = (2, 0, 1)
        self.default_tree_color  = (2, 0, 0)
        self.default_wood_color  = (6, 0, 0)
        self.plant_tile_types = (
            #'PICKED',
            #'DEAD_PICKED',
            'SHRUB',
            'TREE',
            'SAPLING',
            'DEAD_SHRUB',
            'DEAD_TREE',
            'DEAD_SAPLING' )
                
        self.soil_tags = ( 'SOIL', 'SOIL_OCEAN') # inorganics with these tags are marked as soil
        self.layer_tags = ( # inorganics with these tags are marked as (layer) stone
            'SEDIMENTARY',
            'SEDIMENTARY_OCEAN_SHALLOW',
            'SEDIMENTARY_OCEAN_DEEP',
            'IGNEOUS_EXTRUSIVE',
            'IGNEOUS_INTRUSIVE',
            'METAMORPHIC' )
        self.stone_tag = 'IS_STONE' # inorganics not matching above but with this tag are markes as minerals
        """ for the rest of inorganics only Constructed* tiles are defined.
            plants having [TREE:] tag also get Constructed* tiles defined for them
            this all is controlled by setting the .type attr to one of:
                'soil' : soil. generate only soil tiles
                'stone' : layer stone, generate stone and construction tiles
                'mineral' : vein stone, generate mineral and construction tiles
                'grass' : generate grass tiles
                'plant' : generate plant tiles 
                'tree'  : generate plant and construction tiles
                'constr' : generate construction tiles only.
                
            The compiler then emits corresponing tile definitions. 
            
            For tileset extensions the following overrides are possible:
            [OBJECT:FULL_GRAPHICS]
            [MAT:<matname>]
                [TILE:<tilename>]
                    ... various FG crap
            """

    def parse_rgba(self, f):
            if len(f) == 3:
                r = int(f[0],16) << 4
                g = int(f[1],16) << 4
                b = int(f[2],16) << 4
                a = 0xff            
            if len(f) == 4:
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

    def eat(self, *dirs):
        for path in dirs:
            for f in glob.glob(os.path.join(path, '*.txt')):
                self.parse_file(f, self.parse_tag)

    def parse_tag(self, name, tail):
        if name == 'OBJECT':
            if tail[0] not in ['INORGANIC', 'PLANT', 'FULL_GRAPHICS']:
                raise StopIteration
            self.otype = tail[0]
            return

        if self.otype == 'INORGANIC':
            if name == 'INORGANIC':
                self.mats.append(self.mat)
                self.mat = mat_stub('std', name = tail[0])
            elif name == 'TILE':
                self.mat.tile = self.tileparse(tail[0])
            elif name == 'DISPLAY_COLOR':
                self.mat.color = map(int, tail)
            elif name in self.soil_tags:
                self.mat.type  = 'soil'
            elif name in self.layer_tags:
                self.mat.type = 'stone'
            elif name in 'IS_STONE' and self.mat.type != 'stone':
                self.mat.type = 'mineral'
            elif name in 'IS_GEM':
                self.mat.type = 'gem'
            elif name == 'ITEMS_METAL': # bad substitute for IS_METAL, but I don't want to
                self.mat.type = 'constr' # implement USE_MATERIAL_TEMPLATE just yet
                
        elif self.otype == 'PLANT':
            if name == 'PLANT':
                self.mats.append(self.mat)
                self.mat = mat_stub('std', name = tail[0], type = "plant", 
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
            elif name == 'GRASS':
                self.mat.type = 'grass'
                self.mat.color = self.default_grass_color
            elif name == 'TREE':
                self.mat.type = 'tree'
            elif name == 'DISPLAY_COLOR':
                self.mat.color = map(int, tail)
            elif name.endswith('_TILE'):
                ttype = name[:-5]
                tile = self.tileparse(tail[0])
                if ttype not in self.plant_tile_types:
                    return
                try:
                    self.mat.tiles[ttype].tile = tile
                except KeyError:
                    self.mat.tiles[ttype] = mat_stub('std', tile = tile, color = self.default_tree_color) # set default color
                        
            elif name.endswith('_COLOR'):
                ttype = name[:-6]
                if ttype not in self.plant_tile_types:
                    return
                color = map(int, tail)
                try:
                    self.mat.tiles[ttype].color = color
                except KeyError:
                    self.mat.tiles[ttype] = mat_stub('std', color = color, tile = None)
            

    def get(self):
        self.mats.append(self.mat)
        return self.mats
   
def FGParser(Rawsparser0):
    """ not functional yet """
    def __init__(self):
        self.effects = {}
        self.tilesets = {}
        self.emits = {}
        self.matless_tiles = {}
        
        self.fgmat = None
        self.fgmats = []
        self.fgtile = None

    def parse_tag(self, name, tail):
        if name == 'OBJECT':
            if tail[0].upper() not in ['FULL_GRAPHICS']:
                raise StopIteration
            self.otype = tail[0].upper()
            return
        
        if name == 'TILESET':
            self.state = 'tileset'
            self.name = tail[0].upper()
            self.tilesets[self.name] = {}
            return
        elif name =='EFFECT':
            self.state = 'effect'
            self.name = tail[0].upper()
            self.tilesets[self.name] = {}
            return
        elif name == 'BUILDING':
            self.state = 'building'
            self.name = tail[0].upper()
            self.buildings[self.name] = {}
            return
        elif name == 'BUILDING_SIEGEENGINE':
            self.state = 'siege'
            self.name = tail[0].upper()
            self.siege[self.name] = {}
            return
        elif name == 'BUILDING_FURNACE':
            self.state = 'furnace'
            self.name = tail[0].upper()
            self.furnaces[self.name] = {}
            return
        elif name == 'BUILDING_WORKSHOP':
            self.state = 'workshop'
            self.name = tail[0].upper()
            self.workshops[self.name] = {}
            return
        elif name == 'TILEPAGE':
            if self.page is not None:
                self.pages[self.page.name] = self.page
            self.page = Tilepage(tail[0])
            self.fg_state = 'tilepage'
            return
        elif name == 'MATERIAL':
            self.state = 'emit'
            self.fgmats.append(self.fgmat)
            self.fgmat = mat_stub(self.page_name, name = tail[0], tiles = [])
            return
        elif name == 'TILE':
            self.fg_state = 'tiledef'
            self.fgmat.tiles.append(self.tile)
            self.tile = mat_stub(self.page_name, name = tail[0], frames = [])
            return
        elif name == 'CEL':
            self.fg_state = 'celdef'
            self.fgmat.tiles.append(self.tile)
            self.tile = mat_stub(self.page_name, name = tail[0], frames = [])
            return
            
        if self.fg_state == 'tilepage':
            if tag == 'FILE':
                self.page.file = tail[1]
            elif tag == 'TILE_DIM':
                self.page.tdim = (int(tail[1]), int(tail[2]))
            elif tag == 'PAGE_DIM':
                self.page.pdim = (int(tail[1]), int(tail[2]))
            elif tag == 'DEF':
                if f[3] == '':
                    return
                elif len(tail) == 4:
                    self.page.defs[tail[3]] = (int(tail[1]), int(tail[2]))
                elif len(tail) == 3:
                    idx = int(f[1])
                    s = idx % self.page.pdim[1]
                    t = idx / self.page.pdim[0]
                    self.page.defs[tail[2]] = ( s, t )
                else:
                    raise ValueError("Incomprehensible DEF")
        elif self.fg_state == 'material':
            pass
        elif self.fg_state == 'tiledef':
            if name == 'BLIT':
                """ revised blitdef: 
                  [BLIT:args]
                  args: 
                    one of:
                      defname
                      cel_index
                      cel_s:cel_t
                  pagenames are implicit for now.
                """
                
                try:
                    tmp = int(tail[0])
                except ValueError:
                    s, t = self.page.defs[tail[0]]
                else:
                    if len(tail) == 1:
                        s = tmp % self.page.pdim[0]
                        t = tmp / self.page.pdim[1]
                    else:
                        s = tmp
                        t = int(tail[1])
                self.tile.frames.append(('blit', self.page.name, s, t))
            elif tag == 'BLEND':
                self.tile.frames.append(('blend', self.parse_rgba(tail[1])))
            elif tag == 'GLOW':
                self.tile.frames.append(('glow', self.parse_rgba(tail[1])))
            elif tag == 'KEY':
                frameno = int(tail[1])
                self.tile.frames.append(('key', frameno))
                if self.maxframeno < frameno:
                    self.maxframeno = frameno


def work(dfprefix, moar_raws = [], dumpfile=None):
    init = Initparser(dfprefix)
    rawsdirs = [ os.path.join(dfprefix, 'raw', 'objects') ] + moar_raws
    pageman = Pageman(init.fontpath)
    parser = TSParser()
    map(parser.eat, rawsdirs)
    mats = parser.get()
    compiler = TSCompiler(pageman, init.colortab)
    matiles = compiler.compile([], mats)
    if dumpfile:
        compiler.dump(dumpfile)
        pageman.dump(dumpfile)
    maxframe = 0
    return pageman, matiles, maxframe


def main():
    p,m,ma = work(sys.argv[1], sys.argv[2:], 'matidu') 
    

if __name__ == '__main__':
    main()

