#version 130
#line 2 0

// lt rt rb lb

uniform ivec2 resolution;

in ivec4 position; 
out vec2 coord;

void main() {	
    vec2 posn = 2.0 * vec2(position.xy) / vec2(resolution) - 1.0;
    gl_Position = vec4(posn.x, posn.y, 0.0, 1.0);
    gl_PointSize = 34;
    coord = vec2(position.zw);
}
