#!/bin/sh

FGTDIR=`dirname $0`
TMPDIR=`mktemp -d`
#TMPDIR=/tmp/emoe
mkdir $TMPDIR/fgtestbed

rsync -avk \
--exclude=.git\* --exclude=\*.pyc --exclude=/pics \
--exclude=__pycache__ --exclude=/ird\* --exclude=drop.sh \
$FGTDIR/  $TMPDIR/fgtestbed/

7zr a -t7z -m0=lzma -mx=9 -mfb=64 -md=32m -ms=on $TMPDIR/fgtestbed.7z $TMPDIR/fgtestbed

echo $TMPDIR/fgtestbed.7z

