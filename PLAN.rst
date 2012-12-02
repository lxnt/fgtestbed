what's going on:
================

UI
--

Moving from fgt.hud - hardcoded panels, SDL_ttf, to fgt.ui -
a layout engine, however primitive, Pango text layout and rendering.

To get rid of fgt.hud:

    - Implement a MapPanel. It should control MapView tile overdraw
      and zoom and respond to pan/zoom/resize. Basically lift all this
      from fgt.gui.Rednerer.

    - Detect and propagate pan/zoom input events.

To make fgt.ui look good:

    - Debug fgt.ui.Box. While it does what is needed for 3-4 panels,
      I suspect lots of bugs there.

    - Load UI structure from yaml. This would aid the debugging.

    - Implement the whole updating and formatting of text panel data
      instead of blindly replacing their text each frame.

    - Play with scissor test when rendering MapViews for MapPanels
      to cut off areas that won't get blitted anyway.

    - Rethink text panel interface to the layout engine.

Further:

    - MapPanel analog for text - scrolling panels.

    - Offload UI to another thread. Once we've got all data for the
      UI's next frame, send it to that thread and continue with
      something CPU-intensive, like preparing map data buffers and such.
      By the time we're done with that, UI would hopefully be laid out
      and text rendered into PBO-backed textures.

    - Look at hacking colored text rendering into PangoFT2, or at least
      somehow exporing color attrs in shader-digestable way.
      I don't like the idea of pulling PangoCairo in here.

Map renderer
------------

    - Move to streaming instead of uploading the whole map dump.
      Mesa's r600 fails at memory management, so this basically
      doesn't work, not to say that we won't have that luxury in real DF.
      Extend fgt.gl.SurfBunchPBO to support TEXTURE_2DARRAY
      and memmove() needed parts of dump there.

    - Render a single tile in debug mode rather than the whole viewport.
      But keep whole-viewport mode since there might be side-effects.
      Read back via fgt.gl.TexFBO.

DF integration
--------------

    - Gather all will there is and start it already. Maybe binary-hack out
      all references to SDL-1.2 from DF to avoid segfaults. Try something.
