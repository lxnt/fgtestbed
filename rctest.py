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

import os
import sys
import argparse
import logging
import time

import fgt
import fgt.gl
import fgt.raw

def main():
    fgt.config(description = 'full-graphics raws parser/compiler')
    fgt.config.add_data_args()
    fgt.config.add_argument('-dump-dir', metavar='dir-name', 
            help="dump intermediate representation, dispatch, blitcode and the texture album here")
    fgt.config.add_argument('-lint', nargs='?', metavar='zstart', type=int, const=-1,
            help="cross-check compiler output, starting at z-level zstart; results written to 'lint.out'")
    fgt.config.parse_args()
    
    if fgt.config.dump_dir is not None and not os.path.isdir(fgt.config.dump_dir):
        os.mkdir(fgt.config.dump_dir)
    
    fgt.gl.sdl_offscreen_init()
    
    mo = fgt.raw.MapObject(     
        dfprefix = fgt.config.dfdir,
        fgraws = [ fgt.config.std ] + fgt.config.ext,
        apidir = fgt.config.apidir,
        dump_dir = fgt.config.dump_dir)

    mo.use_dump(fgt.config.dfdump, fgt.config.dump_dir)

    if fgt.config.lint is not None:
        mo.lint(fgt.config.lint)

    fgt.gl.sdl_fini()
    return 0

if __name__ == "__main__":
    sys.exit(main())
