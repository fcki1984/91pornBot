import asyncio
import datetime
import logging
import os
import random
import re
import shutil
from urllib import parse
import cv2
import aiohttp
import ffmpy3
import jieba

# 分词
from tenacity import retry, stop_after_attempt, wait_fixed

headers = None
jieba.setLogLevel(logging.ERROR)


async def seg(str):
    try:
        jieba.load_userdict("/config/word.txt")
        jieba.set_dictionary("/config/dict.txt")
    except:
        print('自定应词典不存在')
    seg_list = jieba.cut(str, cut_all=False)
    return '#' + " #".join(seg_list)


@retry(stop=stop_after_attempt(4), wait=wait_fixed(10))
async def imgCover(input, output):
    # ffmpeg -i 001.jpg -vf 'scale=320:320'  001_1.jpg
    ff = ffmpy3.FFmpeg(
        inputs={input: None},
        outputs={output: ['-y', '-loglevel', 'quiet']}
    )
    await ff.run_async()
    await ff.wait()


# 截取视频
async def segVideo(input, output, start='25', end=''):
    quiet_ = ['-y', '-c:v', 'copy', '-c:a', 'copy', '-avoid_negative_ts', '1',
              '-loglevel', 'quiet'
              ]
    if end != '':
        quiet_.append('-t')
        quiet_.append(end)
    ff = ffmpy3.FFmpeg(
        inputs={input: ['-ss', start]},
        outputs={output: quiet_}
    )
    print(ff.cmd)
    await ff.run_async()
    await ff.wait()


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
    ff = ffmpy3.FFmpeg(
        inputs={input: None},
        outputs={output: ['-y', '-vframes', '1', '-loglevel', 'quiet']}
    )
    await ff.run_async()
    await ff.wait()


@retry(stop=stop_after_attempt(4), wait=wait_fixed(10))
async def m3u8ToMp4(input, output):
    #  ffmpeg  -i "http://xxxxxx/video/movie.m3u8" -vcodec copy -acodec copy -absf aac_adtstoasc  output.mp4
    ff = ffmpy3.FFmpeg(
        inputs={input: None},
        outputs={output: ['-y', '-c', 'copy', ]}
    )
    await ff.run_async()
    await ff.wait()



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
        if url.endswith('.mp4'):
            filename = viewkey + '.mp4'
        elif url.endswith('.jpg'):
            filename = re.search('([a-zA-Z0-9-_]+.jpg)', url).group(1).strip()
            filename = filename.removesuffix('.jpg')
            filename = filename + '.ts'
        else:
            filename = re.search('([a-zA-Z0-9-_]+.ts)', url).group(1).strip()

        async with session.get(url) as r:
            # print('下载：',url)
            if (r.status == 503):
                print('下载失败,抛出重试')
                raise RuntimeError('抛出重试')
            with open(viewkey + '/' + filename, "wb") as fp:
                while True:
                    chunk = await r.content.read(64 * 1024)
                    if not chunk:
                        break
                    fp.write(chunk)
                if url.endswith('.jpg'):
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
def merge(concatfile, viewkey):
    try:
        path = viewkey + '/' + viewkey + '.mp4'
        command = '''ffmpeg -y -f concat -i %s -bsf:a aac_adtstoasc -loglevel quiet -c copy  %s''' % (concatfile, path)
        os.system(command)
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
    merge(concatfile, viewkey)
    end = datetime.datetime.now().replace(microsecond=0)
    print('写文件及下载耗时：' + str(end - start))
