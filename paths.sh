

export PGLIBDIR="${FGTDIR}/lib"
export PYTHONPATH="${PGLIBDIR}/python3.2/site-packages/"

[ -f "${PGLIBDIR}/SDL2.so" ] || ln -s libSDL2.so ${PGLIBDIR}/SDL2.so
[ -f "${PGLIBDIR}/SDL2_image.so" ] || ln -s libSDL2_image.so ${PGLIBDIR}/SDL2_image.so
[ -f "${PGLIBDIR}/SDL2_ttf.so" ] || ln -s libSDL2_ttf.so ${PGLIBDIR}/SDL2_ttf.so