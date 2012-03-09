#version 130
#line 2 0
precision highp int;
precision highp float;

uniform usampler2D dispatch;      // blit_insn to blitcode_idx lookup table. Texture is GL_RG16UI.
uniform usampler2DArray blitcode; // blit and blend insns. Texture is GL_RGBA32UI ARRAY
uniform int frame_no;
uniform ivec4 txsz;               // { w_tiles, h_tiles, max_tile_w, max_tile_h } <- font texture params.
uniform int dispatch_row_len;
uniform ivec2 grid;
uniform vec3 pszar;               // { parx, pary, psz }
uniform ivec2 mouse_pos;

in ivec2 position; 
in int screen;
in uint designation;

flat out vec4 blit;
flat out vec4 fg;
flat out vec4 bg;
flat out int mode;
flat out int mouse_here;
flat out uint des;

void main() {
    vec2 normposn = (position + 0.5)/grid;
    normposn.y = 1.0 - normposn.y;
    vec2 posn = 2.0 * pszar.xy*normposn - 1.0;
    gl_Position = vec4(posn.x, posn.y, 0.0, 1.0);
    gl_PointSize = pszar.z;
    des = designation;

    if  (mouse_pos == position) { 
	mouse_here = 23;
    } else {
	mouse_here = 0;
    }

    uvec4 addr;
    addr = texelFetch(dispatch, ivec2( screen % dispatch_row_len, screen / dispatch_row_len ), 0 );
    addr.z = uint(frame_no);

    if ((addr.x + addr.y) == 0u) { // not defined.
	blit = vec4(0,0,0,0);
	fg = vec4(0,0,0,0);
	bg = vec4(0,0,0,0);
	mode = -1;
	return;
    }

    uvec4 insn = texelFetch(blitcode, ivec3(addr.xyz), 0);
    
    blit.xy = vec2(insn.x>>24u, (insn.x>>16u ) &0xffu)/ vec2(txsz.xy) ;
    blit.zw = 1.0 / vec2(txsz.xy) ; // for as long as we don't support tiles-smaller-than-txsz.zw
    // when we do: blit.zw = vec2( (insn.x>>8u)&0xffu,insn.x&0xffu )/vec2(txsz.xy);
    
    mode = int(insn.y);
    fg = vec4(insn.z>>24u, (insn.z>>16u ) &0xffu, (insn.z>>8u ) &0xffu, insn.z & 0xffu) / 256.0;
    bg = vec4(insn.w>>24u, (insn.w>>16u ) &0xffu, (insn.w>>8u ) &0xffu, insn.w & 0xffu) / 256.0;

}
