#version 130
#line 2 0

uniform vec2 resolution;
uniform vec2 size;

in ivec2 position; 
out vec2 coord;

void main() {
    gl_Position = vec4(2.0*position.x/resolution.x- 1.0, 2.0*position.y/resolution.y - 1.0, 0.0, 1.0);
    coord = vec2((resolution - position)/size);
    coord.x = 1.0 - coord.x;
}
