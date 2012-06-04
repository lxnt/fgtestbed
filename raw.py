#!/usr/bin/python3.2
# -*- encoding: utf-8 -*-
"""
https://github.com/lxnt/fgtestbed
Copyright (c) 2012-2012 Alexander Sabourenkov (screwdriver@lxnt.info)

This software is provided 'as-is', without any express or implied
warranty. In no event will the authors be held liable for any
damages arising from the use of this software.

Permission is granted to anyone to use this software for any
purpose, including commercial applications, and to alter it and
redistribute it freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must
not claim that you wrote the original software. If you use this
software in a product, an acknowledgment in the product documentation
would be appreciated but is not required.

2. Altered source versions must be plainly marked as such, and
must not be misrepresented as being the original software.

3. This notice may not be removed or altered from any source
distribution.

"""

import os, os.path, glob, sys, xml.parsers.expat, time, re, argparse
import stat, copy, struct, math, mmap, ctypes
import logging, logging.config
from collections import namedtuple
import lxml.etree

from fractions import gcd
lcm = lambda a, b: abs(a * b) // gcd(a, b)

from py3sdl2 import *
from tokensets import *

# tileflags:
TCF_GRASS = 1
TCF_FAKEFLOOR = 2
TCF_TRUEFLOOR = 4
TCF_VOID = 8
TCF_UNKNOWN = 16
TCF_PLANT = 32

# blitmodes:
BM_NONE = 0
BM_ASIS = 1
BM_CLASSIC = 2
BM_FGONLY = 3
BM_CODEDBAD = 255

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
        f = os.path.join(dfapipath, names2files[name])
        self.enums = []
        self.enumc = []
        self.emap = {}
        self.emapc = {}
        self.gotit = False
        self.name = name
        self.parse(f)
        print("DfapiEnum({}): {} items".format(name, len(self.enums)))

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
        p.Parse(open(fle).read())
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
        if isinstance(key, int):
            try:
                return self.enums[key]
            except IndexError:
                return "-no-data-"
        else:
            return self.emap[key.upper()]


def flag_tiles(dfapipath):
    """
    Okay. Tileclasses/flags.
    What do we need:
     - is_grass flag : to select grass mat
     - needs_fakefloor flag: to know we've got to fake a floor for this tile
     - is_floor flag : for faking floors by looking at neighbours; for floor melding
     - is_openspace : for drawing open space as open, see
     
     most of this can be inferred from the df.tile-types.xml contents.
     
    """

    class enum_t(object):
        log = logging.getLogger('fgt.enum_t')
        debug = logging.getLogger('fgt.enum_t').debug
        def __init__(self, e, typedict):
            self._names = {}
            self._values = {}
            self.name = e.get('type-name')
            self.debug("__init__() name={}".format(self.name))
            attrtypes = { 'name': None, 'value': None }
            for ea in lxml.etree.XPath('enum-attr')(e):
                attrtypes[ea.get('name')] = ( typedict[ea.get('type-name', None)], ea.get('default-value') )
            
            nt = namedtuple(self.name, attrtypes.keys())
            
            i = 0
            for ei in lxml.etree.XPath('enum-item')(e):
                try:
                    i = int(ei.get('value'))
                except:
                    pass
                attvals = dict.fromkeys(attrtypes, None)
                attvals['name'] = ei.get('name')
                attvals['value'] = i
                for ia in lxml.etree.XPath('item-attr')(ei):
                    aname = ia.get('name')
                    atype = attrtypes[aname][0]
                    avalue = ia.get('value')
                    self.debug("({}, {}, {}, {})".format(aname, atype, avalue, atype(avalue)))
                    attvals[aname] = atype(avalue)
                for aname, avalue in attvals.items():
                    if aname != 'name' and avalue is None:
                        atype = attrtypes[aname][0]
                        adefval = attrtypes[aname][1]
                        attvals[aname] = atype(adefval)
                self.debug("attvals={} nt={}".format(repr(attvals), nt(**attvals)))
                self._names[attvals['name']] = self._values[attvals['value']] = nt(**attvals)
                i += 1
            
            typedict[self.name] = lambda x: self[x]
            
        def __getitem__(self, val):
            if isinstance(val, int):
                return self._values[val]
            elif isinstance(val, str):
                return self._names[val]
            else:
                raise TypeError("can't lookup with {}".repr(val))

    def parse_tiletypes(fname):
        parser = lxml.etree.XMLParser(remove_blank_text = True)
        root = lxml.etree.parse(fname, parser).getroot()
        for e in root.iter():
            if isinstance(e, lxml.etree._Comment):
                e.getparent().remove(e)
            else:
                e.tail = e.text = None

        typedict = { 
            None: lambda s: s,
            'bool': lambda s: True if s == 'true' else False 
        }
        for e in lxml.etree.XPath('enum-type')(root):
            rv = enum_t(e, typedict)

        return rv
        
    def flag_a_tile(tt):
        flags = 0
        if tt.name is None:
            return TCF_UNKNOWN
        
        if tt.name.startswith('Grass'):
            flags = flags | TCF_GRASS
        if tt.shape.name in ('TREE', 'SHRUB', 'SAPLING'):
            flags = flags | TCF_PLANT
        if (tt.material.name in ('DRIFTWOOD', 'CAMPFIRE', 'FIRE') or
           tt.shape.name in ('TREE', 'SHRUB', 'SAPLING', 'PEBBLES', 'BOULDER', 'STAIR_UP')):
               flags = flags | TCF_FAKEFLOOR 
        if ( tt.name.endswith(('FloorSmooth', 'Floor1', 'Floor2', 'Floor3', 'Floor4', 'Floor')) and
            tt.name not in ('ConstructedFloor', 'GlowingFloor')):
                flags = flags | TCF_TRUEFLOOR
        if (tt.shape.name in ('EMPTY', 'ENDLESS_PIT', 'RAMP_TOP') or tt.name == 'Void'):
            flags = flags | TCF_VOID
        return flags

    e = parse_tiletypes(os.path.join(dfapipath, 'df.tile-types.xml'))

    rv = CArray(None, "I", len(e._values))
    for ei in e._values.values():
        rv.set((flag_a_tile(ei),), ei.value)
    return rv

