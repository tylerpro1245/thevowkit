#!/bin/bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
while read -r u; do
  [ -z "$u" ] && continue
  code=$(curl -sSL -o /dev/null -w "%{http_code}" --max-time 30 -A "$UA" --compressed "$u" 2>/dev/null)
  echo "$code  $u"
done < /opt/data/venture/site/_check/urls.txt
