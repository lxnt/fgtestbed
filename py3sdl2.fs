#version 130
#line 2 0

out vec4 frag;

void main() {
    frag = vec4(gl_PointCoord.st, 0, 1);
    //frag = vec4(0.75, 0.5, 0.25, 1);
}
