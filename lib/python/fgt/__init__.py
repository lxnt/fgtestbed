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

import os
import os.path
import sys
import logging
import logging.config
import argparse
import yaml

import pygame2
_pgld = os.environ.get('PGLIBDIR', False)
if _pgld:
    pygame2.set_dll_path(_pgld)

def curly_formatter(format):
    return logging.Formatter(fmt=format, style='{')

def logconfig(glinfo = None, gltrace = None, extraconf = 'logs.conf'):
    lcfg = {
        'version': 1,
        'formatters': {
            'console': {
                '()': 'fgt.curly_formatter',
                'format': '{name:10s}: {message}',
            },
            'alert': {
                '()': 'fgt.curly_formatter',
                'format': '-- {levelname:10s} {message}',
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'stream': sys.stdout,
                'formatter': 'console'
            },
            'alert': {
                'class': 'logging.StreamHandler',
                'level': 'WARN',
                'stream': sys.stderr,
                'formatter': 'alert'
            },
        },
        'root': { 'handlers': ['console'] },
        'loggers': {
            'OpenGL': { 'level': 'INFO' },
            'OpenGL.calltrace': { 'level': 'CRITICAL', 'propagate': False },
            'OpenGL.extensions':        { 'level': 'WARN' },
            'fgt.args': { 'level': 'WARN', 'propagate': False, 'handlers': ['alert'] }
        },
    }

    logging.config.dictConfig(lcfg)

    if gltrace:
        logger = logging.getLogger('OpenGL.calltrace')
        logger.setLevel('INFO')
        if gltrace != 'stderr':
            logger.addHandler(logging.StreamHandler(stream=open(gltrace, 'w')))
        else:
            logger.propagate = True

    if glinfo:
        logging.getLogger('fgt.glinfo').setLevel('INFO')
        if glinfo == 'exts':
            logging.getLogger('fgt.glinfo.extensions').setLevel('INFO')

    try:
        icfg = {}
        for doc in yaml.safe_load_all(open(extraconf)):
            icfg.update(doc)
        icfg['incremental'] = True
        icfg['version'] = 1
        logging.config.dictConfig(icfg)
    except IOError:
        if extraconf != 'logs.conf':
            logging.getLogger('fgt.args').exception('opening {}'.format(extraconf))
            sys.exit(1)
    except (ValueError, yaml.YAMLError):
        logging.getLogger('fgt.args').exception('parsing logs.conf')
        sys.exit(1)

    if gltrace and 'GLTRACE' not in os.environ:
        logging.getLogger('fgt.args').warn('Set GLTRACE env var to actually trace GL calls.')

class _fgt_config_container(object):
    def __init__(self):
        self.ap = None
        self.pa = None

    def __call__(self, **kwargs):
        self.ap = argparse.ArgumentParser(**kwargs)
        self.ap.add_argument('-logconf', metavar='logs.conf', type=str, default='logs.conf',
            help="logging conf file instead of './logs.conf'")

    def parse_args(self):
        self.pa = self.ap.parse_args()
        logconfig(getattr(self.pa,"glinfo", False),
                    getattr(self.pa,"gltrace", False), self.pa.logconf)

    def add_argument(self, *args, **kwargs):
        return self.ap.add_argument(*args, **kwargs)

    def add_render_args(self, **kwargs):
        self.ap.add_argument('-choke', metavar='fps', type=float, default=0, help="renderer fps cap")
        self.ap.add_argument('-psize', metavar="psize", type=int, help="point size")
        self.ap.add_argument('-par', metavar="par", type=float, help="point aspect ratio")
        self.ap.add_argument('-ss', metavar='sname', help='shader set name', default='step')
        self.ap.set_defaults(**kwargs)

    def add_gl_args(self, **kwargs):
        self.ap.add_argument('-gltrace', metavar="outfile", nargs='?', type=str, const='calltrace.out',
                help="write GL call trace to given file; enable by setting GLTRACE env var")
        self.ap.add_argument('-glinfo', metavar="exts", nargs='?', type=str, const='noexts',
                help="log GL caps and possibly extensions")
        self.ap.add_argument('-shaderpath', metavar='ssdir', help='path to shader sets', default='lib/shaders')
        self.ap.set_defaults(**kwargs)

    def add_ui_args(self, **kwargs):
        self.ap.add_argument('-uifont', metavar='family[,pt]', help='font family substring[,size]', default=None)
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

class EmaFilter(object):
    """ http://en.wikipedia.org/wiki/Exponential_moving_average

        used here for the FPS counters. seed of 16 corresponds
        to approximately 60 fps if we're talking microseconds.

        alpha of 0.01 is completely arbitrary, see the wikipedia article.

        usage: supply whatever time it took to render previous frame
        to the value() method and it'll return a filtered value.

        filtered fps = 1.0 / filtered value

        todo: convert this into a generator.
    """
    def __init__(self, alpha, nseed):
        self.alpha = alpha
        self._value = None
        self.nseed = nseed
        self.seeds = []

    def update(self, val):
        if self.nseed is not None:
            self.seeds.append(val)
            if len(self.seeds) == self.nseed:
                self._value = sum(self.seeds)/len(self.seeds)
                self.nseed = None
        else:
            self._value = self.alpha*val + (1-self.alpha)*self._value

    def value(self, val=None):
        self.update(val)
        return self._value
