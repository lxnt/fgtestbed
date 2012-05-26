#version 130
#line 2 0

uniform sampler2D hudtex;

in vec2 coord;
out vec4 frag;

void main() {
    frag = texture(hudtex,  coord);
}
