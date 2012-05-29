wotsit?
=======


**fgtestbed** is a prototype full-graphics renderer for the Dwarf Fortress.

The prototype is written in Python and works on custom-format dumps of DF map data.

The purpose of this prototype is to design and test rendering methods and graphic
definition format. 

After this is done, the renderer will be gradually rewritten in C++ and merged to the libgraphics code to become PRINT_MODE:FULL_GRAPHICS. 

At first I plan to merge only map drawing code and draw it instead the DF's map window, leaving the rest of the interface intact. 

When this works acceptably, it would be possible to begin replacing most critical parts of DF's interface with rewritten ones, dig designation, K and V views and unit list being both the most notorious and relatively simple to implement.

What it uses
------------

On the system site, fgtestbed requires OpenGL 3.0/GLSL 1.30 capable hardware and drivers, Python 3.2, trunk PyOpenGL and pgreloaded are the dependencies.

On the Dwarf Fortress side, it requires *some* installation of version 34.10. 
Standard and custom tile sets and graphics sets are supported. 

A special version of print_mode:shader renderer is required for generating map dumps. You can get it `here <http://dffd.wimbli.com/file.php?id=5763>`_ (linux only). When running DF with it, press F12 to generate dump or F11 to dump and quit. 
Resulting file is called 'fugr.dump'. 


Graphics raws format
--------------------

Is documented in raws files themselves. Please see fgraws-stdpage/proto.txt.

Image data itself is supplied just like existing graphic sets, with CEL_PAGE tokens (aka TILE_PAGE).

Launching
---------

On linux, do it like this::

  ./fgtestbed.py ../df_linux ../df_linux/fugr.dump fgraws-stdpage

Currently it is recommended to copy and modify the fgraws-stdpage directory.

Rest of command-line options can be viewed with::

  ./fgtestbed.py -h

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




