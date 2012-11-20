Wotsit?
-------


This is a prototype full-graphics renderer for the Dwarf Fortress.

The prototype is written in Python and works on custom-format dumps of DF map data.

The purpose of this prototype is to design and test rendering methods and graphic
definition format.

After this is done, the renderer will be gradually rewritten in C++ and merged
to the libgraphics code to become ``[PRINT_MODE:FULL_GRAPHICS]``.


What it uses
------------

On the system side, fgtestbed requires OpenGL 3.0/GLSL 1.30 capable hardware and drivers.

On the Dwarf Fortress side, it requires *some* installation of version 34.10 or 34.11.
Standard and custom tile sets and graphics sets are supported.

Python 3.2, python3-lxml, python3-yaml, trunk PyOpenGL, pgreloaded, libSDL 2.0,
SDL_image and SDL_ttf are the code dependencies.


Getting started
---------------

Make sure that you have needed packages. For Ubuntu, do::

  apt-get install python3.2 python3-lxml, python3-yaml realpath git bzr mercurial
  apt-get build-dep libsdl1.2debian libsdl-ttf2.0-0 libsdl-image1.2

Clone the git repository::

  user@box:~$ git clone https://github.com/lxnt/fgtestbed
  user@box:~$ cd fgtestbed
  user@box:~/fgtestbed$ git submodule init
  user@box:~/fgtestbed$ git submodule update

Pull in, build and install non-packaged dependencies::

  user@box:~/fgtesbed$ mkdir deps prefix
  user@box:~/fgtesbed$ ./build-dep.sh ./deps ./prefix all

     ... lots of output ...

  user@box:~/fgtesbed$

This will download dependencies' source code into the deps directory and install them under prefix directory.
This will also create a "run" file. This file can either be used as a launcher::

  user@box:~/fgtesbed$ ./run ./gltest.py

or as a shell config file::

  user@box:~/fgtesbed$ . run
  user@box:~/fgtesbed$ ./gltest.py
  ...

``gltest.py`` is a simple testing script that will display a window with rainbow tiles and some text,
or fail if something went wrong or your OpenGL drivers are not up to the task. Ask for help
in the `forum thread <http://www.bay12forums.com/smf/index.php?topic=94528.666>`__.

Download the dump pack from `<https://github.com/downloads/lxnt/fgtestbed/dumps-341x.7zr>`__ and extract it
in the directory. It will create ``dumps`` directory with four example dumps.

Now, assuming there's a df-34.11 installation in ``/home/user/df_linux``, test it::
  
  user@box:~/fgtesbed$ ./run ./fgtest.py dumps/micro.dump

Otherwise you will have to supply the path to the df directory::

  user@box:~/fgtesbed$ ./run ./fgtest.py -dfdir /home/df/df_whatever dumps/micro.dump

Watch magnificently swirling drifwood and grass growing under the trees::

    user@box:~/fgtesbed$ ./run ./fgtest.py dumps/driftwood.dump raw/fakefloors


Generating map dumps
--------------------


Map dumps are generated using a version of libgraphics.so with dumping code built in.
You can get it `here <http://dffd.wimbli.com/file.php?id=6210>`__ (df_linux 34.11 only).

When running DF with it, press ``F12`` to generate dump or ``F11`` to dump and quit.
Resulting file is called 'fugr.dump'.


Graphics raws format
--------------------

Is documented in raws files themselves. Please see
`raws/std/proto.yaml <https://github.com/lxnt/fgtestbed/blob/master/raw/std/proto.yaml>`__.

Overall fg-raws format is `YAML <http://yaml.org>`__.

If you feel like experimenting with fg-raws themselves, create a directory and put some yaml in there.
Then supply it at the end of the above command line.

Model it based on supplied yaml files. The code parses directories of yaml files in the order listed
(first and implicitly goes the raw/std directory), definitions from later ones overriding the former ones.

Each directory is treated as a raws module. All yaml files there can refer to the tilesets,
materialsets, effects and cel pages defined only in the files from the same directory, with the exception
of ``std`` cel page which always refers to the ``init.txt`` - defined standard 16x16 tile set.
Cel page definitions can only refer to the graphic files in the same directory.

Nesting of directories is allowed, but keep in mind that the order in which subdirectories
are processed is not defined.

For more information see comments in the yaml files.

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

``origin`` and ``extent`` define which part of the map was dumped (all of it for now).

``window`` is the tile-coordinates of the map window top-left corner at the time the dump was taken,
used to recenter the ``fgtest.py`` viewer.

``tiles`` is the offset and length of binary dump data. For its exact format please
see rendumper's `fugr_dump.cc <https://github.com/lxnt/rendumper/blob/master/g_src/fugr_dump.cc>`__ file.

``flows`` is the offset to the final text section which contains data about smoke, mist and the like.

After this header there go sections, each beginning with a section header::

  section:materials
  section:buildings
  section:constructions
  section:building_defs
  section:items
  section:units

All but the materials section are not used yet and thus have somewhat freeform format,
just to take a look on what's in there. The materials one is an index to which the binary data refers.

Binary data has 128 bits for each map tile, encoding tile type, base tile material (stone/plant),
bulding tile type and material, grass material and amount, and the designation value
which contains water/magma levels, hidden/aquifer flags, etc. For the exact format please
see rendumper's `fugr_dump.cc <https://github.com/lxnt/rendumper/blob/master/g_src/fugr_dump.cc>`__ file.




