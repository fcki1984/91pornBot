import asyncio
import datetime
import logging
import os
import platform
import random
import re
from urllib import parse

import aiohttp
import cv2
import jieba
# 分词
from tenacity import retry, stop_after_attempt, wait_fixed
from urllib.parse import urlparse, parse_qs
headers = None
jieba.setLogLevel(logging.ERROR)

ffmpe_root = 'ffmpeg'

if platform.system().lower() == 'windows':
    proxy = 'http://127.0.0.1:10809'
    proxies = {
        'https': proxy
    }
elif platform.system().lower() == 'linux':
    proxy = None
    proxies = None
    # for root, dirs, files in os.walk("/root/.cache/ms-playwright/", topdown=False):
    #     for name in files:
    #         if name == 'ffmpeg-linux':
    #             ffmpe_root = os.path.join(root, name)


# 读取停用词列表
def get_stopword_list(file):
    with open(file, 'r', encoding='utf-8') as f:  #
        stopword_list = [word.strip('\n') for word in f.readlines()]
    return stopword_list


async def seg(str):
    stopword_list = []
    try:
        jieba.load_userdict("/config/word.txt")
        jieba.load_userdict("/config/dict.txt")
        stopword_list = get_stopword_list('/config/hit_stopwords.txt')
    except:
        print('自定应词典不存在')
    str = str.replace(" ", "")
    seg_list = jieba.lcut(str, cut_all=False)
    res_list = []
    for w in seg_list:
        if w not in stopword_list:
            res_list.append('#' + w)
    return " ".join(res_list)


@retry(stop=stop_after_attempt(4), wait=wait_fixed(10))
async def imgCover(input, output):
    # ffmpeg -i 001.jpg -vf 'scale=320:320'  001_1.jpg
    print('截图入参:', input, output)
    command = '''%s -i  "%s" -y -loglevel quiet "%s" ''' % (
        ffmpe_root, input, output)
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{command!r} exited with {proc.returncode}]')


# 截取视频
async def segVideo(input, output, start='25', end=''):
    if end != '':
        command = '%s -ss %s -i "%s" -y -c:v copy -c:a copy -avoid_negative_ts 1 -t %s -loglevel quiet "%s" ' % (
            ffmpe_root,
            start, input, end, output)
    else:
        command = '%s -ss %s -i "%s" -y -c:v copy -c:a copy -avoid_negative_ts 1 -loglevel quiet  "%s" ' % (ffmpe_root,
                                                                                                            start,
                                                                                                            input,
                                                                                                            output)
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{command!r} exited with {proc.returncode}]')


def getVideoDuration(input):
    cap = cv2.VideoCapture(input)
    if cap.isOpened():
        rate = cap.get(5)
        frame_num = cap.get(7)
        duration = frame_num / rate
        return int(duration)
    return -1


# 检查字符串出现次数
def checkStrCount(str_source, str_check):  # str_source：源字符串；str_check：要检查字符
    splits = str_source.split(str_check)  # 返回拆分数组
    return len(splits) - 1  # 返回拆分次数-1


@retry(stop=stop_after_attempt(4), wait=wait_fixed(10))
async def imgCoverFromFile(input, output):
    # ffmpeg -i 001.jpg -vf 'scale=320:320'  001_1.jpg
    command = ''' %s -i "%s" -y -vframes 1   "%s" ''' % (
        ffmpe_root, input, output)
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{command!r} exited with {proc.returncode}]')


# asyncio.get_event_loop().run_until_complete( imgCoverFromFile('754744.jpg','out.png'))


async def genIpaddr():
    m = random.randint(0, 255)
    n = random.randint(0, 255)
    x = random.randint(0, 255)
    y = random.randint(0, 255)
    return str(m) + '.' + str(n) + '.' + str(x) + '.' + str(y)