class Pageman(object):
    """ blits tiles in order of celpage submission to album.w//max(cdim.w) columns """
    def __init__(self, album_w = 2048, pages = []):
        self.mapping = {}
        self.pages = {}
        self.current_i = self.current_j = 0
        self.max_cdim = Size2(0,0)
        
        w_lcm = 1
        count = 0
        for page in pages:
            w_lcm = lcm(w_lcm, page.cdim.w)
            count += page.pdim.w * page.pdim.h
            
        fidx_side = int(math.ceil(math.sqrt(count)))
        self.findex = CArray(None, "HHHH", fidx_side*fidx_side)
        
        pages.sort(key = lambda p: p.cdim.h, reverse = True)
        
        album_w -= album_w%w_lcm # no space gets wasted when a row is full of cels of uniform size
        
        cx = 0 # stuff in cels, filling up partially occupied rows 
        cy = 0 # with cels of lesser height.
        row_h = pages[0].cdim.h # current row height.
        index = 0
        
        album = rgba_surface(album_w, album_w//8)
        for page in pages:
            self.pages[page.name.upper()] = page
            for j in range(page.pdim.h):
                for i in range(page.pdim.w):
                    src = Rect(i*page.pdim.w, j*page.pdim.h, page.cdim.w, page.cdim.h)
                    if cx >= album_w:
                        cx = 0
                        cy += row_h
                        row_h = page.cdim.h 
                        if cy + row_h > album.h: # grow it
                            a = rgba_surface(album.w, album.h*2)
                            a.blit(album, Rect(0, 0, a.w, album.h), Rect(0, 0, a.w, album.h))
                            album = a
                    dst = Rect(cx, cy, page.cdim.w, page.cdim.h)
                    album.blit(page.surface, dst, src)
                    self.mapping[(page.name.upper(), i, j)] = index
                    self.findex.set((cx, cy, page.cdim.w, page.cdim.h), i)
                    index += 1
                    cx += page.cdim.w
        # cut off unused tail
        a = rgba_surface(album.w, cy + row_h)
        a.blit(album, Rect(0, 0, a.w, album.h), Rect(0, 0, a.w, cy + row_h))
        self.surface = a
        self.count = index
        
    def dump(self, dumpdir):
        sk = sorted(self.mapping.keys())
        with open(os.path.join(dumpdir, 'album.mapping', 'w')) as f:
            f.write(str(self.surface) + "\n")
            f.write(repr(self.uniform) + "\n")
            for k in sk:
                f.write("{}:{}:{} -> {}:{} \n".format(
                        k[0], k[1], k[2], self.mapping[k][0], self.mapping[k][1]))
        self.surface.write_bmp(os.path.join(dumpdir, 'album.bmp'))

    def __call__(self, pagename, ref): # pagename comes in uppercased
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
                t = tmp // page.pdim[1]
        else:
            s, t = int(ref[0]), int(ref[1])
        return self.mapping[(pagename, s, t)]  

    def __str__(self):
        if len(self.pages) == 0:
            return "Pageman(empty)"
        return "Pageman(): {} pages {} tiles, font {}K; findex {}K; surface: {}".format(
            len(self.pages), self.count, self.surface.w*self.surface.h>>8, 
                len(self.findex.data)>>10, str(self.surface))

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
            return "mode=as is   blit={}".format(self.blit)
        elif self.mode == 2:
            return "mode=classic blit={} fg={:08x} bg={:08x}".format(self.blit, self.fg, self.bg)
        elif self.mode == 3:
            return "mode=fg-only blit={} fg={:08x}".format(self.blit, self.fg)
        elif self.mode == 4:
            return "mode=???"
        elif self.mode == 6:
            return "mode=PROFIT!!!"

    def __repr__(self):
        return self.__str__()

def Inflate(tilename, material, keyframes, ctx):
    """ Converts keyframes into seqs of basicframes. """
    
    if keyframes is None or len(keyframes) == 0:
        return None  # discard

    """ well in fact the effect belongs to the tile, not keyframe, but ... 
        they end up in the first keyframe ftb """
    effect = ctx.effects.get(keyframes[0]._effect, lambda c: c)
    """ """
    def lahy(kf):
        if kf._blend == 'MAT':
            kf._blend = material.display_color
        return kf

    # 'instantiate' MAT colors
    keyframes = list(map(lahy, copy.deepcopy(keyframes)))
    
    # for no reason at all 'mat_name/mat_idx' blits
    # are handled inside CelRef class. Boooo.
    if len(keyframes) == 1:
        blit = keyframes[0]._blit.emit(material, ctx.pageman)
        if blit is None:
            blend = (0, None, None)
        else:
            blend = keyframes[0]._blend.emit(ctx.colors, effect)
        
        
        return [ BasicFrame(blit, blend) ]

    def interpolate_keyframes(fromframe, toframe):
        assert fromframe != toframe
        rv = []
        mode0, fg0, bg0 = fromframe._blend.emit(material, ctx.colors, ctx.effects)
        if thisframe._glow:
            mode1, fg1, bg1 = toframe._blend.emit(ctx.colors, ctx.effects)
            if mode1 != mode0:
                raise CompileError("can't glow between two different blend modes")
        else:
            mode0, fg0, bg0 = mode1, fg1, bg1
            
        def _delta(a, b, amt): # delta is okay to be float
            return ( (b[0]-a[0])/amt, (b[1]-a[1])/amt, (b[2]-a[2])/amt, 0 )

        def _advance(base, delta, amt):
            return ( base[0] + delta[0]*amt, base[1] + delta[1]*amt, base[2] + delta[2]*amt, 1 )
        
        dfg = _delta(fg0, fg1, float(toframe.no - fromframe.no))
        dbg = _delta(bg0, bg1, float(toframe.no - fromframe.no))
        
        blit = fromframe._blit.emit(material, ctx.pageman)
        for no in range(fromframe.no, toframe.no):
            if fromframe.glow:
                blend = (mode0, _advance(fg0, dfg, no), _advance(bg0, dbg, no))
            else:
                blend = fromframe.blend.emit(self.ctx, material)
            self.frames[no] = BasicFrame(blit, blend)
        return rv

    rv = []
    frameno = 0
    while frameno < len(keyframes) - 1:
        rv += interpolate_keyframes(keyframes[frameno], keyframes[frameno+1], ctx)
    lafra = keyframes[-1]    
    
    if lafra.blit is None and lafra.blend is None: #loop back to 0th keyframe:
        lafra.blit = cel.frames[0].blit
        lafra.blend = cel.frames[0].blend
        rv += interpolate_keyframes(keyframes[-1], lafra, ctx)

    return rv

class ObjectCode(object):
    def __init__(self, ctx):
        self.map = {}
        #self.buildings = {}
        #self.items = {}
        self.ctx = ctx

    def add(self, mat, tile):
        bframes = Inflate(tile.name, mat, tile.cel.frames, self.ctx)
        try:
            self.map[(mat.name, mat.klass)][tile.name] = bframes # add or overwrite it
        except KeyError:
            self.map[(mat.name, mat.klass)] = { tile.name: bframes }

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
        
    @property
    def maxframe(self):
        seen = set([1])
        maxframes = 1
        for tilesframes in self.map.values():
            for frameseq in tilesframes.values():
                if len(frameseq) not in seen:
                    maxframes = lcm(maxframes, len(frameseq))
        return maxframes


class RawsParser0(object):
    log = logging.getLogger('fgt.raws')
    
    def parse_file(self, fna, handler):
        data = None
        for enc in ('utf8', 'cp1252'):
            try:
                data = open(fna, encoding=enc).read()
                break
            except UnicodeDecodeError:
                continue
        if data is None:
            raise RuntimeError("File '{}' is neither utf8 nor cp1252".format(fna))
        lnum = 0
        for l in map(lambda x: x.strip(), data.split('\n')):
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
                    if name not in  ( 'FILE',) and not name.endswith('FONT'):
                        tail = [x.upper() for x in tail]
                except ValueError:
                    name = token[1:].upper()
                    tail = []
                try:
                    handler(name, tail)
                except StopIteration:
                    self.log.debug("{} stopiteration {}:{}".format(self.__class__.__name__, fna, lnum))
                    return
                except :
                    self.log.exception("unexpected exception at {}:{}:{}".format(fna, lnum, l.rstrip()))
                    raise SystemExit
        self.log.debug("{} parsed {}".format(self.__class__.__name__, fna))

    @staticmethod
    def tileparse(t):
        """ parses stdraws' celspecs in the form of:
                int in a string 
                quoted character is a string (think '`')
            to an single int.
            """

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
                    if os.path.basename(path) == 'text':
                        continue # ignore strangeness under raw/objects/text
                    nextpaths += glob.glob(os.path.join(path, '*'))
                elif path.lower().endswith('.txt'):
                    final.append(path)
            paths = nextpaths

        if numit == limit:
            raise RuntimeError("{} paths scanned: something's wrong".format(numit))

        for f in final:
            self.parse_file(f, self.parse_token)

class ObjectHandler(RawsParser0):
    """ handles OBJECT tokens so that raws get parsed in one pass
        and less confustion ensues or code gets duplicated """
    def __init__(self, *object_klasses, **kwargs):
        self.object_klasses = {}
        self.objects = {}
        self.stack = []
        for ok in object_klasses:
            self.object_klasses[ok.object_klass] = ok
    
    def parse_token(self, name, tail):
        if name == 'VERSION': 
            return
        elif name == 'OBJECT':
            self.finalize_object()
            if len(self.stack) == 1:
                if tail[0] != self.stack[-1].object_klass:
                    self.stack.pop()
            if len(self.stack) == 0:
                try:
                    o = self.objects[tail[0]]
                except KeyError:
                    try:
                        ok = self.object_klasses[tail[0]]
                    except KeyError:
                        self.log.debug("Ignoring unhandled object klass {}".format(tail[0]))
                        raise StopIteration
                    o = ok(name, tail)
                    self.objects[tail[0]] = o
                self.stack.append(o)
            return
    
        # see if current object can handle the token itself.        
        if name in self.stack[-1].parses:
            self.log.debug("{} parses {}".format(self.stack[-1].__class__.__name__, name))
            self.stack[-1].parse(name, tail)
            return True
        
        # see if current object is eager to contain it
        try:
            self.stack.append(self.stack[-1].contains[name](name, tail))
            return True
        except KeyError:
            pass # alas
        except TypeError:
            self.log.exception("hfs? {}".format(type(self.stack[-1])))
            raise
       
        # got some stack to unwind
        self.log.debug('unwinding stack: {} for {}'.format(' '.join(map(lambda x: x.__class__.__name__, self.stack)), name))

        o = self.stack.pop(-1)
        if self.stack[-1].add(o):
            self.log.debug("{} accepted {}".format(self.stack[-1].__class__.__name__, o.__class__.__name__))
        else:
            self.log.debug("{} did not accept {}".format(self.stack[-1].__class__.__name__, o.__class__.__name__))
        
        # continue unwinding stack until we've put the token somewhere.
        self.parse_token(name, tail)
        return

    def finalize_object(self):
        while len(self.stack) > 1:
            self.log.debug('fin(): unwinding stack: {}'.format( ' '.join(map(lambda x: x.__class__.__name__, self.stack))))
            o = self.stack.pop(-1)
            if self.stack[-1].add(o):
                self.log.debug("fin(): {} accepted {}".format(self.stack[-1].__class__.__name__, o.__class__.__name__))
            else:
                self.log.debug("fin(): {} did not accept {}".format(self.stack[-1].__class__.__name__, o.__class__.__name__))

    def get(self, oklass):
        self.finalize_object()
        return self.objects[oklass.object_klass]
        

class ColorMap(object):
    def __init__(self, colors):
        self.tab = colors
    
    def __getitem__(self, color):
        try:
            return ( self.tab[color[0]+8*color[2]], self.tab[color[1]] )
        except IndexError:
            raise KeyError("unknown color {}".format(repr(color)))
        except TypeError:
            raise ValueError("bogus color {}".format(repr(color)))

class InitParser(RawsParser0):
    def __init__(self, dfprefix):
        init = os.path.join(dfprefix, 'data', 'init', 'init.txt')
        colors = os.path.join(dfprefix, 'data', 'init', 'colors.txt')
        self.dfprefix = dfprefix
        self.colortab = [0xff]*16
        self.fontpath = None
        self.fonts = {}
        self.parse_file(init, self.init_handler)
        self.parse_file(colors, self.colors_handler)
    
    def colors_handler(self, name, tail):
        colorseq = "BLACK BLUE GREEN CYAN RED MAGENTA BROWN LGRAY DGRAY LBLUE LGREEN LCYAN LRED LMAGENTA YELLOW WHITE".split()
        cshift = { 'R': 24, 'G': 16, 'B': 8, 'A': 0 }        
        color, channel = name.split('_')
        self.colortab[colorseq.index(color)] = self.colortab[colorseq.index(color)] | int(tail[0])<< cshift[channel]
        
    def init_handler(self, name, tail):
        if name.endswith('FONT'):
            self.fonts[name] = os.path.join(self.dfprefix, 'data', 'art', tail[0])
        elif name == 'WINDOWED':
            self.windowed = tail[0] == 'YES'
        elif name == 'GRAPHICS':
            self.graphics = tail[0] == 'YES'
            
    def get(self):
        if self.graphics:
            if self.windowed:
                font = self.fonts['GRAPHICS_FONT']
            else:
                font = self.fonts['GRAPHICS_FULLFONT']
        else:
            if self.windowed:
                font = self.fonts['FONT']
            else:
                font = self.fonts['FULLFONT']
        return font, ColorMap(self.colortab)

class Color(object):
    @staticmethod
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

    def __init__(self, coldef):
        if coldef == 'NONE':
            self.color = None
        elif len(coldef) == 1:
            self.color = self.parse_rgb(coldef[0])
        elif len(coldef) == 2:
            self.color = (self.parse_rgb(coldef[0]), self.parse_rgb(coldef[1]))
        elif len(coldef) == 3:
            self.color = list(map(int, coldef))
        else:
            raise ParseError("can't parse colordef {}".format(':'.join(color)))
        
    def __str__(self):
        return "({})".format(self.color)
        
    def emit(self, colormap, effect = None):
        """ returns a triplet: mode, fg, bg. 
            mode is :
            0 - discard       (0, None, None)
            1 - no blending   (1, None, None)
            2 - classic fg/bg (2, fg, bg)
            3 - fg only       (3, fg, None)
            4 - ???           ("?", "?", "?")
            5 - PROFIT!!!     (5, "PROFIT", "!!!")
        """

        if self.color == 'NONE' or self.color is None: # discard
            return (0, None, None) 
        elif self.color in ('ASIS', 'AS_IS'):
            return (1, None, None)
        elif isinstance(self.color, int): # fg
            return (3, self.color, None)
        elif len(self.color) == 2: # fg,bg
            return (2, self.color[0], self.color[1])
        elif len(self.color) == 3: # fg,bg,br triplet
            if effect:
                fg, bg = colormap[effect(self.color)]
            else:
                fg, bg = colormap[self.color]
            return (2, fg, bg)

class CelRef(object):
    """ celref can """
    def __init__(self, page = 'STD', idx = None, st = None, cref = None):
        if isinstance(idx, str):
            idx = RawsParser0.tileparse(idx)
        
        self.page = page
        self.cref = cref
        self.idx = idx if idx is None else [ int(idx) ]
        self.st = st
        if st is None:
            return
        elif st == 'MAT':
            assert idx is None
            assert page == 'STD'
            return
        self.st = list(map(int, st))

    def emit(self, material, pageman):
        """ returns st tuple as returned by the pageman lookup """
        if self.st == 'MAT':
            assert self.cref is not None
            cd = material.getceldef(self.cref)
            return cd if cd is None else cd[0].emit(material, pageman)
        elif self.st is not None:
            assert self.cref is None
            assert self.idx is None
            return pageman(self.page, self.st)
        else:
            if self.cref is not None:
                assert self.idx is None
                return pageman(self.page, self.cref)
            else:
                return pageman(self.page, self.idx)

    def __str__(self):
        return "CelRef(page={} idx={} st={} cref={})".format(self.page, self.idx, self.st, self.cref)

class CelDiscard(object):
    def emit(self, un, used):
        return None

class RawsObject0(object):
    def __init__(self, name, klass):
        self.name = name
        self.klass = klass
        self._basic_mat = None        
        self.tokens = set()
        self.celdefs = {}

    def pad_celdefs(*args, **kwargs):
        pass

    def add(self, name):
        self.tokens.add(name)

    def __contains__(self, what):
        return what in self.tokens

    def __str__(self):
        return "{}({})".format(self.klass, self.name)

    def _addcref(self, tname, cref):
        try:
            self.celdefs[tname] = ( cref, self.celdefs[tname][1] )
        except KeyError:
            self.celdefs[tname] = ( cref, None )
        
    def _addcolor(self, tname, color):
        try:
            self.celdefs[tname] = ( self.celdefs[tname][0], color )
        except KeyError:
            self.celdefs[tname] = ( None, color )
    
    def getceldef(self, mdt_name):
        return self.celdefs.get(mdt_name, None)

class Plant(RawsObject0):
    """ a plant (and not a plant material) 
        has multiple celdefs.
        celrefs are for std 16x16 font.
    """
    TREE_CELDEFS = { # tiletype -> (blit,blend)
        'TREE':         (CelRef(st = (5,  0)), Color((2, 0, 1))),
        'SAPLING':      (CelRef(st = (7, 14)), Color((2, 0, 1))),
        'DEAD_TREE':     (CelRef(st = (6, 12)), Color((6, 0, 0))),
        'DEAD_SAPLING':  (CelRef(st = (7, 14)), Color((6, 0, 0))), }
    SHRUB_CELDEFS = {
        'DEAD_SHRUB':    (CelRef(st = (2, 2)), Color((6, 0, 0))),
        'SHRUB':        (CelRef(st = (2, 2)), Color((2, 0, 1))), }
    GRASS_CELDEFS = { # mdt_idx -> (blit,blend)); 
    # in fact mdt_idx can be anything that doesn't contain ':'
    # called 'index' since it's used in grass only whose raws aren't that advanced
        '0':       (CelRef(idx = 39), Color((2, 0, 1))), # GRASSwhateverFLOOR0 
        '1':       (CelRef(idx = 44), Color((2, 0, 0))),
        '2':       (CelRef(idx = 96), Color((6, 0, 1))),
        '3':       (CelRef(idx = 39), Color((6, 0, 0))), }

    def __init__(self, name):
        super(Plant, self).__init__(name, 'PLANT')
        self._padded = False # see pad_celdefs()

    @property
    def basic_mat(self):
        return self._basic_mat

    @basic_mat.setter
    def basic_mat(self, mat):
        assert self._basic_mat is None
        self._basic_mat = mat
        
    def pad_celdefs(self):
        # pad read celdefs with defaults in case some are missing,
        # relies on the fact that a plant can't be a shrub and a tree
        # at the same time.
        # can't do that in constructor since no data on plant type
        def _pad(src):
            for tname, v in src.items():
                blit, blend = v
                if tname not in self.celdefs:
                    self._addcref(tname, blit)
                    self._addcolor(tname, blend)
                elif self.celdefs[tname][0] is None:
                    self._addcref(tname, blit)
                elif self.celdefs[tname][1] is None:
                    self._addcolor(tname, blend)
        
        if 'TREE' in self:
            _pad(self.TREE_CELDEFS)
        elif 'GRASS' not in self:
            _pad(self.SHRUB_CELDEFS)
        else: # GRASS.
            _pad(self.GRASS_CELDEFS)

        self.pad_celdefs = super(Plant, self).pad_celdefs # pass on next calls

    def token(self, name, tail):
        if name == 'GRASS_TILES':
            i = 0
            for t in tail:
                i += 1
                self._addcref(i, t)
        elif name == 'GRASS_COLORS':
            colors = list(map(int, tail))
            fgs = colors[0::3]
            bgs = colors[1::3]
            brs = colors[2::3]
            i = 0
            for fg in fgs:
                i += 1
                self._addcolor(i, Color((fg, bgs.pop(0), brs.pop(0))))
        elif name.endswith('_TILE'):
            self._addcref(name[:-5], CelRef(idx=tail[0]))
        elif name.endswith('_COLOR'):
            self._addcolor(name[:-6], Color(tail))
        self.add(name)

class Inorganic(RawsObject0):
    """ an inorganic material 
        has a single cref named 'WALL' for StoneWall/MineralWall tiles. """
    def __init__(self, name):
        super(Inorganic, self).__init__(name, 'INORGANIC')
        
    def token(self, name, tail):
        if name == 'DISPLAY_COLOR':
            self._dc = Color(tail)
            self._addcolor('WALL', self._dc)
        elif name == 'TILE':
            self._addcref('WALL', CelRef(idx = tail[0]))
            
        self.add(name)

    def update(self, template):
        self.tokens.update(template.parsed)
        self._dc = template.display_color
        self._t = template.tile

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
            self._dc = Color(tail)
        self.tokens.add(name)

    def getceldef(self, mdt_name):
        self.parent.pad_celdefs()
        return self.parent.getceldef(mdt_name)
    
    def pad_celdefs(self):
        self.parent.pad_celdefs()
    
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

class NoneMat(object):
    name = 'NONEMAT'
    klass = 'BUILTIN'
    display_color = Color('NONE')
    pad_celdefs = lambda x: None

class TSParser(RawsParser0):
    def __init__(self, templates, materialsets):
        self.all = []
        self.otype = None
        self.mat = None
        self.derived_mat = None
        self.materialsets = materialsets
        self.templates = templates
    
    def select(self):
        if self.mat is not None:
            matched = False
            for sel in self.materialsets:
                if sel.match(self.mat):
                    matched = True
            if not matched:
                self.log.debug("no matset accepted {}".format(self.mat))
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
            self.log.exception("not in " + repr(self.templates.keys()))
            raise

    def get(self):
        self.select()
        return self.materialsets

class Token(object):
    tokens = ()
    parses = ()
    contains = {}

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
        self._surf = None

    def __str__(self):
        return '{}:{} pdim={} cdim={} surf={}'.format(self.name, self.file, 
            self.pdim, self.cdim, self._surf)

    def __repr__(self):
        return self.__str__()            
            
    def parse(self, name, tail):
        if name == 'FILE':
            self.file = tail[0]
        elif name in ('CEL_DIM', 'TILE_DIM'):
            self.cdim = Size2(int(tail[0]), int(tail[1]))
        elif name == 'PAGE_DIM':
            self.pdim = Size2(int(tail[0]), int(tail[1]))
        elif name == 'DEF':
            if len(tail) == 3:
                self.defs[tail[0]] = (int(tail[1]), int(tail[2]))
            elif len(tail) == 2:
                idx = int(tail[1])
                s = idx % self.pdim.w
                t = idx // self.pdim.w
                self.defs[tail[0]] = ( s, t )
            else:
                raise ValueError("Incomprehensible DEF")

    def _check_dim(self, surf):
        if surf.w != self.cdim.w*self.pdim.w or surf.h != self.cdim.h*self.pdim.h:
            raise ValueError("size mismatch on {}: surf={}x{} pdim={} cdim={}".format(
                self.file, surf.w, surf.h, self.pdim, self.cdim))

    @property
    def surface(self):
        if not self._surf:
            self._surf = rgba_surface(self.file)
            self._check_dim(self._surf)
        return self._surf

class StdCelPage(CelPage):
    name = 'STD'
    def __init__(self, filename):
        self.pdim = Size2(16, 16)
        self.file = filename
        self._surf = rgba_surface(filename=filename)
        self.cdim = Size2(self._surf.w//16, self._surf.h//16)
        self._check_dim(self._surf)

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

class KeyFrame(object):
    def __init__(self, number, idef = []):
        self.no = number
        self._blit = CelDiscard()
        self._blend = None
        self._effect = None
        self._glow = False

        if len(idef) == 0:
            return
        # parse inline celdef (only place where effects are allowed)
        #  -- moderately ugly hack.
        self._blend = 'MAT' # inline celdefs always rely on material color
        if idef[0] == 'MAT':
            if len(idef) == 1:
                self._blit = CelRef(st='MAT', idx=0) # (first) material-defined tile from the std tileset
            elif len(idef) == 2: # (MAT, mdt_ref) # mdt = 'material-defined tile'
                self._blit = CelRef(st='MAT', cref=idef[1])
            elif len(idef) == 3: # (MAT, mdt_ref, effect)
                self._blit =  CelRef(st='MAT', cref=idef[1])
                self._effect = idef[2]
        elif idef[0] == 'NONE': # explicit discard
            return
        elif len(idef) == 2: # ( page, idx)  or (page, def)
            try:
                self._blit = CelRef(page=idef[0], idx=idef[1]) 
            except ValueError:
                self._blit = CelRef(page=idef[0], cdef=idef[1])
        elif len(idef) == 3: # ( page, s, t) or (page, idx, effect) or (page, def, effect)
            try:
                self._blit = CelRef(page=idef[0], st=idef[1:])
            except ValueError:
                self._effect = idef[2]
                try:
                    self._blit = CelRef(page=idef[0], idx=int(idef[1]))
                except ValueError:
                    self._blit = CelRef(page=idef[0], cref=idef[1])
        elif len(idef) == 4: # ( page, s, t, effect )
            self._blit = CelRef(page=idef[0], st=idef[1:2])
            self._effect = idef[3]
        else:
            raise ParseError("Incomprehensible inline celdef '{}'".format(':'.join(idef)))

    def blit(self, cref):
        assert type(cref) in ( list, tuple )
        self._blit = CelRef(page=cref[0], st=cref[1:])

    def blend(self, color):
        assert type(color) in ( list, tuple )
        self._blend = Color(color)
        
    def glow(self):
        assert not self._inline
        self._glow = True
        
    def __str__(self):
        return "page={} blit={} blend={}".format(self.page, self._blit, self._blend)

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

    def __str__(self):
        try:
            f = self.frames[0]
        except IndexError:
            f = None
        return "CEL({} frames), first=({})".format( len(self.frames), f)

    def noparse(self, name, tail):
        raise AlreadyFinalizedError
        
    def fin(self):
        self.frames.append(self.current_frame)
        self.parse = self.noparse

class Tile(Token):
    tokens = ( 'TILE', )
    contains = { 'CEL': Cel }

    def __init__(self, name, tail):
        self.name = tail.pop(0)
        self.cel = None
        if len(tail) > 0: # embedded celdef
            self.add(Cel(None, tail))
            
    def add(self, token):
        if isinstance(token, Cel):
            self.cel = token
            return True
            
    def __str__(self):
        return "TILE({}, {})".format(self.name, str(self.cel))

    def __repr__(self):
        return self.__str__()        
        
class TileSet(Token):
    tokens = ('TILESET', )
    contains = { 'TILE': Tile }
    
    def __init__(self, name, tail):
        self.name = tail[0]
        self.tiles = []
        
    def add(self, token):
        if isinstance(token, Tile):
            self.tiles.append(token)
            return True

    def __str__(self):
        return "TILESET({}: {})".format(self.name, ' '.join(map(str, self.tiles)))

    def __repr__(self):
        return self.__str__()

def TSCompile(materialsets, tilesets, ctx):
        """ output:
            map: { material: { tiletype: [ basicframe, basicframe, ... ], ... }, ... }
        """

        rv = ObjectCode(ctx)
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
                for tile in tlist:
                    for mat in materialset.materials:
                        if mat.klass == 'SOAP':
                            # SOAPP! SOAPP! SKIPP ITT! SKIPP ITT!
                            # (soap being hardmapped to a built-in mat in the dumper for now)
                            continue
                        mat.pad_celdefs()
                        rv.add(mat, tile)
        return rv

class RpnExpr(object):
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
    contains =  { 'TILE': Tile }
    def __init__(self, name, tail):
        self.tiles = []
        self.tilesets = []
        self.materials = []
        self.buildings = False
        if tail[0] == 'NONE':
            self.nomat = True
            self.klass = 'NONE'
            self.materials = [ NoneMat() ] # ze nonemat
            self.expr = None
            return
        self.nomat = False
        self.expr = RpnExpr(tail)
        
    def add(self, token):
        if isinstance(token, Tile):
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
        if not self.expr:
            return False # nonemat matches no mat
        try:
            rv = self.expr(mat)
        except AttributeError: # attempt at mat.parent on inorganic mat
            return False
        assert isinstance(rv, bool)
        if rv: self.materials.append(mat)
        return rv

    def __str__(self):
        rv =  "MaterialSet(selector={}, emits={})".format(self.expr, ', '.join([str(x) for x in self.tilesets]))
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
    contains =  { 'CEL': Cel }
    def __init__(self, name, tail):
        self.name = tail[0]
        self.current_def = []
        self.dim = (1,1)
        
    def add(self, token):
        if isinstance(token, Cel):
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
    object_klass = 'FULL_GRAPHICS'
    contains = { 
        'TILESET': TileSet,
        'EFFECT': CelEffect,
        'CEL_PAGE': CelPage,
        'TILE_PAGE': CelPage,
        'MATERIAL':MaterialSet,
        'BUILDING': Building,
    }
            
    def __init__(self, name, tail):
        if tail[0] != 'FULL_GRAPHICS':
            raise StopIteration
        self.tilesets = {}
        self.materialsets = []
        self.celpages = []
        self.celeffects = {}
        self.buildings = {}
        self.tileclasses = []
        self.tcflags = {}
        
    def add(self, token):
        if isinstance(token, TileSet):
            self.tilesets[token.name] = token
        elif isinstance(token, CelEffect):
            self.celeffects[token.name] = token
        elif isinstance(token, CelPage):
            self.celpages.append(token)
        elif isinstance(token, MaterialSet):
            self.materialsets.append(token)
        elif isinstance(token, Building):
            self.buildings[token.name] = token
        elif isinstance(token, TcFlag):
            self.tcflags[token.name] = token
        elif isinstance(token, FullGraphics):
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

class MaterialTemplate(Token):
    tokens = ('MATERIAL_TEMPLATE',)
    parses = MATERIAL_TEMPLATE_TOKENS

    def __init__(self, name, tail):
        self.name = tail[0]
        self.display_color = None
        self.tile = None
        self.parsed = set()
        
    def parse(self, name, tail):
        if name == 'DISPLAY_COLOR':
            self.display_color = Color(tail)
        elif name == 'TILE':
            self.tile = tail[0]
        self.parsed.add(name)

class MaterialTemplates(Token):
    tokens = ('OBJECT',)
    contains = { 'MATERIAL_TEMPLATE': MaterialTemplate }
    object_klass = 'MATERIAL_TEMPLATE'

    def __init__(self, name, tail):
        if tail[0] != 'MATERIAL_TEMPLATE':
            raise StopIteration
        self.templates = {}
    
    def add(self, token):
        if isinstance(token, MaterialTemplate):
            self.templates[token.name] = token
            return True

class CreaGraphics(Token):
    tokens = ('CREATURE_GRAPHICS',)
    parses = CREATURE_GRAPHICS_TOKENS

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
    object_klass = 'GRAPHICS'
    contains = { 
        'CREATURE_GRAPHICS': CreaGraphics,
        'TILE_PAGE': CelPage,
        'CEL_PAGE': CelPage, 
    }

    def __init__(self, name, tail):
        if tail[0] != 'GRAPHICS':
            raise StopIteration
        self.pages = []
        self.cgraphics = {}
            
    def add(self, token):
        if isinstance(token, CelPage):
            self.pages.append(token)
            return True
        elif isinstance(token, CreaGraphics):
            self.cgraphics[token.race] = token
            return True



class MapObject(object):
    def __init__(self, dfprefix,  fgraws=[], apidir='', cutoff = -1):
        self.dispatch_dt = struct.Struct("HH") # s t GL_RG16UI - 32 bits, all used.
        self.blitcode_dt = struct.Struct("IIII") # cst mode fg bg GL_RGBA32UI - 128 bits. 16 bits unused.
        self.data_dt = struct.Struct("IIII") # stoti bmabui grass designation GL_RGBA32UI - 128 bits. 16 bits unused.
        self._mmap_fd = None
        self.cutoff = cutoff
        
        self.tileresolve = DfapiEnum(apidir, 'tiletype')
        self.building_t = DfapiEnum(apidir, 'building_type')
        self.tileflags = flag_tiles(apidir)
        
        self._parse_raws(dfprefix, fgraws)

    def use_dump(self, dumpfname, dump_dir=None):
        if dump_dir:
            self.pageman.surface.write_bmp(os.path.join(dump_dir, 'album.bmp'))
            irdump = open(os.path.join(dump_dir, 'intrep.dump'), 'w')
        else:
            irdump = None

        self._parse_dump(dumpfname)
        self._assemble_blitcode(self._objcode, irdump)
        if dump_dir:
            self.dispatch.dump(open(os.path.join(dump_dir, 'dispatch.dump'), 'wb'))
            self.blitcode.dump(open(os.path.join(dump_dir, 'blitcode.dump'), 'wb'))

        self._mmap_dump(dumpfname)
        
    def _parse_raws(self, dfprefix, fgraws):
        log = logging.getLogger('fgt.raws')
        stdraws = os.path.join(dfprefix, 'raw')
        
        boo = ObjectHandler(MaterialTemplates, FullGraphics, CreaGraphicsSet)
        boo.eat(stdraws, *fgraws)

        mtset = boo.get(MaterialTemplates)
        fgdef = boo.get(FullGraphics)
        cgset = boo.get(CreaGraphicsSet)
        
        log.info("ObjectHandler done.")

        stdparser = TSParser(mtset.templates, fgdef.materialsets)
            
        stdparser.eat(stdraws)
        materialsets = stdparser.get()

        log.info("TSParser done.")

        fontpath, colormap = InitParser(dfprefix).get()
        fgdef.celpages.append(StdCelPage(fontpath))
        self.pageman = Pageman(pages = fgdef.celpages) # + cgset.celpages) when creatures become supported
        log.info(str(self.pageman))

        ctx = namedtuple("ctx", "pageman colors effects")(
            pageman = self.pageman,
            colors = colormap,
            effects = fgdef.celeffects)
        
        self._objcode = TSCompile(materialsets, fgdef.tilesets, ctx)
        
        log.info("TSCompile done.")
    
    def _mmap_dump(self, dumpfname):
        log = logging.getLogger('fgt.mapdata')
        
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
            log.exception("fsize: {} tiles {},{} effects: {}".format(fsize, 
                self.tiles_offset, self.tiles_size, self.flows_offset ))
            raise
        self.mapdata = CArray(self._tiles_mmap, 'IIII', self.dim.x, self.dim.y, self.dim.z)
        log.info("loaded {}x{}x{} {}M".format(self.dim.x, self.dim.y, self.dim.z, self.tiles_size >>20))

    def _parse_dump(self, dumpfname):
        self.mat_ksk = {}
        self.mat_ids = {}
        HEADER_SIZE = 264
        dumpf = open(dumpfname)
        self.max_mat_id = -1
        # read header
        l = dumpf.readline()
        if not l.startswith("origin:"):
            raise TypeError("Wrong trousers " + l )
        self.origin = Coord3._make(map(int, l[7:].strip().split(':')))
        
        l = dumpf.readline()
        if not l.startswith("extent:"):
            raise TypeError("Wrong trousers " + l )
        x, y, z = list(map(int, l[7:].strip().split(':')))
        self.dim = Coord3(x*16, y*16, z)
        
        l = dumpf.readline()
        if not l.startswith("window:"):
            raise TypeError("Wrong trousers " + l )
        self.window = Coord3._make(map(int, l[7:].strip().split(':')))
        
        l = dumpf.readline()
        if not l.startswith("tiles:"):
            raise TypeError("Wrong trousers " + l )
        self.tiles_offset, self.tiles_size = map(int, l[6:].split(':'))
        
        l = dumpf.readline()
        if not l.startswith("flows:"):
            raise TypeError("Wrong trousers " + l )
        self.flows_offset = int(l[6:])
        
        # read and combine all of plaintext
        lines = dumpf.read(self.tiles_offset - dumpf.tell()).split("\n")
        
        dumpf.seek(self.flows_offset)
        lines += dumpf.read().split("\n")
        
        # parse plaintext
        sections = [ 'materials', 'buildings', 'building_defs', 'constructions', 'flows', 'units', 'items' ]
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
                        subklass = v
                    elif k == 'klass':
                        klass = v
                if klass == 'PLANT':
                    klass = subklass

                self.mat_ksk[id] = (name, klass, subklass)
                self.mat_ids[(name, klass)] = id

    def _assemble_blitcode(self, objcode, irdump=None):
        if irdump is None:
            class irdummy(object):
                def write(*args, **kwargs):
                    pass
            irdump = irdummy
        log = logging.getLogger('fgt.raws')

        # maxframes defines for how many frames to extend cel's final framesequence
        # (if cel don't have that much frames on its own)
        # cutoff: cut all animations after this frame
        if self.cutoff == -1: # don't cut:
            maxframes = objcode.maxframe
        else:
            maxframes = self.cutoff if objcode.maxframe > self.cutoff else objcode.maxframe

        tcount = 0
        for mat, tset in objcode.map.items():
            tcount += len(tset.keys())
        if tcount > 65536:
            raise TooManyTilesDefinedCommaManCommaYouNutsZedonk

        log.info("objcode: {1} mats, {0} defined tiles, {2} frames max".format(
            len(objcode.map.keys()), tcount, objcode.maxframe))

        self.codew = int(math.ceil(math.sqrt(tcount)))
        self.codeh = self.codew
        self.codedepth = maxframes
        
        self.dispw = self.max_mat_id
        self.disph = len(self.tileresolve)

        dispatch = CArray(None, "HH", self.dispw, self.disph, inverty = True)
        dispatch.memset(128)
        log.info("dispatch: {}".format(dispatch))
        blitcode = CArray(None, "IIII", self.codew, self.codeh, self.codedepth, inverty = True)
        blitcode.memset(BM_CODEDBAD)
        log.info("blitcode: {}".format(blitcode))
        
        tc = 1 # reserve 0,0 blitinsn as an implicit nop
        for mat_name, tileset in objcode.map.items():
            try:
                mat_id = self.mat_ids[mat_name]
            except KeyError:                
                raise CompileError("unknown mat name '{}' in tileset '{}'".format(mat_name, tileset))

            for tilename, frameseq in tileset.items():
                try:
                    tile_id = self.tileresolve[tilename]
                except KeyError:
                    raise CompileError("unknown tile name '{}' in mat '{}'".format(tilename, mat_name))
                    
                cx = int (tc % self.codew)
                cy = int (tc // self.codew)

                # write dispatch record: (mat, tile) -> blitcode
                dispatch.set((cx, cy), mat_id, tile_id)

                frame_no = 0
                for frame in frameseq:
                    bm = 0 if frame.mode == BM_NONE else ( frame.blit << 8 ) & frame.mode
                    unused = 0
                    fg = frame.fg if frame.mode in ( BM_CLASSIC, BM_FGONLY ) else 0
                    bg = frame.bg if frame.mode == BM_CLASSIC else 0
                    
                    blitcode.set((bm, unused, fg, bg), cx, cy, frame_no)
                        
                    irdump.write("dis@{:03d}:{:03d} code@{}:{} {} {} {}\n".format(mat_id, 
                                    tile_id, cx, cy, mat_name, tilename, frame))
                    frame_no += 1
                    if frame_no > self.codedepth - 1: # cutoff
                        break
                tc += 1                
                #  FIXME: add fill-out down to self.codedepth here

        self.dispatch, self.blitcode = dispatch, blitcode

    def gettile(self, posn):
        x, y, z = posn
        offs = self.data_dt.size*(self.dim.x*self.dim.y*z + y*self.dim.x + x)
        stoti, bmabui, grass, designation = self.data_dt.unpack(self._tiles_mmap[offs:offs+self.data_dt.size])
        tile_id  = stoti & 0xffff
        mat_id   = stoti >> 16
        btile_id = bmabui & 0xffff # can also hold building_type+768
        bmat_id  = bmabui >> 16 
        grass_id = grass & 0xffff
        grass_amount = ( grass >> 16 ) & 0xff

        flags = self.tileflags.get(tile_id)[0]
        tilename = self.tileresolve[tile_id]
        btilename = self.tileresolve[btile_id]

        matname, matklass, matsubklass = self.mat_ksk.get(mat_id, None)
        bmatname, bmatklass, bmatsubklass = self.mat_ksk.get(bmat_id, None)
        grassname, grassklass, grasssubklass = self.mat_ksk.get(grass_id, None)
        
        return ( (mat_id, matname),   (tile_id, tilename),
                 (bmat_id, bmatname), (btile_id, btilename),
                 (grass_id, grassname, grass_amount), 
                  designation, flags )
    
    def inside(self, x, y, z):
        return (  (x < self.dim.x) and (x >= 0 ) 
                and  ( y < self.dim.y) and (y >= 0)
                and (z < self.dim.z) and (z>= 0))

    def lint(self, zstart):
        """ verifies that (most of) map tiles in the dump are drawable """
        if zstart < 0:
            zstart = self.dim.z - 1
        else:
            assert zstart < self.dim.z
        rep = open('lint.out', 'w')
        oks = {}
        fails = {}
        count = 0
        empty = True
        try:
            for _z in range(zstart):
                z = zstart - _z - 1 # go from top to bottom
                empty = True
                for y in range(self.dim.y):
                    for x in range(self.dim.x):
                        count += 1
                        
                        fl_tm, up_tm, grass, des = self.mapdata.get(x,y,z)
                        fl_mat = fl_tm >> 16
                        fl_tile = fl_tm & 0xffff
                        up_mat = up_tm >> 16
                        up_tile = up_tm & 0xffff
                        gr_mat = grass & 0xffff
                        
                        flags = self.tileflags.get(fl_tile)[0]
                        
                        if (flags & TCF_TRUEFLOOR) and (flags & TCF_FAKEFLOOR):
                            fails[(fl_mat, fl_tile)] = "mode=floor true+fake"
                            continue
                            
                        if flags & TCF_GRASS:
                            fl_mat = gr_mat
                        
                        if flags & TCF_PLANT:
                            fl_mat = up_mat
                        
                        if (flags & TCF_VOID):
                            fl_mat = 0
                        else:
                            empty = False
                        
                        if (fl_mat, fl_tile) in oks:
                            continue

                        addr_s, addr_t = self.dispatch.get(fl_mat, fl_tile)
                        
                        if (addr_s > self.codew) or (addr_t > self.codeh):
                            fails[(fl_mat, fl_tile)] = "bogus addr (tile*mat not defined?)"
                            continue
                        
                        fibm, unused, bg, fg = self.blitcode.get(addr_s, addr_t, 0)
                        mode = fibm & 0xff
                        index = fibm >> 8
                        if mode == BM_CODEDBAD:
                            fails[(fl_mat, fl_tile)] = "mode=codedbad"
                            continue
                        elif mode not in (BM_NONE, BM_ASIS, BM_CLASSIC, BM_FGONLY):
                            fails[(fl_mat, fl_tile)] = "mode={}".format(mode)
                            continue
                        
                        if mode != BM_NONE:
                            if index >= len(self.pageman.findex.data):
                                fails[(fl_mat, fl_tile)] = "font index out of bounds: {}".format(index)
                                continue
                            cx, cy, cw, ch = self.pageman.findex.get(index)
                            if (cw == 0) or (ch == 0):
                                fails[(fl_mat, fl_tile)] = "cw,ch={},{}".format(cw, ch)
                                continue
                            if (cx > self.pageman.surface.w - ch) or (cy > self.pageman.surface.h - cw):
                                fails[(fl_mat, fl_tile)] = "cx,cy={},{}".format(cx, cy)
                                continue
                        
                        oks[(fl_mat, fl_tile)] = 23

                if empty:
                    print("{: 3d} -empty-z-level-".format(z))
                else:
                    print("{: 3d} ok={} fail={}".format(z, len(oks), len(fails)))
        except KeyboardInterrupt:
            pass
        rep.write("\nFAILs:\n")
        for eka, val in fails.items():
            rep.write("{} {} {} {}:{}\n".format(eka[0], eka[1], self.mat_ksk.get(eka[0], None), self.tileresolve[eka[1]], val))

class Designation(object):
    def __init__(self, u32):
        self.level              =  u32 &   7
        self.pile               = (u32 >>  3) & 1
        self.dig                = (u32 >>  4) & 7
        self.smooth             = (u32 >>  7) & 3
        self.hidden             = (u32 >>  9) & 1
        self.geolayer           = (u32 >> 10) & 15
        self.light              = (u32 >> 14) & 1
        self.subter             = (u32 >> 15) & 1
        self.outside            = (u32 >> 16) & 1
        self.biome              = (u32 >> 17) & 15
        self.ltype              = (u32 >> 21) & 1
        self.aquifer            = (u32 >> 22) & 1
        self.rained             = (u32 >> 23) & 1
        self.traffic            = (u32 >> 24) & 3
        self.flow_forbid        = (u32 >> 26) & 1
        self.liquid_static      = (u32 >> 27) & 1
        self.feat_local         = (u32 >> 28) & 1
        self.feat_global        = (u32 >> 29) & 1
        self.stagnant           = (u32 >> 30) & 1
        self.salt               = (u32 >> 31) & 1
        
    def __str__(self):
        rv = []
        if self.level > 0:
            rv.append([ '', 'stagnant'][self.stagnant])
            rv.append([ '', 'salt'][self.salt])
            rv.append(['water', 'magma'][self.ltype])
            rv.append('level {}'.format(self.level))
        rv.append(['dark', 'light'][self.light])
        rv.append(['inside', 'outside'][self.outside])
        rv.append(['', 'subter'][self.subter])
        rv.append(['', 'rained'][self.light])
        rv.append(['', 'aquifer'][self.aquifer])
        rv.append(['', 'hidden'][self.hidden])
        
        return ' '.join(rv)

def main():
    ap = argparse.ArgumentParser(description = 'full-graphics raws parser/compiler')
    ap_data_args(ap)
    ap.add_argument('-dump-dir', metavar='dir-name', 
            help="dump intermediate representation, dispatch, blitcode and the texture album here")
    ap.add_argument('-lint', nargs='?', metavar='zstart', type=int, const=-1,
            help="cross-check compiler output, starting at z-level zstart; results written to 'lint.out'")
    pa = ap.parse_args()
    logconfig()

    if pa.dump_dir is not None and not os.path.isdir(pa.dump_dir):
        os.mkdir(pa.dump_dir)
    
    sdl_offscreen_init()
    
    mo = MapObject(     
        dfprefix = pa.dfdir,
        fgraws = pa.rawsdir,
        cutoff = pa.cutoff,
        apidir = pa.apidir)

    mo.use_dump(pa.dfdump, pa.dump_dir)

    if pa.lint is not None:
        mo.lint(pa.lint)

if __name__ == '__main__':
    main()
