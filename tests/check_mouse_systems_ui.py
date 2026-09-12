"""Touch interactions and bilingual discovery for the nine new mouse systems."""
import argparse
import asyncio
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.async_api import async_playwright, expect
from check_mobile_annotations import QuietHandler

SLUGS=['auditory','somatosensory','gustatory','vestibular','cerebellum','limbic','pain','sleep','autonomic']


async def check(base):
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        context=await browser.new_context(viewport={'width':390,'height':700},has_touch=True,is_mobile=True)
        await context.add_init_script("localStorage.setItem('neuroLang','zh')")
        page=await context.new_page()
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        for slug in SLUGS:
            await page.goto(base+'/mouse/'+slug+'/')
            await page.wait_for_function("getComputedStyle(document.querySelector('#loading')).opacity==='0'")
            await expect(page.locator('.na-mobile-annotations')).to_have_text('顯示節點')
            await expect(page.locator('.na-callout:visible')).to_have_count(0)
            await page.locator('.na-mobile-annotations').tap()
            nodes=page.locator('.na-callout:visible')
            await expect(nodes.first).to_be_visible()
            await nodes.first.tap()
            await expect(page.locator('#naNodeDetail')).to_be_visible()
            await page.locator('.na-detail-close').tap()
            await page.locator('#naButton-layers').tap()
            branches=page.locator('#naPane-layers input[id^="pw_"]')
            for branch in await branches.all():
                await branch.uncheck()
            await page.locator('#naClose').tap()
            await expect(nodes).to_have_count(0)
            await page.locator('#naButton-layers').tap()
            for branch in await branches.all():
                await branch.check()
            # Each anatomical layer remains independently operable.
            for layer in await page.locator('#naPane-layers input[data-target]').all():
                await layer.uncheck()
                await expect(layer).not_to_be_checked()
                await layer.check()
            await page.locator('#naClose').tap()
            await page.locator('.na-mobile-annotations').tap()
            canvas=page.locator('#scene canvas')
            before=await canvas.screenshot()
            rect=await canvas.bounding_box()
            x,y=rect['x']+rect['width']*.6,rect['y']+rect['height']*.5
            await page.mouse.move(x,y)
            await page.mouse.down()
            await page.mouse.move(x+60,y+35,steps=12)
            await page.mouse.up()
            await page.wait_for_timeout(200)
            assert before!=await canvas.screenshot(), (slug,'rotation')
            await page.locator('#naButton-controls').tap()
            await page.locator('.na-reset').tap()
            await page.locator('#naClose').tap()
            reset=await canvas.screenshot()
            await page.locator('#naButton-controls').tap()
            await page.locator('.na-zoom button').first.tap()
            await page.locator('#naClose').tap()
            await page.wait_for_timeout(200)
            assert reset!=await canvas.screenshot(), (slug,'zoom')
            for language in ['zh','en']:
                if language=='en':
                    await page.locator('#langToggle').tap()
                await page.locator('#naButton-guide').tap()
                await expect(page.locator('#naPane-guide')).to_contain_text('Allen')
                await expect(page.locator('#naPane-guide')).to_contain_text('Finch')
                await expect(page.locator('#naPane-guide')).to_contain_text('不構成醫療建議' if language=='zh' else 'not medical advice')
                assert await page.locator('#naPane-guide a[href^="https://"]').count()>=3
                await page.locator('#naClose').tap()
            await page.locator('#neuroNav').tap()
            await expect(page).to_have_url(base+'/mouse/')
            print('PASS new viewer interactions:',slug,flush=True)
        for width in [320,390,1440]:
            await page.set_viewport_size({'width':width,'height':900 if width>760 else 700})
            await page.goto(base+'/mouse/')
            for language in ['zh','en']:
                wanted='EN' if language=='zh' else '中文'
                if wanted not in await page.locator('#langToggle').inner_text():
                    await page.locator('#langToggle').click()
                for slug in SLUGS:
                    card=page.locator(f'[data-card="{slug}"]')
                    link=page.locator(f'.map-route[data-slug="{slug}"]')
                    assert (await card.locator('.card-index').inner_text()).strip()==(await link.locator('.map-number').inner_text()).strip()
                    assert await link.evaluate('''e => {const r=e.getBoundingClientRect();return [...e.children].every(c=>{const a=c.getBoundingClientRect();return a.left>=r.left&&a.right<=r.right})}'''),(slug,width,language)
                    await page.locator('#atlasSearch').fill(slug if language=='en' else (await card.locator('h3').inner_text()))
                    await expect(card).to_be_visible()
                    await page.locator('#atlasSearch').fill('')
            await page.locator('[data-filter="output"]').click()
            await expect(page.locator('[data-card="pain"]')).to_be_visible()
            await expect(page.locator('[data-card="autonomic"]')).to_be_visible()
            await expect(page.locator('[data-card="auditory"]')).to_be_hidden()
        assert not errors,errors
        print('PASS bilingual hub search, numbering, body filter and name bounds',flush=True)
        await browser.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site',type=Path,required=True)
    args=parser.parse_args()
    with ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(args.site.resolve()))) as server:
        thread=Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            asyncio.run(check(f'http://127.0.0.1:{server.server_port}'))
        finally:
            server.shutdown()
            thread.join()


if __name__=='__main__':
    main()
