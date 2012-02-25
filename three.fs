#version 130
#line 2 0
precision highp int;
precision highp float;

uniform sampler2D font;

uniform float final_alpha;
uniform vec3 pszar;             // { Parx, Pary, Psz }

flat in vec4 blit;   // fka 'tile', but zw are pre-divided with txsz.xy
flat in vec4 blend;

out vec4 color;

void main() {
    vec2 pc = gl_PointCoord/pszar.xy;
    if ((pc.x > 1.0) || (pc.y > 1.0) || (blit.z == 0)) {
        discard;
    }
    
    vec2 texcoords = vec2 (blit.x + pc.x * blit.z, blit.y + pc.y * blit.w );
    vec4 tile_color = texture2D(font, texcoords);
    
    //color = mix(tile_color, blend, 1.0 - tile_color.a);
    color = 0.5*tile_color + 0.5*blend;
    color.a = final_alpha;    
}
