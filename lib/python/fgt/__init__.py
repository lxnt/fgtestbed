# -*- encoding: utf-8 -*-

import os.path
import sys
import logging
import argparse

def logconfig(info = None, calltrace = None):
    lcfg = {
        'version': 1,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
                'stream': sys.stdout,
            },
            'calltrace': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
                'stream': sys.stdout,
            },
        },
        'loggers': {
            'root': { 'level': 'INFO', 'handlers': ['console'] },
            'OpenGL': { 'level': 'INFO' },
            'OpenGL.calltrace': { 'level': 'CRITICAL', 'handlers': ['calltrace'], 'propagate': 0 },
            'OpenGL.extensions':        { 'level': 'WARN' },
            'fgt':                      { 'level': 'INFO' },
            'fgt.raws':                 { 'level': 'DEBUG' },
            'fgt.raws.rpn.trace':       { 'level': 'WARN' },
            'fgt.raws.TSParser':        { 'level': 'WARN' },
            'fgt.raws.ObjectHandler':   { 'level': 'WARN' },
            'fgt.raws.InitParser':      { 'level': 'WARN' },
            'fgt.raws.pageman.get':     { 'level': 'WARN' },
            'fgt.raws.InflateFrameseq': { 'level': 'DEBUG' },
            'fgt.raws.MaterialSet':     { 'level': 'WARN' },
            'fgt.raws.RawsCart.compile':{ 'level': 'DEBUG' },
            'fgt.shader':               { 'level': 'INFO' },
            'fgt.shader.locs':          { 'level': 'WARN' },
            'fgt.pan':                  { 'level': 'WARN' },
            'fgt.zoom':                 { 'level': 'WARN' },
            'fgt.reshape':              { 'level': 'WARN' },
            'fgt.glinfo':               { 'level': 'WARN' },
            'fgt.glinfo.extensions':    { 'level': 'WARN' },
        },
    }
    if calltrace:
        lcfg['loggers']['OpenGL.calltrace']['level'] = 'INFO'
        if calltrace != 'stderr':
            lcfg['handlers']['calltrace']['stream'] = open(calltrace, 'w')
        else:
            del lcfg['loggers']['OpenGL.calltrace']['propagate']

    if info:
        lcfg['loggers']['fgt.glinfo']['level'] = 'INFO'
        if info == 'exts':
            lcfg['loggers']['fgt.glinfo.extensions']['level'] = 'INFO'
    logging.config.dictConfig(lcfg)

class _fgt_config_container(object):
    def __init__(self):
        self.ap = None
        self.pa = None

    def __call__(self, **kwargs):
        self.ap = argparse.ArgumentParser(**kwargs)

    def parse_args(self):
        self.pa = self.ap.parse_args()
        logconfig(getattr(self.pa,"glinfo", False), getattr(self.pa,"calltrace", False))

    def add_argument(self, *args, **kwargs):
        return self.ap.add_argument(*args, **kwargs)

    def add_render_args(self, **kwargs):
        self.ap.add_argument('-choke', metavar='fps', type=float, default=0, help="renderer fps cap")
        self.ap.add_argument('-psize', metavar="psize", type=int, help="point size")
        self.ap.add_argument('-par', metavar="par", type=float, help="point aspect ratio")
        self.ap.add_argument('-calltrace', metavar="outfile", nargs='?', type=str, const='calltrace.out',
                help="enable GL call trace, write to given file")
        self.ap.add_argument('-glinfo', metavar="exts", nargs='?', type=str, const='noexts',
                help="log GL caps and possibly extensions")
        self.ap.add_argument('-ss', metavar='sname', help='shader set name', default='step')
        self.ap.add_argument('-shaderpath', metavar='ssdir', help='path to shader sets', default='lib/shaders')
        self.ap.add_argument('-hudfont', metavar='family[,pt]', help='font family substring[,size]', default=None)
        self.ap.set_defaults(**kwargs)

    def add_data_args(self, **kwargs):
        self.ap.add_argument('-apidir', metavar="lib/df-structures", default="lib/df-structures",
                help="df-structures directory to get xml data from")
        self.ap.add_argument('-dfdir', metavar="../df_linux", default=os.path.join("..","df_linux"),
                help="df directory to get base tileset and raws from")
        self.ap.add_argument('-std', metavar="raws/dir", default=os.path.join('raw','std'), help="core FG raws dir")
        self.ap.add_argument('dfdump', metavar="some.dump", help="dump file name")
        self.ap.add_argument('ext', metavar="raws/dir", nargs='*', default=[],
                help="extra FG raws dir to parse")
        self.ap.set_defaults(**kwargs)

    def __getattr__(self, name):
        return getattr(self.pa, name)

config = _fgt_config_container()
configure = config
