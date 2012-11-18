#!/usr/bin/python3.2
# -*- encoding: utf-8 -*-
#
# lxnt has created fgtestbed, a lump of python code
# all masterwork is of dubious quiality.
# it is studded with bugs
# it is encrusted with bugs
# it is smelling with bugs
# it menaces with spikes of bugs
# a picture of giant bug is engraved on its side
# ...
# lxnt cancels Store item in stockpile: interrupted by bug
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
import sys
import argparse
import logging

import fgt
import fgt.raw
import fgt.gl
import fgt.gui

def main():
    fgt.config(description = 'full-graphics renderer testbed')
    fgt.config.add_render_args()
    fgt.config.add_data_args()
    fgt.config.add_argument('-afps', metavar='afps', type=float, default=12, help="animation fps")
    fgt.config.add_argument('-zeddown', metavar='zlevels', type=int, 
            help="number of z-levels to draw below current", default=4)
    fgt.config.parse_args()
    
    window, context = fgt.gl.sdl_init()
    
    mo = fgt.raw.MapObject(     
            dfprefix = fgt.config.dfdir,
            fgraws = [ fgt.config.std ] + fgt.config.ext,
            apidir = fgt.config.apidir,
            dump_dir = None)
    mo.use_dump(fgt.config.dfdump)

    rednr = fgt.gui.Rednerer(window, fgt.config.ss, mo, fgt.config.psize, 
                fgt.config.par, fgt.config.zeddown, fgt.config.afps)
    rednr.loop(fgt.config.choke)
    rednr.fini()
    
if __name__ == "__main__":
    main()
