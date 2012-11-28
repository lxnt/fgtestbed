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

import os, os.path, glob, sys, re
import stat, struct, math, mmap, pprint
import logging
import collections
import lxml.etree
import yaml

import fractions
lcm = lambda a, b: abs(a * b) // fractions.gcd(a, b)

def lcm_seq(ible):
    seen = set([1])
    rv = 1
    for i in ible:
        rv = lcm(rv, i)
    return rv

from fgt.gl import *
from fgt.tokensets import *

# tileflags:
TF_GRASS = 1
TF_FAKEFLOOR = 2
TF_TRUEFLOOR = 4
TF_VOID = 8
TF_UNKNOWN = 16
TF_PLANT = 32
TF_NONMAT = 64 # driftwood, campfire, etc.

# blitmodes:
BM_NONE = 0
BM_ASIS = 1
BM_CLASSIC = 2
BM_FGONLY = 3
BM_OVERSCAN = 254 # used for grid locations outside the map
BM_CODEDBAD = 255 # filler

class ci_dict(dict):
    def __contains__(self, key):
        return super(ci_dict, self).__contains__(key.upper()) 
    
    def __setitem__(self, key, value):
        super(ci_dict, self).__setitem__(key.upper(), value)

    def __getitem__(self, key):
        return super(ci_dict, self).__getitem__(key.upper()) 
        
    def __delitem__(self, key):
        return super(ci_dict, self).__delitem__(key.upper())
    
    def get(self, key, d = None):
        return super(ci_dict, self).get(key.upper(), d)

class ci_set(set):
    def __contains__(self, key):
        return super(ci_set, self).__contains__(key.upper()) 

    def add(self, key):
        return super(ci_set, self).add(key.upper()) 
    
    def discard(self, key):
        return super(ci_set, self).discard(key.upper())
        
    def pop(self, key):
        return super(ci_set, self).pop(key.upper())            

    def remove(self, key):
        return super(ci_set, self).remove(key.upper())

class ParseError(Exception):
    pass

class CompileError(Exception):
    pass
class ExpressionError(Exception):
    """ stack underflow or more than one value at end
        of material selector expression evaluation """

class enum_t(object):
    debug = logging.getLogger('fgt.enum_t').debug
    def __init__(self, e, typedict):
        self._names = {}
        self._values = {}
        self.name = e.get('type-name')
        self.debug("__init__() name={}".format(self.name))
        attrtypes = { 'name': None, 'value': None }
        for ea in lxml.etree.XPath('enum-attr')(e):
            attrtypes[ea.get('name')] = ( typedict[ea.get('type-name', None)], ea.get('default-value') )
        
        nt = collections.namedtuple(self.name, attrtypes.keys())
        self._type = nt
        
        i = 0
        for ei in lxml.etree.XPath('enum-item')(e):
            try:
                i = int(ei.get('value'))
            except TypeError:
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
        self.last = i - 1
        typedict[self.name] = lambda x: self[x]
    
    def extend(self, fieldname, valuefactory):
        """ adds a field to each item """
        names = {}
        values = {}
        typename = self._type.__doc__.split('(')[0]
        newtype = collections.namedtuple( typename, list(self._type._fields) + [ fieldname ] )
        for number, value in self._values.items():
            value = newtype( *(list(value) + [ valuefactory(value) ]) )
            names[value.name] = value
            values[number] = value
            
        self._type = newtype
        self._names = names
        self._values = values
    
    def uppercase(self):
        """ enables uppercased name lookups 
            side-effect: removes the None key """
        names = {}
        for name, value in self._names.items():
            if name is not None:
                names[name] = names[name.upper()] = value
        self._names = names
    
    def __len__(self):
        return self.last + 1
    
    def __iter__(self):
        cur = -1
        while cur < len(self) -1:
            cur += 1
            yield self[cur]
    
    def __getitem__(self, val):
        if isinstance(val, int):
            return self._values[val]
        elif isinstance(val, str):
            return self._names[val]
        else:
            raise TypeError("can't lookup with {}".repr(val))


class DFAPI(object):
    """ currently has the following enum_t attribures:
            tiletype
            building_type
            civzone_type
            construction_type
            furnace_type
            shop_type
            siegeengine_type
            trap_type
            workshop_type
    """
    
    def __init__(self, dfapipath):
        def parse(filename):
            parser = lxml.etree.XMLParser(remove_blank_text = True)
            root = lxml.etree.parse(filename, parser).getroot()
            for e in root.iter():
                if isinstance(e, lxml.etree._Comment):
                    e.getparent().remove(e)
                else:
                    e.tail = e.text = None

            typedict = { 
                None: lambda s: s,
                'bool': lambda s: True if s == 'true' else False 
            }
            rv = []
            for e in lxml.etree.XPath('enum-type')(root):
                rv.append(enum_t(e, typedict))

            return rv
        nonmat_tiles = """Ashes1 Ashes2 Ashes3 Campfire Chasm Driftwood
                          EeriePit Fire MagmaFlow RampTop OpenSpace
                          RampTop SemiMoltenRock Void Waterfall""".split()
        # nonmats are those where the shader will replace supplied material
        # with material BUILTIN:NONEMAT.

        def flag_a_tile(tt):
            flags = 0
            if tt.name is None:
                return TF_UNKNOWN                
            if tt.name.startswith('Grass'):
                flags = flags | TF_GRASS
            if tt.shape.name in ('TREE', 'SHRUB', 'SAPLING'):
                flags = flags | TF_PLANT
            if (tt.material.name in ('DRIFTWOOD', 'CAMPFIRE', 'FIRE') or
               tt.shape.name in ('TREE', 'SHRUB', 'SAPLING', 'PEBBLES', 'BOULDER', 'STAIR_UP')):
                   flags = flags | TF_FAKEFLOOR 
            if ( tt.name.endswith(('FloorSmooth', 'Floor1', 'Floor2', 'Floor3', 'Floor4', 'Floor')) and
                tt.name not in ('ConstructedFloor', 'GlowingFloor')):
                    flags = flags | TF_TRUEFLOOR
            if (tt.shape.name in ('EMPTY', 'ENDLESS_PIT', 'RAMP_TOP') or tt.name in ('RampTop', 'Void')):
                flags = flags | TF_VOID | TF_NONMAT
            if tt.name in nonmat_tiles:
                flags = flags | TF_NONMAT
            if tt.name.startswith(('Feature', 'Lava', 'Frozen')):
                flags = flags | TF_NONMAT
            return flags

        self.tiletype = parse(os.path.join(dfapipath, 'df.tile-types.xml'))[-1]
        self.tiletype.extend('flags', flag_a_tile)
        self.tiletype.uppercase()
        
        bt_enums = parse(os.path.join(dfapipath, 'df.buildings.xml'))
        for e in bt_enums:
            setattr(self, e.name, e)

