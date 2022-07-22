import asyncio
import re
from urllib import parse
from urllib.parse import unquote

import aiohttp
from faker import Faker
from pyppeteer import launch
from tenacity import retry, stop_after_attempt, wait_fixed

fake = Faker('zh_CN')
import util


class VideoInfo(object):
    pass


@retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
async def getVideoInfo91(url):
    try:
        browser, page = await ini_browser()
        await asyncio.wait_for(page.goto(url, {'waitUntil': 'networkidle0'}), timeout=10.0)
        await page._client.send("Page.stopLoading")

        await page.waitForSelector('.video-border')
        # 执行JS代码
        # evaluate页面跳转后 已经注入的JS代码会失效
        # evaluateOnNewDocument每次打开新页面注入
        strencode = await page.evaluate('''() => {
               return $(".video-border").html().match(/document.write([\s\S]*?);/)[1];
            }''')

        realM3u8 = await page.evaluate(" () => {return " + strencode + ".match(/src='([\s\S]*?)'/)[1];}")

        imgUrl = await page.evaluate('''() => {
               return $(".video-border").html().match(/poster="([\s\S]*?)"/)[1]
            }''')
        scCount = await page.Jeval('#useraction > div:nth-child(1) > span:nth-child(4) > span', 'el => el.innerText')
        title = await page.Jeval('#videodetails > h4', 'el => el.innerText')
        author = await page.Jeval('#videodetails-content > div:nth-child(2) > span.title-yakov > a:nth-child(1) > span',
                                  'el => el.innerText')

        # 判断是否高清
        length = await page.evaluate('''() => {
               return $("#videodetails-content > a:nth-child(2)").length
            }''')
        if int(length) > 0:
            if '.mp4' in realM3u8:
                # realM3u8 = realM3u8.replace('/mp43', '/mp4hd')
                pass
            else:
                realM3u8 = realM3u8.replace('/m3u8', '/m3u8hd')

    finally:
        # 关闭浏览器
        await page.close()
        await browser.close()

    videoinfo = VideoInfo()
    videoinfo.title = title
    videoinfo.author = author
    videoinfo.scCount = scCount
    videoinfo.realM3u8 = realM3u8
    videoinfo.imgUrl = imgUrl
    print(title)
    print(realM3u8)
    return videoinfo


async def ini_browser():
    browser = await launch(headless=True, dumpio=True, devtools=False,
                           # userDataDir=r'F:\temporary',
                           args=[
                               # 关闭受控制提示：比如，Chrome正在受到自动测试软件的控制...
                               '--disable-infobars',
                               # 取消沙盒模式，沙盒模式下权限太小
                               '--no-sandbox',
                               '--ignore-certificate-errors',
                               '--disable-setuid-sandbox',
                               '--disable-features=TranslateUI',
                               '-–disable-gpu',
                               '--disable-software-rasterizer',
                               '--disable-dev-shm-usage',
                               # log 等级设置，如果出现一大堆warning，可以不使用默认的日志等级
                               '--log-level=4',
                           ])
    page = await browser.newPage()
    await page.setUserAgent(fake.user_agent())
    await page.setExtraHTTPHeaders(
        headers={'X-Forwarded-For': await util.genIpaddr(), 'Accept-Language': 'zh-cn,zh;q=0.5'})
    await page.evaluateOnNewDocument('() =>{ Object.defineProperties(navigator,'
                                     '{ webdriver:{ get: () => false } }) }')
    return browser, page


# 首页列表爬取
async def page91Index():
    try:
        browser, page = await ini_browser()
        await asyncio.wait_for(page.goto('https://91porn.com/index.php', {'waitUntil': 'domcontentloaded'}),
                               timeout=30.0)
        # await page._client.send("Page.stopLoading")
        await page.waitForSelector('#wrapper > div.container.container-minheight > div.row > div > div > a')
        urls = await page.querySelectorAllEval(
            '#wrapper > div.container.container-minheight > div.row > div > div > div > div > a',
            'nodes => nodes.map(node => node.href)')
        # 首页标题
        titles = await page.querySelectorAllEval(
            '#wrapper > div.container.container-minheight > div.row > div > div > div > div > a > span',
            'nodes => nodes.map(node => node.innerText)')
        # 首页作者
        content_ = await page.content()
        authors = re.findall('作者:</span>([\d\D]*?)<br>', content_)
        scCounts = re.findall('收藏:</span>([\d\D]*?)<br>', content_)
        print(titles)

    finally:
        await page.close()
        await browser.close()
    return urls, titles, authors, scCounts



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


async def get91Home():
    """
        获取91免翻墙地址
    :return:
    """
    async with aiohttp.ClientSession() as session:
        async with session.get('https://www.ebay.com/usr/91home') as r:
            return re.findall(r'<h2 class="bio inline_value">\s\s\s\s(.*?)\s\s', await r.text())[0]


async def getMaDou(url):
    async with aiohttp.request("GET",url ,
                               # proxy='http://127.0.0.1:10809',
                               ) as r:
        text = await r.text()
        # print(text)
        urls = re.findall('"url":"(.*?)","u', text)
        title = re.findall('<title>(.*?)</title>', text)[0]
        title=title.split(' - ')[0]
        m3u8 = urls[0].replace('\\', '')
        return m3u8,title


