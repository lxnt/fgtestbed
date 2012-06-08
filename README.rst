wotsit?
=======


**fgtestbed** is a prototype full-graphics renderer for the Dwarf Fortress.

The prototype is written in Python and works on custom-format dumps of DF map data.

The purpose of this prototype is to design and test rendering methods and graphic
definition format.

After this is done, the renderer will be gradually rewritten in C++ and merged to the libgraphics code to become PRINT_MODE:FULL_GRAPHICS. 

What it uses
------------

On the system site, fgtestbed requires OpenGL 3.0/GLSL 1.30 capable hardware and drivers.

It is known to not work with AMD/ATI Catalyst 12.4.

Python 3.2, python3-lxml, python3-yaml, trunk PyOpenGL, pgreloaded libSDL 2.0, SDL_image and SDL_ttf are the dependencies. 

Precompiled binaries for the SDL family, known-working PyOpenGL and pgreloaded are provided as a separate download `here <http://dffd.wimbli.com/file.php?id=6445>`__ (linut 64-bit only).

On the Dwarf Fortress side, it requires *some* installation of version 34.10 or 34.11.
Standard and custom tile sets and graphics sets are supported. 

Map dumps are generated using a version of libgraphics.so with dumping code integrated. You can get it `here <http://dffd.wimbli.com/file.php?id=6210>`__ (linux 34.11 only). When running DF with it, press F12 to generate dump or F11 to dump and quit. Resulting file is called 'fugr.dump'. 


Graphics raws format
--------------------

Is documented in raws files themselves. Please see `raws/std/proto.yaml <https://github.com/lxnt/fgtestbed/blob/master/raw/std/proto.yaml>`__.

Overall fg-raws format is `YAML <http://yaml.org>`__.

Launching
---------

On linux, do it like this::

  ./fgt ../df_linux ../df_linux/fugr.dump raw/fakefloors

Where ../df_linux is the path to your df installation, ../df_linux/fugr.dump is a path to a map dump (there are some supplied in precompiled binaries archive) and raw/fakefloors is a path to fg-raws directory containing a "mod" demonstrating floors drawn under trees, boulders, and animated driftwood.

If you feel like experimenting with fg-raws themselves, create a directory and put some yaml in there.
Then supply it at the end of the above command line. Model it based on supplied yaml files. The code parses directories of yaml files in the order listed (first and implicitly goes the raw/std directory), definitions from later ones overriding the former ones. PNG file paths are relative to the directory they are referenced in. Cel page references are (to be) limited to a single raws directory, so you should not rely on any other directories being parsed earlier (or ever). The only exception is the 'std' celpage which refers to the init.txt-defined standard tileset.

Rest of command-line options can be viewed with::

  ./fgt -h

Keeping current
---------------

To keep track of latest developments, clone the git repository::

  git clone https://github.com/lxnt/fgtestbed
  cd fgtestbed
  git submodule init
  git submodule update
  
then move in the lib and dump directories from the precompiled binary archive.

After that do::

  cd fgtestbed
  git pull
  git submodule update
  
to fetch any changes.



Dump format
-----------

The dump file consists of two text parts, with a binary part in between.
The first text part starts with header, which gives necessary offsets and metadata to parse the rest.
Example::

  origin:0:0:0
  extent:12:12:156
  window:0:74:130
  tiles:196608:92078080
  flows:92274688

Description:
origin and extent define which part of the map was dumped (all of it for now). 
window is the tile-coordinates of the map window top-left corner at the time the dump was taken, used to 'recenter' the fgtesbed viewer. 
tiles is the offset and length of binary dump data. For its exact format please see rendumper's fugr_dump.cc file.
flows is the offset to the final text section which contains data about smoke, mist and the like.

After this header there go sections, beginning with a 'section' line ::

  section:materials
  section:buildings
  section:constructions
  section:building_defs
  section:items
  section:units

All but the materials section are not used yet and thus have somewhat freeform format, just to take a look on what's in there.
The materials one is an index to which the binary data refers.

Binary data has 128 bits for each map tile, encoding tile type, base tile material (stone/plant), bulding tile type and material, grass material and amount, and the designation value which contains water/magma levels, hidden/aquifer flags, etc. For the exact format please see rendumper's fugr_dump.cc file.