class Pageman(object):
    """ blits tiles in order of celpage submission to album.w//max(cdim.w) columns 
        TODO: move blits and mapping generation to the get() method, so that only
        referenced cels are uploaded.
    """
    def __init__(self, pages, album_w = 2048):
        self.mapping = {}
        self.pages = ci_dict()
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
        
        album_w -= album_w % w_lcm # no space gets wasted when a row is full of cels of uniform size
        
        cx = 0 # stuff in cels, filling up partially occupied rows 
        cy = 0 # with cels of lesser height.
        row_h = pages[0].cdim.h # current row height.
        index = 0
        
        album = rgba_surface(album_w, album_w//8)
        for page in pages:
            if page.id in self.pages:
                raise ValueError("duplicate page {}#{}".format(page.origin, page.name))
            self.pages[page.id] = page
            for j in range(page.pdim.h):
                for i in range(page.pdim.w):
                    src = Rect(i*page.pdim.w, j*page.pdim.h, page.cdim.w, page.cdim.h)
                    if cx >= album_w:
                        cx = 0
                        cy += row_h
                        row_h = page.cdim.h 
                        if cy + row_h > album.h: # grow it
                            a = rgba_surface(album.w, album.h*2)
                            a.fill((0,0,0,0))
                            a.blit(album, Rect(0, 0, a.w, album.h), Rect(0, 0, a.w, album.h))
                            album = a
                    dst = Rect(cx, cy, page.cdim.w, page.cdim.h)
                    album.blit(page.surface, dst, src)
                    self.mapping[(page.id, i, j)] = index
                    self.findex.set((cx, cy, page.cdim.w, page.cdim.h), index)
                    index += 1
                    cx += page.cdim.w
        # cut off unused tail
        a = rgba_surface(album.w, cy + row_h)
        a.blit(album, Rect(0, 0, a.w, album.h), Rect(0, 0, a.w, cy + row_h))
        self.surface = a
        self.count = index
        
    def dump(self, dumpdir):
        sk = sorted(self.mapping.keys())
        with open(os.path.join(dumpdir, 'album.mapping'), 'w') as f:
            f.write(str(self.surface) + "\n")
            for k in sk:
                f.write("{}:{}:{} -> {} \n".format(
                        k[0], k[1], k[2], self.mapping[k]))
        self.surface.write_bmp(os.path.join(dumpdir, 'album.bmp'))
        self.findex.dump(open(os.path.join(dumpdir, "album.index"), 'wb'))

    def get(self, origin, ref):
        logging.getLogger('fgt.raws.pageman.get').debug(repr(ref))
        pageid = ref[0].upper()
        if pageid == 'STD':
            page = self.pages[pageid]
        else:
            pageid = origin.upper() + '\00' + pageid
            try:
                page = self.pages[pageid]
            except KeyError:
                raise NameError("page '{}#{}' is not defined".format(origin, ref[0]))
        
        ref = ref[1:]
        if len(ref) == 2:
            s, t = ref
        elif isinstance(ref[0], int): # an idx
            s = ref[0] % page.pdim[0]
            t = ref[0] // page.pdim[1]
        elif isinstance(ref[0], str): # a def
            s, t = page.defs[ref[0]]
        else:
            raise KeyError(repr(ref))
        return self.mapping[(pageid, s, t)]

    def __str__(self):
        if len(self.pages) == 0:
            return "Pageman(empty)"
        return "Pageman(): {} pages {} tiles, font {}K; findex {}K; surface: {}".format(
            len(self.pages), self.count, self.surface.w*self.surface.h>>8, 
                len(self.findex.data)>>10, str(self.surface))

class BasicFrame(object):
    def __init__(self, mode, blit, fg, bg):
        self.mode = mode
        self.blit = blit
        self.fg = fg
        self.bg = bg

    def __str__(self):
        if self.mode == BM_NONE:
            return "mode=BM_NONE"
        elif self.mode == BM_ASIS:
            return "mode=BM_ASIS   blit={}".format(self.blit)
        elif self.mode == BM_CLASSIC:
            return "mode=BM_CLASSIC blit={} fg={:08x} bg={:08x}".format(self.blit, self.fg, self.bg)
        elif self.mode == BM_FGONLY:
            return "mode=BM_FGONLY blit={} fg={:08x}".format(self.blit, self.fg)
        else:
            return "mode={} WTF?!".format(self.mode)

    def __repr__(self):
        return self.__str__()

def InflateFrameseq(keyframes, material, celeffects, colortab):
    """ Converts keyframes into seqs of basicframes. """
    log = logging.getLogger('fgt.raws.InflateFrameseq')
    if keyframes is None or len(keyframes) == 0:
        raise CompileError("None or empty frame sequence for {} {}".format(tilename, material))

    if len(keyframes) == 1:
        return [ BasicFrame(*keyframes[0].emit(material, celeffects, colortab)) ]

    def interpolate_keyframes(fromframe, toframe):
        nonlocal material, celeffects, colortab
        assert fromframe != toframe
        frameseq = []
        mode0, blit0, fg0, bg0 = fromframe.emit(material, celeffects, colortab)
        
        if not fromframe.glow:
            for no in range(fromframe.no, toframe.no):
                frameseq.append(BasicFrame(mode0, blit0, fg0, bg0))
            return frameseq
        
        mode1, blit1, fg1, bg1 = toframe.emit(material, celeffects, colortab)

        def split(rgba):
            return (rgba>>24)&0xff,(rgba>>16)&0xff,(rgba>>8)&0xff,rgba&0xff

        def join(r,g,b,a):
            return  (int(r)<<24)|(int(g)<<16)|(int(b)<<8)|int(a)
        
        def delta(a, b, amt): # delta is okay to be float
            r0,g0,b0,a0 = split(a)
            r1,g1,b1,a1 = split(b)
            return (r1-r0)/amt, (g1-g0)/amt, (b1-b0)/amt, (a1-a0)/amt

        def advance(base, delta, amt):
            r,g,b,a = base
            dr,dg,db,da = delta
            return join(r+dr*amt, g+dg*amt, b+db*amt, a+da*amt)
        
        base_fg, base_bg = split(fg0), split(fg1)
        dfg = delta(fg0, fg1, toframe.no - fromframe.no)
        dbg = delta(bg0, bg1, toframe.no - fromframe.no)
        
        for no in range(fromframe.no, toframe.no):
            frameseq.append(BasicFrame(mode0, blit0, advance(base_fg0, dfg, no), advance(base_bg0, dbg, no)))

    log.debug("len(keyframes) = {}".format(len(keyframes)))
    
    rv = []
    for frameno in range(len(keyframes)-1):
        rv += interpolate_keyframes(keyframes[frameno], keyframes[frameno+1])
    
    return rv

class RawsParser0(object):
    @property
    def log(self):
        return logging.getLogger('fgt.raws.' + self.__class__.__name__)
    
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
        lcontd = ''
        for l in map(lambda x: x.strip(), data.split('\n')):
            lnum += 1
            if l.endswith('\\'):
                lcontd += l[:-1]
                continue
            elif lcontd:
                l = lcontd + l
                lcontd = ''
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
        o.fin()
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
    colorseq = "BLACK BLUE GREEN CYAN RED MAGENTA BROWN LGRAY DGRAY LBLUE LGREEN LCYAN LRED LMAGENTA YELLOW WHITE".split()
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
        cshift = { 'R': 24, 'G': 16, 'B': 8, 'A': 0 }        
        color, channel = name.split('_')
        val = self.colortab[self.colorseq.index(color)] | int(tail[0]) << cshift[channel]
        self.colortab[self.colorseq.index(color)] = val
        
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

class RawsObject0(object):
    def __init__(self, name, klass):
        self.name = name
        self.klass = klass
        self._basic_mat = None        
        self.tokens = ci_set()
        self.celdefs = ci_dict()

    def __hash__(self):
        return hash(self.name + self.klass)

    def pad_celdefs(*args, **kwargs):
        pass

    def add(self, name):
        self.tokens.add(name)

    @staticmethod
    def parse_tile(t):
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
    
    def getcel(self, mdt_name):
        return self.celdefs.get(str(mdt_name), None)

class Plant(RawsObject0):
    """ a plant (and not a plant material) 
        has multiple celdefs.
        celrefs are for std 16x16 font.
    """
    TREE_CELDEFS = { # tiletype -> (blit,blend)
        'TREE':         (('STD', 5,  0), (2, 0, 1)),
        'SAPLING':      (('STD', 7, 14), (2, 0, 1)),
        'DEAD_TREE':    (('STD', 6, 12), (6, 0, 0)),
        'DEAD_SAPLING': (('STD', 7, 14), (6, 0, 0)), }
    SHRUB_CELDEFS = {
        'DEAD_SHRUB':   (('STD', 2,  2), (6, 0, 0)),
        'SHRUB':        (('STD', 2,  2), (2, 0, 1)), }
    GRASS_CELDEFS = { # mdt_idx -> (blit,blend)); 
    # in fact mdt_idx can be anything that doesn't contain ':'
    # called 'index' since it's used in grass only whose raws aren't that advanced
        '0':            (('STD', 39), (2, 0, 1)), # GRASSwhateverFLOOR0
        '1':            (('STD', 44), (2, 0, 0)),
        '2':            (('STD', 96), (6, 0, 1)),
        '3':            (('STD', 39), (6, 0, 0)), }

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
                self._addcref(str(i), ('STD', self.parse_tile(t)))
        elif name == 'GRASS_COLORS':
            colors = list(map(int, tail))
            fgs = colors[0::3]
            bgs = colors[1::3]
            brs = colors[2::3]
            i = 0
            for fg in fgs:
                i += 1
                self._addcolor(str(i), (fg, bgs.pop(0), brs.pop(0)))
        elif name.endswith('_TILE'):
            tile_idx = self.parse_tile(tail[0])
            self._addcref(name[:-5], ('STD', tile_idx))
        elif name.endswith('_COLOR'):
            self._addcolor(name[:-6], list(map(int, tail)))
        self.add(name)

class Inorganic(RawsObject0):
    """ an inorganic material 
        has a single cref named 'WALL' for StoneWall/MineralWall tiles. """
    def __init__(self, name):
        super(Inorganic, self).__init__(name, 'INORGANIC')
        
    def token(self, name, tail):
        if name == 'DISPLAY_COLOR':
            self._dc = list(map(int, tail))
            self._addcolor('WALL', self._dc)
        elif name == 'TILE':
            tile_idx = self.parse_tile(tail[0])
            self._addcref('WALL', ('STD', tile_idx))
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
        self.tokens = ci_set()
        
        self.tokens.update(template.parsed)
        self._dc = template.display_color
        
    def __hash__(self):
        return hash(self.klass + self.parent.name)
    
    def token(self, name, tail):
        if name == 'DISPLAY_COLOR':
            self._dc = list(map(int, tail))
        self.tokens.add(name)

    def getcel(self, mdt_name):
        self.parent.pad_celdefs()
        return self.parent.getcel(mdt_name)
    
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

def GetBuiltinMaterials():
    class Builtin(object):
        klass = 'BUILTIN'
        display_color = (0, 0, 1)
        def __contains__(self, wha):
            return False
        def __str__(self):
            return "{}({})".format(self.klass, self.name)            
    class Nonemat(Builtin):
        name = 'NONEMAT'
    class Soap(Builtin):
        name = 'SOAP'
    class Amber(Builtin):
        name = 'AMBER'
    class Coral(Builtin):
        name = 'CORAL'
    class GreenGlass(Builtin):
        name = 'GLASS_GREEN'
    class ClearGlass(Builtin):
        name = 'GLASS_CLEAR'
    class CrystalGlass(Builtin):
        name = 'GLASS_CRYSTAL'
    class Water(Builtin):
        name = 'WATER'
    class Coke(Builtin):
        name = 'COKE'
    class Charcoal(Builtin):
        name = 'CHARCOAL'
    class Potash(Builtin):
        name = 'POTASH'
    class Ash(Builtin):
        name = 'ASH'
    class Pearlash(Builtin):
        name = 'PEARLASH'
    class Lye(Builtin):
        name = 'LYE'
    class Mud(Builtin):
        name = 'MUD'
    class Vomit(Builtin):
        name = 'VOMIT'
    class Salt(Builtin):
        name = 'SALT'
    class FilthB(Builtin):
        name = 'FILTH_B'
    class FilthY(Builtin):
        name = 'FILTH_Y'
    class Unknown(Builtin):
        name = 'UNKNOWN_SUBSTANCE'
    class Grime(Builtin):
        name = 'GRIME'
    
    return set([ Nonemat(), Soap(), Amber(), Coral(), GreenGlass(), ClearGlass(),
              CrystalGlass(), Water(), Coke(), Charcoal(), Potash(), Ash(), 
              Pearlash(), Lye(), Mud(), Vomit(), Salt(), FilthB(), FilthY(), 
              Unknown(), Grime() ])
    
class TSParser(RawsParser0):
    def __init__(self, templates):
        self.all = set()
        self.mat = None
        self.plant = None # mat.parent
        self.otype = None
        self.templates = templates
    
    def parse_inorganic(self, name, tail):
        if name == 'INORGANIC':
            self.all.add(self.mat)
            self.mat = Inorganic(tail[0])
        elif name == 'USE_MATERIAL_TEMPLATE':
            self.mat.update(self.templates[tail[0]])
        elif name in INORGANIC_TOKENS:
            self.mat.token(name, tail)
        else:
            raise ParseError("Unrecognized inorganic material definition token:'{}'".format(name))

    def parse_plant(self, name, tail):
        if name == 'PLANT':
            self.all.add(self.mat) # add previous derived
            self.mat = None
            self.plant = Plant(tail[0])
        elif name == 'USE_MATERIAL_TEMPLATE':
            if len(tail) != 2:
                raise ParseError('Non-2-parameter USE_MATERIAL_TEMPLATE in PLANT: WTF?')
            self.all.add(self.mat) # add previous derived                
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
    
    @property 
    def materials(self):
        self.all.discard(None)
        return self.all


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

    def fin(self):
        pass

class CelPage(Token):
    tokens = ('CEL_PAGE', 'TILE_PAGE')
    parses = ('FILE', 'TILE_DIM', 'PAGE_DIM')
    def __init__(self, name, tail, origin = None, data = None):
        self.defs = {}
        self._surf = None

        if isinstance(tail, dict) and isinstance(origin, str): # from YAML
            self.id = origin.upper() + '\x00' + name.upper()
            self.name = name
            self.file = data[0]
            self.data = data[1]
            self.cdim = Size2(*tail['cel-dim'])
            self.pdim = Size2(*tail['page-dim'])
            for ndef, adef in tail.get('defs', {}).items():
                if isinstance(adef, int):
                    self.defs[ndef] = [ adef% self.pdim.w, adef // self.pdim.w ]
                elif isinstance(adef, (list, tuple)) and len(adef) == 2:
                    self.defs[ndef] = adef
                else:
                    raise ValueError("WTF is this def: {}: {}?".format(ndef, adef))
            self._surf = None
        else: # from df raws
            self.name = tail[0]
            self.file = None
            self.data = None
            self.cdim = None
            self.pdim = None
            self.id = None

    def __str__(self):
        return '{}:{} pdim={} cdim={} surf={}'.format(self.name, self.file, 
            self.pdim, self.cdim, self._surf)
    __repr__ = __str__
            
    def parse(self, name, tail):
        if name == 'FILE':
            self.file = tail[0]
        elif name == 'TILE_DIM':
            self.cdim = Size2(int(tail[0]), int(tail[1]))
        elif name == 'PAGE_DIM':
            self.pdim = Size2(int(tail[0]), int(tail[1]))

    def _check_dim(self, surf):
        if surf.w != self.cdim.w*self.pdim.w or surf.h != self.cdim.h*self.pdim.h:
            raise ValueError("size mismatch on {}: surf={}x{} pdim={} cdim={}".format(
                self.file, surf.w, surf.h, self.pdim, self.cdim))

    @property
    def surface(self):
        if not self._surf:
            self._surf = rgba_surface(filename=self.file, filedata=self.data)
            self._check_dim(self._surf)
        return self._surf

class StdCelPage(CelPage):
    name = 'STD'
    id = 'STD'
    def __init__(self, filename, celdefs):
        self.pdim = Size2(16, 16)
        self.file = filename
        self._surf = rgba_surface(filename=filename)
        self.cdim = Size2(self._surf.w//16, self._surf.h//16)
        self._check_dim(self._surf)
        self.defs = celdefs

class CelEffect(object):
    def __init__(self, name, data, origin):
        self.name = name
        self.data = data
        self.origin = origin

    def __call__(self, color):
        assert isinstance(color, (tuple, list)) and len(color) == 3
        rv = []
        for k in self.data:
            if isinstance(k, str):
                k = k.upper()
                if k == 'FG':
                    rv.append(color[0])
                elif k == 'BG':
                    rv.append(color[1])
                elif k == 'BR':
                    rv.append(color[2])
                else:
                    raise ValueError('bogus effect {}'.format(repr(self.data)))
            else:
                rv.append(int(k))
        return rv
        
    def __str__(self):
        return "CelEffect({}#{}: {})".format(self.origin, self.name, self.data)
    def __repr__(self):
        return self.__str__()

def parse_rgba(f):
    a = 0xff
    if len(f) == 4:
        r = int(f[0],16) << 4
        g = int(f[1],16) << 4
        b = int(f[2],16) << 4
        a = int(f[3],16) << 4
    elif len(f) == 8:
        r, g, b, a = int(f[:2], 16), int(f[2:4], 16), int(f[4:6], 16), int(f[6:8], 16)
    elif len(f) == 3:
        r = int(f[0],16) << 4
        g = int(f[1],16) << 4
        b = int(f[2],16) << 4
    elif len(f) == 6:
        r, g, b = int(f[:2], 16), int(f[2:4], 16), int(f[4:6], 16)
    else:
        raise ValueError(f)
    return (r<<24) | (g<<16) | (b<<8) | a

class KeyFrame(object):
    def __init__(self, data):
        self.no = data.get('frame', 0)
        self.blit = data.get('blit', None)
        self.effect = data.get('effect', None)
        self.blend = data.get('blend', 'MAT')
        self.glow = 'glow' in data
        self.final = data.keys() == ['frame']

    def clone(self, first):
        self.blit = first.blit
        self.effect = first.effect
        self.blend = first.blend
        self.glow = first.glow

    def emit(self, material, celeffects, colortab):
        blit = self.blit
        blend = self.blend

        if isinstance(blit, str) and blit.upper() == 'VOID':
            return BM_NONE, ['std', 0, 0], 0, 0
        elif isinstance(blit[0], str) and blit[0].upper() == 'MAT':
            blit, blend = material.getcel(blit[1])

        if isinstance(self.effect, str):
            effect = celeffects.get(self.effect, lambda x:x)
        else:
            effect = lambda x: x

        if isinstance(blend, (list, tuple)):
            if len(blend) == 3: # classic/ansi color
                blend = effect(blend)
                fg, bg = colortab[blend]
                mode = BM_CLASSIC
            elif len(blend) == 2: # fg/bg pair
                fg, bg = parse_rgba(blend[0]), parse_rgba(blend[1])
                mode = BM_CLASSIC
            else:
                raise ValueError("WTF is this blend: {}".format(repr(blend)))
        elif isinstance(blend, str):
            if blend.upper() == 'ASIS':
                fg = bg = 0
                mode = BM_ASIS
            elif blend.upper() == 'MAT':
                blend = material.display_color
                blend = effect(blend)
                fg, bg = colortab[blend]
                mode = BM_CLASSIC
            elif blend.upper() == 'MAT_FG':
                blend = material.display_color
                blend = effect(blend)
                fg, bg = colortab[blend]
                mode = BM_FGONLY
            else: # should be rgb stuff
                fg, bg = parse_rgba(blend), 0
                mode = BM_FGONLY
        elif isinstance(blend, int):
            fg, bg = blend, 0
            mode = BM_FGONLY
        else:
            raise TypeError("blend: {}".format(repr(blend)))

        return mode, blit, fg, bg

    def __str__(self):
        return "no={} blit={} blend={}".format(self.no, self.blit, self.blend)
    
    __repr__ = __str__

class Cel(object):
    def __init__(self, data):
        self.frames = []
        for fd in data:
            self.frames.append(KeyFrame(fd))
        if self.frames[-1].final:
            self.frames[-1].clone(self.frames[0])

    def __str__(self):
        try:
            f = self.frames[0]
        except IndexError:
            f = None
        return "CEL({} frames), first=({})".format( len(self.frames), f)

class Tile(object):
    def __init__(self, name, data):
        self.name = name
        self.cel = None
        if isinstance(data, dict):
            # implied cel, single keyframe
            self.cel = Cel([data])
        elif isinstance(data, list):
            assert isinstance(data[0], dict)
            if 'cel' in data[0]: # multiple cel definition
                for celdata in data:
                    self.cel = Cel(celdata)
                    break # multicel not implemented yet
            else: # implied cel, a list of keyframes
                self.cel = Cel(data)
        else:
            self.cel = None

    def __str__(self):
        return "TILE({}, {})".format(self.name, str(self.cel))

    def __repr__(self):
        return self.__str__()        
        
class TileSet(object):
    def __init__(self, name, data, origin):
        self.name = name
        self.origin = origin
        self.tiles = set()
        for name, td in data.items():
            self.tiles.add(Tile(name, td))

    def __str__(self):
        return "TileSet({}#{}: \n    {})".format(self.origin, self.name, '\n    '.join(map(str, self.tiles)))

    def __repr__(self):
        return self.__str__()

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
            'not':              (1, lambda a   :   not a),
            'and':              (2, lambda a, b: a and b),
            'or':               (2, lambda a, b: a  or b),
            'eq':               (2, lambda a, b: a  == b),
            'in':               (2, lambda a, b: a  in b),
            'instack':          (None, None),
            'mat':              (0, lambda: self.mat),
            'mat.klass':        (0, lambda: self.mat.klass ),
            'mat.name':         (0, lambda: self.mat.name ),
            'mat.parent':       (0, lambda: self.mat.parent ), 
            'mat.parent.klass': (0, lambda: self.mat.parent.klass ), }

        for alias, name in self.aliases.items():
            self.ops[alias] = self.ops[name]

    def __str__(self):
        if self.expr is None:
            return 'False'
        return ','.join(self.expr).lower()

    def __bool__(self):  # empty expressions are false
        return self.expr is not None

    def __call__(self, mat):
        try:
            return self._eval(mat)
        except:
            raise ExpressionError

    def _eval(self, mat):
        log = logging.getLogger('fgt.raws.rpn.trace')
        log.debug("expr: {}".format(self))
        
        stack = []

        def push(a):
            if isinstance(a, str):
                a = a.upper()
            stack.append(a)
            log.debug('pushed {}'.format(a))
            
        def pop():
            try:
                a = stack.pop()
                log.debug('popped {}'.format(a))
                return a
            except IndexError:
                raise ExpressionError("{}: stack underflow".format(self))

        self.mat = mat
        for op in self.expr:
            log.debug("op={}".format(op))
            try:
                arity, foo = self.ops[op.lower()]
            except KeyError:
                push(op) # a literal
                continue
            if arity == 0:
                try:
                    push(foo())
                except AttributeError:
                    if op in ('mat.parent', 'mat.parent.klass', 'mp', 'mpk'):
                        return False  # mat has no parent = no match
                    raise
            elif arity == 1:
                a = pop()
                push(foo(a))
            elif arity == 2:
                b = pop()
                a = pop()
                push(foo(a, b))
            elif arity is None:
                key = pop()
                stack = [ key in stack ]

        self.mat = None
        if len(stack) != 1:
            raise ExpressionError("{}; stack={}".format(self, "\n".join(stack)))
        rv = pop()
        log.debug("result={}".format(rv))
        return rv

class MaterialSet(object):
    log = logging.getLogger('fgt.raws.MaterialSet')
    def __init__(self, name, data, origin):
        self.name = name
        self.tiles = set()
        self.tile_names = set()
        self.tileset_names = set(data.get('tilesets', []))
        self.materials = set()
        self.buildings = data.get('buildings', False)
        self.origin = origin
        
        try:
            self.expr = RpnExpr(data['expr'])
        except KeyError:
            self.log.error("no rpnexpression in ms from {}".format(origin))
            raise ParseError

        for t, td in data.get('tiles', {}).items():
            self.tiles.add(Tile(t, td))
            self.tile_names.add(t)
            
    def resolve_tilesets(self, tilesets):
        for name in self.tileset_names:
            self.tiles.update(tilesets[name].tiles)

    def match(self, mat):
        if not self.expr:
            return False
        try:
            result = self.expr(mat)
        except AttributeError: # attempt at mat.parent on inorganic mat
            self.log.exception(self.origin)
            return False
        if not isinstance(result, bool):
            raise TypeError("expression {} returned {} '{}'; bool expected.".format(self.expr, type(rv), repr(rv)))
        if result: self.materials.add(mat)
        self.log.debug("match: {}:{} {}; {}".format(self.origin, self.name, mat, result))
        return result

    def __str__(self):
        rv =  "MaterialSet({}#{} selector={}, tilesets={} tiles={})".format(
            self.origin,
            self.name,
            self.expr, 
            ', '.join([str(x) for x in self.tileset_names]),
            ', '.join([str(x) for x in self.tile_names]), # explicit ones only
            )
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



class CodeUnit(object):
    """ a bridge between assembler and the origin """
    def __init__(self, mat, tile, frames, origin, matset):
        self.mat = mat
        self.tile = tile
        self.frames = frames
        self.origin = origin # which rawcart this is from
        self.matset = matset # which matset this is from
    
    def emit(self, pageman, matmap, tilenum):
        """ expects:
             - matmap to map (mat.name, mat.klass) to a dump-specific ID, 
             - tilemap to map tile name to corresponding enum-item value,
             - pageman to map (pagename, ref) to an index into the font 
             
            returns: ( mat_id, tile_id, [(mode, blit, fg, bg), ....  ] )
            ready to be encoded as a blitcode column.
        """
        frames = []
        for bf in self.frames:
            frames.append(( bf.mode, pageman.get(self.origin, bf.blit), bf.fg, bf.bg ))
        return matmap[(self.mat.name, self.mat.klass)], tilenum[self.tile.name].value, frames, self
    
    def __str__(self):
        return "{} {} {} {}".format(self.mat.name, self.tile.name, self.origin, self.frames[0])
    __repr__ = __str__
    
class RawsCart(object):
    def __init__(self, path):
        self.origin = path
        self.tilesets = ci_dict()
        self.celeffects = ci_dict()
        self.celpagedefs = ci_dict()
        self.materialsets = []
        self.celpages = []
        self.pngs = ci_dict()

    def add_yaml(self, filename, data):
        log = logging.getLogger("fgt.raws.RawsCart.add_yaml")
        log.info("[{}] {}".format(self.origin, filename))
        mset_n = 0
        origin = os.path.join(self.origin, filename)
        for fd in yaml.safe_load_all(data): # accepts bytes, str and anything with .read()
            for k, v in fd.items():
                if k == 'celpages':
                    for name, i in v.items():
                        if name.upper() == 'STD':
                            raise ValueError("{}: celpage name '{}' is reserved.".format(origin, name))
                        if name in self.celpagedefs:
                            raise ValueError("{}: celpage '{}' already there.".format(origin, name))
                        filename = i['file']
                        if os.path.split(filename)[0]: # detect path separators
                            raise ValueError("{}: path separator in filename '{}'.".format(origin, filename))
                        self.celpagedefs[name] = (name, i, filename)
                elif k == 'tilesets':
                    for name, i in v.items():
                        if name in self.tilesets:
                            raise ValueError("{}: tileset '{}' already there".format(origin, name))
                        self.tilesets[name] = TileSet(name, i, origin)
                elif k == 'materialsets':
                    for i in v:
                        name = i.get('name', "#{:d}".format(mset_n))
                        self.materialsets.append(MaterialSet(name, i, origin))
                        mset_n += 1
                elif k == 'effects':
                    for name, i in v.items():
                        if name in self.celeffects:
                            raise ValueError("{}: celeffect '{}' already there".format(origin, name))
                        self.celeffects[name] = CelEffect(name, i, origin)
                elif k == 'buildings':
                    continue # not ready for'em yet
                elif k == 'std-celpage':
                    # handy celdefs for the std page.
                    assert self.origin == os.path.join('raw','std')
                    assert filename == 'stdpage.yaml'
                    assert 'defs' in v
                    assert len(v) == 1
                    self.stddefs = v['defs']

    def add_png(self, name, filename = None, data = None):
        log = logging.getLogger("fgt.raws.RawsCart.add_png")
        log.info("[{}] {}".format(self.origin, name, filename))
        self.pngs[name] = (filename, data)
        
    def compile(self, materials, colortab):
        log = logging.getLogger("fgt.raws.RawsCart.compile")
        # instantiate celpages
        for name, data, filename in self.celpagedefs.values():
            self.celpages.append(CelPage(name, data, self.origin, self.pngs[filename]))
            log.info("[{}] celpage {} added; {}".format(self.origin, name, filename))

        # populate materialsets with tiles from tilesets
        # and matching materials.
        for ms in self.materialsets:
            ms.resolve_tilesets(self.tilesets)
            for mat in materials:
                ms.match(mat)

        # turn materialsets into (tile, mat) -> frameseq pairs
        # where frameseq blits are unresolved wrt Pageman.
        seen_tiles = ci_set()
        rv = []
        for ms in self.materialsets:
            for material in ms.materials:
                for tile in ms.tiles:
                    if tile.cel is None: # skip undefined stuff
                        log.warn("[{}] matset {}, mat {}, tile {}: no cels defined.".format(
                            self.origin, ms.name, material.name, tile.name))
                        continue
                    keyframes = tile.cel.frames
                    basicframes = InflateFrameseq(keyframes, material, self.celeffects, colortab)
                    rv.append(CodeUnit(material, tile, basicframes, self.origin, ms))
        self.codeunits = rv

    def __str__(self):
        return "RawsCart(path={})".format(self.origin)
    __repr__ = __str__
    
    def dump(self, flike):
        tail = "-"*40 + "\n\n"
        flike.write("Origin: {}\n\n".format(self.origin))
        flike.write("Tilesets:\n" + tail)
        flike.write(pprint.pformat(self.tilesets) + "\n\n")
        flike.write("Materialsets:\n" + tail)
        for ms in self.materialsets:
            flike.write(pprint.pformat(ms) + "\n")
            if ms.tiles:
                flike.write(pprint.pformat(ms.tiles) + "\n")
        flike.write("Celpagedefs:\n" + tail)
        flike.write(pprint.pformat(self.celpagedefs) + "\n\n")
        flike.write("Celpages:\n" + tail)
        flike.write(pprint.pformat(self.celpages) + "\n\n")
        flike.write("Celeffects:\n" + tail)
        flike.write(pprint.pformat(self.celeffects) + "\n\n")
        flike.write("Pngs:\n" + tail)
        flike.write(pprint.pformat(self.pngs) + "\n\n")

class FullGraphics(object):
    def parse(self, fgraws):
        def rc_dir(origin):
            assert os.path.isdir(origin)
            origin = origin.strip(os.path.sep)
            rc = RawsCart(origin)
            numit = 0
            limit = 1024
            paths = [origin]
            nextpaths = [32]
            while len(nextpaths) > 0 and numit < limit:
                nextpaths = []
                for path in paths:
                    numit += 1
                    if os.path.isdir(path):
                        nextpaths += glob.glob(os.path.join(path, '*'))
                    elif path.lower().endswith('.yaml'):
                        rc.add_yaml(path[len(origin)+1:], open(path, encoding='utf-8') )
                    elif path.lower().endswith('.png'):
                        rc.add_png(path[len(origin)+1:], filename=path)
                paths = nextpaths

                if numit == limit:
                    raise RuntimeError("{} paths scanned: something's wrong".format(numit))
            return [ rc ]

        import zipfile
        def rc_zip(origin):
            carts = {}
            zf = zipfile.ZipFile(origin)

            for zi in zf.infolist():
                dirname, filename = os.path.split(zi.filename)
                if not filename: # skip directory entries.
                    continue
                this_origin = os.path.join(origin, dirname)
                try:
                    rc = carts[this_origin]
                except KeyError:
                    rc = carts[this_origin] = RawsCart(this_origin)
                if filename.endswith('.yaml'):
                    rc.add_yaml(filename, zf.read(zi.filename))
                elif filename.endswith('.png'):
                    rc.add_png(filename, data = zf.read(zi.filename))
            return carts.values()

        self.rc_list  = []
        for path in fgraws:
            if os.path.isdir(path):
                self.rc_list.extend(rc_dir(path))
            elif zipfile.is_zipfile(path):
                self.rc_list.extend(rc_zip(path))
            else:
                raise ParseError("what is this '{}'?".format(path))

    def compile(self, materials, colortab):
        celpages = []
        codeunits = []
        stddefs = {}
        for rc in self.rc_list:
            rc.compile(materials, colortab)
            celpages.extend(rc.celpages)
            codeunits.extend(rc.codeunits)
            if hasattr(rc, 'stddefs'):
                stddefs = rc.stddefs
            
        return celpages, codeunits, stddefs

class MaterialTemplate(Token):
    tokens = ('MATERIAL_TEMPLATE',)
    parses = MATERIAL_TEMPLATE_TOKENS

    def __init__(self, name, tail):
        self.name = tail[0]
        self.display_color = None
        self.tile = None
        self.parsed = ci_set()
        
    def parse(self, name, tail):
        if name == 'DISPLAY_COLOR':
            self.display_color = list(map(int, tail))
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
    def __init__(self, dfprefix,  fgraws=[], apidir='', dump_dir=None):
        self.dispatch_dt = struct.Struct("HH") # s t GL_RG16UI - 32 bits, all used.
        self.blitcode_dt = struct.Struct("IIII") # cst mode fg bg GL_RGBA32UI - 128 bits. 16 bits unused.
        self.data_dt = struct.Struct("IIII") # stoti bmabui grass designation GL_RGBA32UI - 128 bits. 16 bits unused.
        self._mmap_fd = None
        
        self.api = DFAPI(apidir)
        self.fg = FullGraphics()
        
        self._parse_raws(dfprefix, fgraws, dump_dir)

    def use_dump(self, dumpfname, dump_dir=None):
        if dump_dir:
            self.pageman.dump(dump_dir)
            irdump = open(os.path.join(dump_dir, 'intrep.dump'), 'w')
        else:
            irdump = None

        self._parse_dump(dumpfname)
        self._assemble_blitcode(irdump)
        if dump_dir:
            self.dispatch.dump(open(os.path.join(dump_dir, 'dispatch.dump'), 'wb'))
            self.blitcode.dump(open(os.path.join(dump_dir, 'blitcode.dump'), 'wb'))

        self._mmap_dump(dumpfname)
        
    def _parse_raws(self, dfprefix, fgraws, dump_dir):
        log = logging.getLogger('fgt.raws.MapObject._parse_raws')
        stdraws = os.path.join(dfprefix, 'raw')
        
        self.fg.parse(fgraws)
        
        fontpath, colortab = InitParser(dfprefix).get()
        log.info('init.txt done.')
        
        boo = ObjectHandler(MaterialTemplates)
        boo.eat(stdraws)
        log.info("df material templates done.")
        
        mtset = boo.get(MaterialTemplates)
        
        stdparser = TSParser(mtset.templates)
        stdparser.eat(stdraws)
        stdparser.materials.update(GetBuiltinMaterials())
        log.info("df materials done.")
        
        celpages, self.codeunits, stddefs = self.fg.compile(stdparser.materials, colortab)
        log.info("compile done, {:d} code units.".format(len(self.codeunits)))
        
        if dump_dir:
            i = 0
            for rcs in self.fg.rc_list:
                f =  open(os.path.join(dump_dir, "rc{:d}.text".format(i)), 
                            mode="wt", encoding="utf-8")
                rcs.dump(f)
                i += 1
        
        celpages.append(StdCelPage(fontpath, stddefs))
        self.pageman = Pageman(celpages)
        log.info(str(self.pageman))
    
    def _mmap_dump(self, dumpfname):
        log = logging.getLogger('fgt.MapObject._mmap_dump')
        
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

    def _assemble_blitcode(self, irdump=None):
        if irdump is None:
            class irdummy(object):
                def write(*args, **kwargs):
                    pass
            irdump = irdummy
        log = logging.getLogger('fgt.raws.MapObject._assemble_blitcode')

        # The shader uses effective_frame_no = frame_no % cel_frame_count.
        # Here frame_no is an uniform running from 0 to lcm(cel_frame_count:all)
        # with anim_fps. cel_frame_count per-cel is stored per-cel in the dispatch
        # or in a separate datasource (when animation gets reenabled in the future).

        # emit all shit to get lcm(cel_frame_count:all) while at it.
        columns = []
        self.codedepth = 1
        self.maxframes = 1
        for cu in self.codeunits:
            c = cu.emit(self.pageman, self.mat_ids, self.api.tiletype)
            self.maxframes = lcm(self.maxframes, len(c[2]))
            self.codedepth = max(self.codedepth, len(c[2]))
            columns.append(c)
        log.info("{} code units emitted, maxframes={} codedepth={}".format(
                len(self.codeunits), self.maxframes, self.codedepth))

        self.tileflags = CArray(None, "I", len(self.api.tiletype))
        for ei in self.api.tiletype:
            self.tileflags.set([ ei.flags ], ei.value)
        log.info("tileflags: {}".format(self.tileflags))

        self.codew = int(math.ceil(math.sqrt(len(self.codeunits))))
        self.codeh = self.codew        
        self.dispw = self.max_mat_id + 1
        self.disph = len(self.api.tiletype)

        dispatch = CArray(None, "HH", self.dispw, self.disph)
        dispatch.bzero() # all your base are point to BM_CODEDBAD insn

        log.info("dispatch: {}".format(dispatch))
        
        blitcode = CArray(None, "IIII", self.codew, self.codeh, self.codedepth)
        blitcode.memset(BM_CODEDBAD)
        log.info("blitcode: {}".format(blitcode))
        
        tc = 1 # 0,0 blitinsn is a trap.
        
        for c in columns:
            mat_id, tile_id, frameseq, cu = c
            
            cx = int (tc % self.codew)
            cy = int (tc // self.codew)

            # write dispatch record: (mat, tile) -> blitcode
            # record frameseq length in the cx
            assert cx<256 and len(frameseq)<256
            fcx = cx | (len(frameseq) << 8)
            dispatch.set((fcx, cy), mat_id, tile_id)

            frame_no = 0
            for mode, blit, fg, bg in frameseq:
                bm = ( blit << 8 ) | mode
                blitcode.set((bm, 0, fg, bg), cx, cy, frame_no)
                irdump.write("{:03d}:{:03d} {:03d}:{:03d}:{:03d} fcx={:04x} bm={:08x} {} {} {} {}\n".format(
                                mat_id, tile_id, cx, cy, frame_no, fcx, bm, 
                                cu.origin, cu.mat.name, cu.tile.name, cu.frames[frame_no]))
                frame_no += 1

            tc += 1                

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
        tilename = self.api.tiletype[tile_id].name
        btilename = self.api.tiletype[btile_id].name

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
                        
                        if (flags & TF_TRUEFLOOR) and (flags & TF_FAKEFLOOR):
                            fails[(fl_mat, fl_tile)] = "mode=floor true+fake"
                            continue
                            
                        if flags & TF_GRASS:
                            fl_mat = gr_mat
                        
                        if flags & TF_PLANT:
                            fl_mat = up_mat

                        if (flags & (TF_VOID | TF_NONMAT)):
                            fl_mat = 0

                        if not (flags & TF_VOID):
                            empty = False
                        
                        if (fl_mat, fl_tile) in oks:
                            continue

                        fcx, fcy = self.dispatch.get(fl_mat, fl_tile)
                        addr_s = fcx & 0xFF
                        addr_t = fcy
                        frameseq_len = fcx >> 8
                        
                        if (addr_s > self.codew) or (addr_t > self.codeh):
                            fails[(fl_mat, fl_tile)] = "bogus addr {}x{} (tile*mat not defined?)".format(addr_s, addr_t)
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
            rep.write("{} {} {} {}:{}\n".format(eka[0], eka[1], self.mat_ksk.get(eka[0], None), self.api.tiletype[eka[1]].name, val))

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

