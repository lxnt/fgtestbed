#!/usr/bin/python


tilepage='curses16sq'
for mat in 'CHERT SLATE SAND_BLACK PHYLLITE SILTY_CLAY MICROCLINE KAOLINITE MAGNETITE LIGNITE TETRAHEDRITE'.split():
    print "[MAT:{0}]".format(mat)
    for tile in 'SoilWall StoneWall MineralWall'.split():
        print '{1}[TILE:{0}]'.format(tile, ' '*4)
        tfn = '{0}_{1}'.format(mat, tile).upper()
        ck=0
        for c in tfn:
            ck += 4
            print '{2}[BLIT:{0}:{1}]'.format(tilepage, c, ' '*8)
            print '{1}[KEY:{0}]'.format(ck, ' '*8)
                



