# tests/

`check_mobile_annotations.py` runs Playwright against an assembled site in an
isolated localhost server. It checks that every upgraded 3D viewer starts with
an unobstructed canvas on phones, then exercises touch selection, dismissal,
language changes, compact viewports, and desktop annotation defaults.

```powershell
rtk proxy py -3.13 tests/check_mobile_annotations.py --site site/dist
```

Use `--screenshots <directory>` to save phone previews outside the public site.
Python Playwright and its Chromium browser must already be installed.
The regression also loads all 25 generated pages at 320×568, 390×700,
740×360 and 1440×900, checking page errors, image loading, horizontal
overflow and mobile annotation defaults. This is Chromium viewport and touch
simulation, not a physical-device certification.
