#version 130
#line 2 0
precision highp int;
precision highp float;

uniform sampler2D font;

uniform float final_alpha;
uniform vec3 pszar;             // { Parx, Pary, Psz }
uniform float darken;  // drawing lower levels.

flat in vec4 blit;   // fka 'tile', but zw are pre-divided with txsz.xy
flat in vec4 fg;
flat in vec4 bg;
flat in float mode;

out vec4 color;

void main() {
    vec2 pc = gl_PointCoord/pszar.xy;
    if ((pc.x > 1.0) || (pc.y > 1.0) || (blit.z == 0)) {
        discard;
    }
    vec2 texcoords = vec2 (blit.x + pc.x * blit.z, blit.y + pc.y * blit.w );
    vec4 tile_color = texture2D(font, texcoords);
    if (mode > 0) {
	color = fg * tile_color * darken;
    } else {
	color = mix(tile_color * fg, bg, 1.0 - tile_color.a) * darken;
    }
    color.a = final_alpha;    
}
