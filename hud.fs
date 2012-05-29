#version 130
#line 2 0

uniform sampler2D hudtex; // shall be BW + alpha for antialiasing
uniform vec4 fg; // font color
uniform vec4 bg; // translucency + bg color

in vec2 coord;
out vec4 frag;

void main() {
    vec4 fpix = texture(hudtex,  coord);
    frag = mix(fpix * fg, bg, 1 - fpix.a);
}
