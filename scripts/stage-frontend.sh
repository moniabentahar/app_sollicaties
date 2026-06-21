#!/usr/bin/env bash
# Stage the latest client build (dist/client) into frontend/dist as a SPA so the
# PC backend serves the newest app. Entry = the JS bundle that bootstraps React.
set -e
cd "$(dirname "$0")/.."
SRC="dist/client/assets"
DST="frontend/dist"
rm -rf "$DST"; mkdir -p "$DST/assets"
cp -f "$SRC"/* "$DST/assets/"
ENTRY=""
for f in "$SRC"/index-*.js; do
  if grep -qE "hydrateRoot|createRoot" "$f"; then ENTRY="$(basename "$f")"; break; fi
done
CSS="$(basename "$(ls "$SRC"/*.css | head -1)")"
cat > "$DST/index.html" <<HTML
<!DOCTYPE html>
<html lang="nl">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Sollicitaties2026 — Job Scan Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet" />
    <link rel="stylesheet" crossorigin href="/assets/$CSS" />
    <script type="module" crossorigin src="/assets/$ENTRY"></script>
  </head>
  <body><div id="root"></div></body>
</html>
HTML
echo "staged: entry=$ENTRY css=$CSS"
