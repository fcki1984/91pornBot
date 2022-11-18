import asyncio
import datetime
import json
import random
import re
from urllib.parse import unquote

import aiohttp
from playwright._impl._api_types import Error, TimeoutError
from playwright.async_api import async_playwright

import util

browser = None
p = None


# 只初始化浏览器上下文，避免创建多个浏览器实例
async def init_browser(is_pc=True):
    global browser
    global p
    if browser is None:
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=True)
    if is_pc:
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )
    else:
        iphone_12 = p.devices['iPhone 12']
        context = await browser.new_context(
            **iphone_12,
            locale='zh-CN',
        )
    await context.set_extra_http_headers(
        {
            'X-Forwarded-For': await genIpaddr(),
            'Accept-Language': 'zh-cn,zh;q=0.5',
        }
    )
    page = await context.new_page()
    await context.route(re.compile(r"(\.png$)|(\.jpg$)"), lambda route: route.abort())
    js = """
                    Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});
                    """
    await page.add_init_script(js)
    return context, page


class VideoInfo(object):
    pass



async def getVideoInfo91(url):
    videoinfo = VideoInfo()
    err_msg = None
    try:
        context, page = await init_browser(is_pc=False)
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_selector('.video-border')
        except TimeoutError:
            print('超时了。。。。')
            err_msg = '页面加载超时'
            return videoinfo, err_msg

        str_encode = await page.evaluate('''() => {
               return $(".video-border").html().match(/document.write([\s\S]*?);/)[1];
            }''')

        real_m3u8 = await page.evaluate(" () => {return " + str_encode + ".match(/src='([\s\S]*?)'/)[1];}")
        sc_count = await page.eval_on_selector('#useraction > div:nth-child(1) > span:nth-child(4) > span',
                                               'el => el.innerText')
        title = await page.eval_on_selector('#videodetails > h4', 'el => el.innerText')

        try:
            author = await page.eval_on_selector(
                '#videodetails-content > div:nth-child(2) > span.title-yakov > a:nth-child(1) > span',
                'el => el.innerText')
        except Error:
            author = '匿名'

        # 判断是否高清
        length = await page.evaluate('''() => {
               return $("#videodetails-content > img").length
            }''')
        if int(length) > 0:
            if '.mp4' in real_m3u8:
                # realM3u8 = realM3u8.replace('/mp43', '/mp4hd')
                pass
            else:
                real_m3u8 = real_m3u8.replace('/m3u8', '/m3u8hd')

        print(title, real_m3u8, sc_count, author)
        videoinfo = VideoInfo()
        videoinfo.title = title
        videoinfo.author = author
        videoinfo.scCount = sc_count
        videoinfo.realM3u8 = real_m3u8
        return videoinfo, err_msg
    finally:
        await context.close()


async def getMaDou(url):
    async with aiohttp.request("GET", url,
                               # proxy='http://127.0.0.1:7890',
                               ) as r:
        text = await r.text()

        urls = re.findall('"url":"(.*?)","u', text)
        title = re.findall('<title>(.*?)</title>', text)[0]
        title = title.split(' - ')[0]
        m3u8 = urls[0].replace('\\', '')
        m3u8 = unquote(m3u8, 'utf-8')
        return m3u8, title


async def getHs(url):
    async with aiohttp.request("GET", url,
                               # proxy='http://127.0.0.1:10809',
                               ) as r:
        text = await r.text()
        urls = re.findall('<source src="(.*?)"', text)
        titles = re.findall(r'<h3 class="panel-title">(.*?)<', text)
        authors = re.findall(r'作者：<a href="user.htm\?author=(.*?)">', text)
        imgs = re.findall(r'property="og:image" content="(.*?)"', text)
        videoinfo = VideoInfo()
        videoinfo.title = titles[0]
        videoinfo.author = unquote(authors[0])
        videoinfo.realM3u8 = urls[0]
        videoinfo.imgUrl = imgs[0]
        print(videoinfo.realM3u8)
        return videoinfo


async def page91Index():
    context, page = await init_browser(is_pc=False)
    try:
        await page.goto('https://91porn.com/index.php', wait_until="domcontentloaded")
        await page.wait_for_selector('#wrapper > div.container.container-minheight > div.row > div > div > a')
        urls = await page.eval_on_selector_all(
            '#wrapper > div.container.container-minheight > div.row > div > div > div > div > a',
            'nodes => nodes.map(node => node.href)')
        # 首页标题
        titles = await page.eval_on_selector_all(
            '#wrapper > div.container.container-minheight > div.row > div > div > div > div > a > span',
            'nodes => nodes.map(node => node.innerText)')

        content_ = await page.content()
        authors = re.findall('作者:</span>([\d\D]*?)<br>', content_)
        scCounts = re.findall('收藏:</span>([\d\D]*?)<br>', content_)
        print(titles)
        return urls, titles, authors, scCounts
    finally:
        await context.close()



async def genIpaddr():
    m = random.randint(0, 255)
    n = random.randint(0, 255)
    x = random.randint(0, 255)
    y = random.randint(0, 255)
    return str(m) + '.' + str(n) + '.' + str(x) + '.' + str(y)


async def get91Home():
    """
        获取91免翻墙地址
    :return:
    """
    async with aiohttp.ClientSession() as session:
        async with session.get('https://www.ebay.com/usr/91home') as r:
            return re.findall(r'regular-text">(.*?)</span>', await r.text())[0]
