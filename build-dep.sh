#!/bin/sh -e


WORK=`realpath $1` || true
PREFIX=`realpath $2` || true
PDIR=`realpath ./fgtest.py` || true
PDIR=`dirname $PDIR`
WHAT=$3

if [ -z "${PREFIX}" -o -z "${WORK}" -o -z "${PDIR}" ]
then 
    echo "Usage: $0 work/dir dest/prefix [sdl|py|gir|all]"
    echo "Please run this from the fgtestbed directory."
    exit 1 
fi

export CFLAGS="-g $CFLAGS"
export PATH=$PREFIX/bin:$PATH

if [ ! -d $WORK/pyopengl ]
then
    echo "Cloning pyopengl repository"
    bzr branch lp:pyopengl $WORK/pyopengl
fi

if [ ! -d $WORK/pgreloaded ]
then
    echo "Cloning pygame2 repository"
    hg clone https://code.google.com/p/pgreloaded $WORK/pgreloaded
fi

if [ ! -d $WORK/SDL ]
then
    echo "Cloning SDL2 repository"
    hg clone http://hg.libsdl.org/SDL $WORK/SDL
fi

if [ ! -d $WORK/SDL_image ]
then
    echo "Cloning SDL_image repository"
    hg clone http://hg.libsdl.org/SDL_image $WORK/SDL_image
fi

if [ ! -d $WORK/SDL_ttf ]
then
    echo "Cloning SDL_ttf repository"
    hg clone http://hg.libsdl.org/SDL_ttf $WORK/SDL_ttf
fi

if [ "sdl" = "$WHAT" -o "all" = "$WHAT" ]
then
    [ -d $WORK/build-all ] && rm -r $WORK/build-all
    mkdir -p $WORK/build-all/sdl $WORK/build-all/image $WORK/build-all/ttf
    
    echo "Building and installing SDL2"
    cd $WORK/build-all/sdl
    $WORK/SDL/configure --prefix $PREFIX && make -j 4 install

    echo "Building and installing SDL_image"
    cd $WORK/build-all/image
    $WORK/SDL_image/configure --prefix $PREFIX && make -j 4 install
    
    echo "Building and installing SDL_ttf"
    cd $WORK/build-all/ttf
    $WORK/SDL_ttf/configure --prefix $PREFIX && make -j 4 install
fi

if [ "py" = "$WHAT" -o "all" = "$WHAT" ]
then
    echo "Installing pyopengl"
    cd $WORK/pyopengl
    python3.2 setup.py install --prefix=$PREFIX

    echo "Installing pygame2"
    cd $WORK/pgreloaded
    python3.2 setup.py install --prefix=$PREFIX
fi

if [ "gir" = "$WHAT" -o "all" = "$WHAT" ]
then
    echo "Compiling ft2 typelib"
    g-ir-compiler -o $PDIR/lib/gir/freetype2-2.0.typelib $PDIR/lib/gir/freetype2-2.0.gir
fi

(   echo "#!/bin/sh"
    echo export PGLIBDIR=$PREFIX/lib
    echo export PYTHONPATH=$PREFIX/lib/python3.2/site-packages:$PDIR/lib/python
    echo export GI_TYPELIB_PATH=$PDIR/lib/gir
    echo '"$@"' ) >$PDIR/run
chmod a+x $PDIR/run
    
