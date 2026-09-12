"""Browser regression for unobstructed mobile atlas views; use a built site copy."""
import argparse
import asyncio
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.async_api import async_playwright, expect


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


async def check(base, routes, screenshots, all_routes):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=[
            '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
        ])
        mobile = await browser.new_context(viewport={'width': 390, 'height': 700},
                                           is_mobile=True, has_touch=True)
        await mobile.add_init_script("localStorage.setItem('neuroLang','zh')")
        page = await mobile.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        for route in routes:
            await page.goto(base + route)
            await expect(page.locator('.na-mobile-annotations')).to_have_attribute('aria-pressed', 'false')
            await expect(page.locator('.na-callout:visible')).to_have_count(0)
            await expect(page.locator('#naNodeDetail')).to_be_hidden()
            assert await page.evaluate('''() => {
                const c=document.querySelector('#scene canvas'), r=c.getBoundingClientRect();
                return r.width>100 && r.height>100 &&
                  document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===c &&
                  document.documentElement.scrollWidth<=innerWidth;
            }'''), route
            print('PASS mobile default:', route, flush=True)

        await page.goto(base + '/mouse/visual/')
        await page.wait_for_function("""() => {
            const loading=document.querySelector('#loading');
            return !loading || getComputedStyle(loading).opacity==='0';
        }""")
        toggle = page.locator('.na-mobile-annotations')
        await expect(toggle).to_have_text('顯示節點')
        if screenshots:
            await page.screenshot(path=str(screenshots / 'mobile-default-zh.png'))
        await toggle.tap()
        markers = page.locator('.na-callout:visible')
        await expect(markers.first).to_be_visible()
        assert await markers.evaluate_all('''nodes => nodes.every(n => {
            const r=n.getBoundingClientRect(); return r.width<=45 && r.height<=45 &&
            getComputedStyle(n.querySelector('.na-callout-copy')).display==='none' &&
            n.getAttribute('aria-label').length>4;
        })''')
        await markers.first.tap()
        await expect(page.locator('#naNodeDetail')).to_be_visible()
        await expect(page.locator('#naEvidence')).to_be_hidden()
        await expect(page.locator('#naScale')).to_be_hidden()
        if screenshots:
            await page.screenshot(path=str(screenshots / 'mobile-selected-zh.png'))
        await page.locator('.na-detail-close').tap()
        await expect(page.locator('#naNodeDetail')).to_be_hidden()
        await expect(page.locator('#naEvidence')).to_be_hidden()
        await page.locator('#naButton-guide').tap()
        await expect(page.locator('#naPane-guide #naEvidence')).to_be_visible()
        await expect(page.locator('#naPane-guide .na-stage-note')).to_be_visible()
        await page.locator('#naClose').tap()
        await toggle.tap()
        await expect(markers).to_have_count(0)
        await page.locator('#langToggle').tap()
        await expect(toggle).to_have_text('Show nodes')
        for width, height in [(320,568),(430,780),(760,700),(740,360)]:
            await page.set_viewport_size({'width':width,'height':height})
            await expect(markers).to_have_count(0)
            assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        print('PASS touch selection, close, hide, language and narrow/landscape sizes', flush=True)

        desktop = await browser.new_context(viewport={'width':1440,'height':900})
        wide = await desktop.new_page()
        wide.on('pageerror', lambda error: errors.append(str(error)))
        await wide.goto(base + '/mouse/visual/')
        await expect(wide.locator('.na-mobile-annotations')).to_be_hidden()
        await expect(wide.locator('.na-callout:visible').first).to_be_visible()
        assert await wide.locator('.na-callout:visible').first.evaluate('(e)=>e.getBoundingClientRect().width>80')
        await wide.set_viewport_size({'width':390,'height':700})
        await expect(wide.locator('.na-callout:visible')).to_have_count(0)
        await wide.set_viewport_size({'width':1440,'height':900})
        await expect(wide.locator('.na-callout:visible').first).to_be_visible()
        print('PASS desktop labels and responsive default restoration', flush=True)
        await mobile.close()
        await desktop.close()
        for width, height in [(320,568), (390,700), (740,360), (1440,900)]:
            await browser.close()
            browser = await playwright.chromium.launch(args=[
                '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
            ])
            context = await browser.new_context(viewport={'width':width,'height':height},
                                                has_touch=width<=760, is_mobile=width<=760)
            audit = await context.new_page()
            audit.on('pageerror', lambda error: errors.append(str(error)))
            for route in all_routes:
                response = await audit.goto(base + route)
                assert response.status == 200, route
                assert await audit.title(), route
                assert await audit.evaluate('document.documentElement.scrollWidth<=innerWidth'), (route,width)
                if route in routes:
                    await expect(audit.locator('#scene canvas')).to_be_visible()
                    if width<=760:
                        await expect(audit.locator('.na-callout:visible')).to_have_count(0)
                        await expect(audit.locator('#naNodeDetail')).to_be_hidden()
                assert await audit.evaluate('''() => [...document.images].every(i =>
                    !i.getAttribute('src') || (i.complete && i.naturalWidth>0))'''), ('images',route)
            print(f'PASS all {len(all_routes)} pages at {width}x{height}', flush=True)
            await context.close()
        assert not errors, errors
        await browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--screenshots', type=Path)
    args = parser.parse_args()
    site = args.site.resolve(strict=True)
    routes = ['/' + p.relative_to(site).as_posix() for p in sorted(site.rglob('*.html'))
              if 'id="neuroSceneStyle"' in p.read_text(encoding='utf-8')]
    assert routes, 'No assembled 3D viewers found'
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    with ThreadingHTTPServer(('127.0.0.1',0), partial(QuietHandler,directory=str(site))) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            all_routes = ['/' + p.relative_to(site).as_posix() for p in sorted(site.rglob('*.html'))]
            asyncio.run(check(f'http://127.0.0.1:{server.server_port}',routes,args.screenshots,all_routes))
        finally:
            server.shutdown()
            thread.join()
    print(f'PASS: {len(routes)} shared 3D viewers; no application errors')


if __name__ == '__main__':
    main()