# 下载任务
@retry(stop=stop_after_attempt(5), wait=wait_fixed(2))
async def run(session, url, viewkey, sem=asyncio.Semaphore(500)):
    async with sem:
        # 解析URL，获取路径部分
        parsed_url = urlparse(url)
        path = parsed_url.path

        if path.endswith('.mp4'):
            filename = viewkey + '.mp4'
        elif path.endswith('.jpg'):
            filename = re.search('([a-zA-Z0-9-_]+.jpg)', path)
            if filename:
                filename = filename.group(1).strip().removesuffix('.jpg') + '.ts'
            else:
                raise ValueError("URL does not match expected pattern for .jpg: " + url)
        elif path.endswith('.ts'):
            match = re.search('([a-zA-Z0-9-_]+.ts)', path)
            if match:
                filename = match.group(1).strip()
            else:
                raise ValueError("URL does not match expected pattern for .ts: " + url)
        else:
            raise ValueError("Unsupported file type in URL: " + url)

        async with session.get(url) as r:
            if r.status == 503:
                print('下载失败,抛出重试')
                raise RuntimeError('抛出重试')
            with open(viewkey + '/' + filename, "wb") as fp:
                while True:
                    chunk = await r.content.read(64 * 1024)
                    if not chunk:
                        break
                    fp.write(chunk)
                if path.endswith('.jpg'):
                    fp.seek(0x00)
                    fp.write(b'\xff\xff\xff\xff')
                print("\r", '任务文件 ', filename, ' 下载成功', end="", flush=True)



    # print("\r", '任务文件 ', filename, ' 下载成功', end="", flush=True)


# 读出ts列表，并写入文件列表到文件，方便后面合并视频
async def down(url, viewkey):
    async with aiohttp.request("GET", url) as r:
        m3u8_text = await r.text()
        if 'index.m3u8' in m3u8_text:
            # 请求真实地址
            hostName = parse.urlparse(url).hostname
            base_url = 'https://' + hostName
            lines = m3u8_text.split('\n')
            async with aiohttp.request("GET", base_url + lines[2]) as r:
                m3u8_text = await r.text()
        else:
            base_url = re.split(r"[a-zA-Z0-9-_\.]+\.m3u8", url)[0]

        lines = m3u8_text.split('\n')
        s = len(lines)
        ts_list = list()
        concatfile = viewkey + '/' + viewkey + '.txt'
        if not os.path.exists(viewkey):
            os.makedirs(viewkey)
        open(concatfile, 'w').close()
        t = open(concatfile, mode='a')
        for i, line in enumerate(lines):

            if ('hls/ts' in line):
                print('跳过')
                continue

            if '.ts' in line or '.jpg' in line:
                if '.jpg' in line:
                    ts_list.append(line)
                    filename = re.search('([a-zA-Z0-9-_]+.jpg)', line).group(1).strip()
                    filename = filename.removesuffix('.jpg')
                    filename = filename + '.ts'
                    t.write("file %s\n" % filename)
                    print("\r", '文件写入中', i, "/", s - 3, end="", flush=True)
                    continue
                if 'http' in line:
                    # print("ts>>", line)
                    ts_list.append(line)
                else:
                    line = base_url + line
                    ts_list.append(line)
                    # print('ts>>',line)
                filename = re.search('([a-zA-Z0-9-_]+.ts)', line).group(1).strip()
                t.write("file %s\n" % filename)
                print("\r", '文件写入中', i, "/", s - 3, end="", flush=True)
        t.close()
        # print(ts_list)
        return ts_list, concatfile


# 视频合并方法，使用ffmpeg
async def merge(concatfile, viewkey):
    try:
        path = f'{viewkey}/{viewkey}.mp4'
        command = '''%s -y -f concat -i "%s" -bsf:a aac_adtstoasc  -c copy   "%s"''' % (
            ffmpe_root, concatfile, path)
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        print(f'[{command!r} exited with {proc.returncode}]')
        print('视频合并完成')
    except:
        print('合并失败')


async def download91(url, viewkey, max=200):
    start = datetime.datetime.now().replace(microsecond=0)
    ts_list, concatfile = await down(url, viewkey)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tasks = []
    sem = asyncio.Semaphore(max)  # 控制并发数
    async with aiohttp.ClientSession() as session:
        for url in ts_list:
            task = asyncio.create_task(run(session, url, viewkey, sem))
            tasks.append(task)

        await asyncio.wait(tasks)
    await merge(concatfile, viewkey)
    end = datetime.datetime.now().replace(microsecond=0)
    print('写文件及下载耗时：' + str(end - start))
