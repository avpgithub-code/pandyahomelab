#!/bin/sh
# Scaffold a new NLP demo from nlp-project-template.
#
#   nlp/_templates/new-nlp-project.sh <project-name> <slot> "<Title>"
#   nlp/_templates/new-nlp-project.sh nlp-quora-randomforest 0 "Quora Duplicate Questions"
#
# <slot> is the demo's position in docs/NETWORK_CIDR_SUMMARY.md §5 (0 = .10/8020,
# 1 = .11/8021, ...). IP and host port are derived from it so they always match
# the locked allocation; nothing is invented per project.
set -eu

if [ $# -ne 3 ]; then
  echo "usage: $0 <project-name> <slot 0-9> \"<Title>\"" >&2
  exit 1
fi

NAME=$1
SLOT=$2
TITLE=$3

case "$NAME" in
  nlp-*) ;;
  *) echo "project name must start with nlp- (ADR-004)" >&2; exit 1 ;;
esac
case "$SLOT" in
  [0-9]) ;;
  *) echo "slot must be a single digit 0-9" >&2; exit 1 ;;
esac

HERE=$(cd "$(dirname "$0")" && pwd)
DEST="$HERE/../$NAME"
SLUG=${NAME#nlp-}
IP="172.22.0.1$SLOT"
PORT="802$SLOT"

if [ -e "$DEST" ]; then
  echo "$DEST already exists" >&2
  exit 1
fi

cp -R "$HERE/nlp-project-template" "$DEST"
cd "$DEST"

grep -rl '__PROJECT__\|__SLUG__\|__IP__\|__PORT__\|__TITLE__' . | while read -r f; do
  sed -i \
    -e "s#__PROJECT__#$NAME#g" \
    -e "s#__SLUG__#$SLUG#g" \
    -e "s#__IP__#$IP#g" \
    -e "s#__PORT__#$PORT#g" \
    -e "s#__TITLE__#$TITLE#g" \
    "$f"
done

ln -sf db-logic db_logic
ln -sf application-logic application_logic
ln -sf presentation-logic presentation_logic

echo "Created $DEST"
echo "  container  $NAME  $IP:8000  →  127.0.0.1:$PORT"
echo "  route      /nlp/$SLUG/"
echo "Left for you: __DESCRIPTION__ / __SUBTITLE__ and every TODO (grep -rn 'TODO\\|__DESCRIPTION__\\|__SUBTITLE__' $DEST)"
