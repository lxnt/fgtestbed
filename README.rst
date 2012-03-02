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

On the system site, fgtestbed requires OpenGL 3.0/GLSL 1.30 capable hardware and drivers. Python 2.7, PyOpenGL, numpy and pygame are the dependencies.

On the Dwarf Fortress side, it requires *some* installation of version 31.25. 
Standard and custom tile sets and graphics sets are supported. 

A special version of print_mode:shader renderer is required for generating map dumps. You can get it `here <http://dffd.wimbli.com/file.php?id=5763>`_ (linux only). When running DF with it, press F12 to generate dump. Resulting file is called 'fugr.dump'. 


Graphics raws format
--------------------

Is documented in raws files themselves. Please see fgraws/proto.txt.

Image data itself is supplied just like existing graphic sets, with TILE_PAGE tokens.

Launching
---------

On linux, do it like this::

  ./fgtestbed.py ../df_linux ../df_linux/fugr.dump

If you've got some extra raws, tack the directory[ies] with them at the end::

  ./fgtestbed.py ../df_linux ../df_linux/fugr.dump ./some-custom-raws

All files in that directory will be processed. By default, code processes ./fgraws directory, so you can just edit files there.

Rest of command-line options can be viewed with::

  ./fgtestbed.py -h

Dump format
-----------

 - [0:4096] - header, with sizes and offsets, text. Padded with "\\n".
 - [4096:tiles_offset] - text sections except effects, zero-padded to pagesize alignment.
 - [tiles_offset:designations_offset] - map data, zero-padded to pagesize alignment.
 - [designations_offset:effects_offset] - designations data, zero-padded to pagesize alignment.
 - [effects_offset:eof] - effects data, text.

Typical 3x3 embark results in about 24 megabytes uncompressed, 0.5 megabytes lzma-compressed. Note that file must be uncompressed to be used, because fgtestbed mmap()s portions of it.

Since I'm lasy, be sure to move previous dump somewhere before making another.


