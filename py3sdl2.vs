#version 130
#line 2 0

uniform ivec2 grid;
uniform  vec3 pszar;

in ivec2 position;

void main() { 
    vec2 posn = 2.0 * (position + 0.5)/grid - 1.0;
    gl_Position = vec4(posn.x, posn.y, 0.0, 1.0);
    gl_PointSize = pszar.z;
}
