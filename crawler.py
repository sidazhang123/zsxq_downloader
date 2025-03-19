import re
import requests
import json
import os
import pdfkit
import shutil
import datetime
import urllib.request
from bs4 import BeautifulSoup
from urllib.parse import quote
from urllib.parse import unquote
import base64
import time,sys
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
# 以下必须修改
ZSXQ_ACCESS_TOKEN = 'xxxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx_xxxxxxxxxxx'    # 登录后Cookie中的Token（必须修改）
GROUP_ID = 'xxxxxxxx'                         # 知识星球中的小组ID（必须修改）
EARLY_DATE = '2024-11-27T00:00:00.000+0800'       # 最早时间 当FROM_DATE_TO_DATE=True时生效 为空表示不限制 形如'2017-05-25T00:00:00.000+0800'
LATE_DATE = '2024-12-25T00:00:00.000+0800'        # 最晚时间 当FROM_DATE_TO_DATE=True时生效 为空表示不限制 形如'2017-05-25T00:00:00.000+0800'

#以下默认下载所有主题、评论、及包含的图片、文件下载链接
PDF_FILE_NAME = '电子书'                       # 生成PDF文件的名字
DOWLOAD_PICS = True                               # 是否下载图片 True | False 下载会导致程序变慢
DOWLOAD_COMMENTS = True                           # 是否下载评论
ONLY_DIGESTS = False                              # True-只精华 | False-全部
FROM_DATE_TO_DATE = True                         # 按时间区间下载
DELETE_PICS_WHEN_DONE = True                      # 运行完毕后是否删除下载的图片
DELETE_HTML_WHEN_DONE = True                      # 运行完毕后是否删除生成的HTML
COUNTS_PER_TIME = 30                              # 每次请求加载几个主题 最大可设置为30
SLEEP_FLAG = True                                 # 请求之间是否SLEEP避免请求过于频繁
SLEEP_SEC = 1                                    # SLEEP秒数 SLEEP_FLAG=True时生效
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'    # 登录时使用的User-Agent
TEMP_PATH='temp/'

html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
</head>
<body>
<h1>{title}</h1>
<br>{author} - {cretime}<br>
<p>{text}</p>
</body>
</html>
"""
htmls = []
num = 0

def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=5,  # number of retries
        backoff_factor=1,  # wait 1, 2, 4, 8, 16 seconds between retries
        status_forcelist=[500, 502, 503, 504]  # HTTP status codes to retry on
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def save_status(url, htmls, num):
    status = {
        'url': url,
        'htmls': htmls,
        'num': num,
        'timestamp': datetime.datetime.now().isoformat()
    }
    with open(TEMP_PATH+'crawl_status.json', 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False)

def load_status():
    if os.path.exists(TEMP_PATH+'crawl_status.json'):
        with open(TEMP_PATH+'crawl_status.json', 'r', encoding='utf-8') as f:
            status = json.load(f)
            # Check if status is not too old (e.g., less than 24 hours)
            saved_time = datetime.datetime.fromisoformat(status['timestamp'])
            if datetime.datetime.now() - saved_time < datetime.timedelta(hours=24):
                return status
    return None
def split_list(big_list, chunk_size=2000):
    """
    将大列表分割为多个小列表，每个小列表的最大长度由chunk_size指定。
    
    :param big_list: 需要分割的大列表。
    :param chunk_size: 每个小列表的最大长度，默认是2000。
    :return: 包含所有小列表的生成器。
    """
    for i in range(0, len(big_list), chunk_size):
        yield big_list[i:i + chunk_size]
def get_data(url):
    print(f'-processing- {url}')
    OVER_DATE_BREAK = False
    global htmls, num
    
    # Check for saved status
    status = load_status()
    if status and status['url'] == url:
        htmls = status['htmls']
        num = status['num']
        print(f"Resuming from saved status at post #{num}")
    
    headers = {
        'Cookie': 'zsxq_access_token=' + ZSXQ_ACCESS_TOKEN,
        'User-Agent': USER_AGENT
    }
    
    session = create_session()
    
    try:
        rsp=None
        for _ in range(5):
            rsp = session.get(url, headers=headers, timeout=30)
            if rsp.status_code==200 and 'topics' in rsp.text:
                break
            time.sleep(1)

        if 'topics' not in rsp.text:
            raise Exception("Invalid response: no topics found")
    except Exception as e:
        print(f"Unrecoverable error occurred: {e}")
        print("Saving current status for resume...")
        save_status(url, htmls, num)
        raise
    jc=rsp.json()
    for topic in jc.get('resp_data').get('topics'):
        try:
            images_index = 0
            if FROM_DATE_TO_DATE and EARLY_DATE.strip():
                if topic.get('create_time') < EARLY_DATE.strip():
                    OVER_DATE_BREAK = True
                    break

            content = topic.get('question', topic.get('talk', topic.get('task', topic.get('solution'))))

            anonymous = content.get('anonymous')
            if anonymous:
                author = '匿名用户'
            else:
                author = content.get('owner').get('name')

            cretime = (topic.get('create_time')[:23]).replace('T', ' ')

            text = content.get('text', '')
            text = handle_text(text)
            title = str(num) + '_' + cretime[:16]
            num += 1
            if topic.get('digested') == True:
                title += '_精华'

            if DOWLOAD_PICS and content.get('images'):
                soup = BeautifulSoup(html_template, 'html.parser')
                for img in content.get('images'):
                    url = img.get('large').get('url')
                    local_url = './images/' + str(num - 1) + '_' + str(images_index) + '.jpg'
                    images_index += 1
                    download_image(url, local_url)
                    #img_tag = soup.new_tag('img', src=local_url)
                    #直接写入路径可能无法正常将图片写入PDF，此处写入转码后的图片数据
                    img_tag = soup.new_tag('img', src=encode_image(local_url))
                    soup.body.append(img_tag)
                html_img = str(soup)
                html = html_img.format(title=title, text=text, author=author, cretime=cretime)
            else:
                html = html_template.format(title=title, text=text, author=author, cretime=cretime)

            if topic.get('question'):
                answer_author = topic.get('answer').get('owner').get('name', '')
                answer = topic.get('answer').get('text', "")
                answer = handle_text(answer)

                soup = BeautifulSoup(html, 'html.parser')
                answer_tag = soup.new_tag('p')

                answer = '【<b><font color=red>' + answer_author + '</font></b>】 回答：<br>' + answer
                soup_temp = BeautifulSoup(answer, 'html.parser')
                answer_tag.append(soup_temp)
                answer_tag.append(soup.new_tag('br'))
                if DOWLOAD_PICS and topic.get('answer').get('images'):
                    for img in topic.get('answer').get('images'):
                        url = img.get('large').get('url')
                        local_url = './images/' + str(num - 1) + '_' + str(images_index) + '.jpg'
                        images_index += 1
                        download_image(url, local_url)
                        #img_tag = soup.new_tag('img', src=local_url)
                        #直接写入路径可能无法正常将图片写入PDF，此处写入转码后的图片数据
                        img_tag = soup.new_tag('img', src=encode_image(local_url))
                        answer_tag.append(img_tag)
                        answer_tag.append(soup.new_tag('br'))
                soup.body.append(answer_tag)
                html = str(soup) 
        
            files = content.get('files')
            if files:
                files_content = '<i>文件列表(需访问网站下载) :<br>'
                for f in files:
                    files_content += f.get('name') + '<br>'
                files_content += '</i>'
                soup = BeautifulSoup(html, 'html.parser')
                files_tag = soup.new_tag('p')
                soup_temp = BeautifulSoup(files_content, 'html.parser')
                files_tag.append(soup_temp)
                soup.body.append(files_tag)
                html = str(soup)

            comments = topic.get('show_comments')
            if DOWLOAD_COMMENTS and comments:
                soup = BeautifulSoup(html, 'html.parser')
                hr_tag = soup.new_tag('hr')
                soup.body.append(hr_tag)
                for comment in comments:
                    comment_str = ''
                    if comment.get('repliee'):
                        replier=comment.get('owner').get('name')
                        rrr='<b><font color=red>郭博财经</font></b>' if replier=='郭博财经' else replier
                        comment_str = '[' + rrr + ' 回复 ' + comment.get('repliee').get('name') + '] : ' + handle_text(comment.get('text'))
                    else:
                        comment_str = '[' + comment.get('owner').get('name') + '] : ' + handle_text(comment.get('text'))

                    comment_tag = soup.new_tag('p')
                    soup_temp = BeautifulSoup(comment_str, 'html.parser')
                    comment_tag.append(soup_temp)
                    if DOWLOAD_PICS and comment.get('images'):
                        for img in comment.get('images'):
                            url = img.get('large').get('url')
                            local_url = './images/' + str(num - 1) + '_' + str(images_index) + '.jpg'
                            images_index += 1
                            download_image(url, local_url)
                            #img_tag = soup.new_tag('img', src=local_url)
                            #直接写入路径可能无法正常将图片写入PDF，此处写入转码后的图片数据
                            img_tag = soup.new_tag('img', src=encode_image(local_url))
                            comment_tag.append(img_tag)
                            comment_tag.append(soup.new_tag('br'))
                    soup.body.append(comment_tag)
                html = str(soup)

            htmls.append(html)

        except Exception as e:
            print(f"Error processing topic: {e}")
            print("Saving current status for resume...")
            save_status(url, htmls, num)
            raise


    if OVER_DATE_BREAK:
        return htmls

    next_page = rsp.json().get('resp_data').get('topics')
  
    if next_page:
        try:
            create_time = next_page[-1].get('create_time')
            if create_time[20:23] == "000":
                end_time = create_time[:20]+"999"+create_time[23:]
                str_date_time = end_time[:19]
                delta = datetime.timedelta(seconds=1)
                date_time = datetime.datetime.strptime(str_date_time, '%Y-%m-%dT%H:%M:%S')
                date_time = date_time - delta
                str_date_time = date_time.strftime('%Y-%m-%dT%H:%M:%S')
                end_time = str_date_time + end_time[19:]
            else:
                res = int(create_time[20:23])-1
                end_time = create_time[:20]+str(res).zfill(3)+create_time[23:]
            end_time = quote(end_time)
            if len(end_time) == 33:
                end_time = end_time[:24] + '0' + end_time[24:]
            next_url = start_url + '&end_time=' + end_time
            if SLEEP_FLAG:
                time.sleep(SLEEP_SEC)
            get_data(next_url)
        except Exception as e:
            print(f"Error processing next page: {e}")
            print("Saving current status for resume...")
            save_status(url, htmls, num)
            raise

    return htmls

def encode_image(image_url):
    with open(image_url, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read())
    return 'data:image/png;base64,' + encoded_string.decode('utf-8')

def download_image(url, local_url):
    for _ in range(5):
        try:
            urllib.request.urlretrieve(url, local_url)
            return
        except:
            time.sleep(1)

def handle_text(text):
    soup = BeautifulSoup(text, "html.parser")

    mention = soup.find_all('e', attrs={'type' : 'mention'})
    if len(mention):
        for m in mention:
            mention_name = m.attrs['title']
            new_tag = soup.new_tag('span')
            new_tag.string = mention_name
            m.replace_with(new_tag)

    hashtag = soup.find_all('e', attrs={'type' : 'hashtag'})
    if len(hashtag):
        for tag in hashtag:
            tag_name = unquote(tag.attrs['title'])
            new_tag = soup.new_tag('span')
            new_tag.string = tag_name
            tag.replace_with(new_tag)

    links = soup.find_all('e', attrs={'type' : 'web'})
    if len(links):
        for link in links:
            title = unquote(link.attrs['title'])
            href = unquote(link.attrs['href'])
            new_a_tag = soup.new_tag('a', href=href)
            new_a_tag.string = title
            link.replace_with(new_a_tag)

    text = str(soup)
    text = re.sub(r'<e[^>]*>', '', text).strip()
    text = text.replace('\n', '<br>')
    return text

def make_pdf(htmls,create_file=False):
    print(f'-making- {PDF_FILE_NAME}')
    import pickle
    if create_file:
        with open(TEMP_PATH+'htmls.pkl','wb')as f:
            pickle.dump(htmls,f)
    html_files = []
    for index, html in enumerate(htmls):
        file = TEMP_PATH+str(index) + ".html"
        html_files.append(file)
        with open(file, "w", encoding="utf-8") as f:
            f.write(html)

    options = {
        "user-style-sheet": "pdf_style.css",
        "page-size": "Letter",
        "margin-top": "0.75in",
        "margin-right": "0.75in",
        "margin-bottom": "0.75in",
        "margin-left": "0.75in",
        "encoding": "UTF-8",
        "custom-header": [("Accept-Encoding", "gzip")],
        "cookie": [
            ("cookie-name1", "cookie-value1"), ("cookie-name2", "cookie-value2")
        ],
        "outline-depth": 10,
    }

    pdf_error_flag = False
    chunked_lists = list(split_list(html_files, 2000))
    for idx, less_html_files in enumerate(chunked_lists):
    
        pdfkit.from_file(less_html_files, f'{PDF_FILE_NAME}{idx}.pdf', options=options)


    if DELETE_HTML_WHEN_DONE:
        for file in html_files:
            os.remove(file)

    if not pdf_error_flag:
        print("电子书生成成功！")

if __name__ == '__main__':
    import pickle,os,warnings
    warnings.filterwarnings('ignore')
    
    if os.path.exists(TEMP_PATH+'htmls.pkl'):
        with open(TEMP_PATH+'htmls.pkl','rb')as f:
            htmls=pickle.load(f)
            make_pdf(htmls,False)
    
    images_path = r'./images'
    if DOWLOAD_PICS:
        if os.path.exists(images_path):
            shutil.rmtree(images_path)
        os.mkdir(images_path)
    if TEMP_PATH and not os.path.exists(TEMP_PATH):
        os.mkdir(TEMP_PATH)

    start_url = ''
    if ONLY_DIGESTS:
        start_url = 'https://api.zsxq.com/v2/groups/' + GROUP_ID + '/topics?scope=digests&count=' + str(COUNTS_PER_TIME)
    else:
        start_url = 'https://api.zsxq.com/v2/groups/' + GROUP_ID + '/topics?count=' + str(COUNTS_PER_TIME)

    url = start_url
    if FROM_DATE_TO_DATE and LATE_DATE.strip():
        url = start_url + '&end_time=' + quote(LATE_DATE.strip())

    
    try:
        gd = get_data(url)
        make_pdf(gd,True)
        # Clean up status file only after successful completion
        if os.path.exists(TEMP_PATH+'crawl_status.json'):
            os.remove(TEMP_PATH+'crawl_status.json')
    except Exception as e:
        print(f"An unrecoverable error occurred: {e}")
        print("Status has been saved. You can resume the crawl by running the script again.")
        sys.exit(1)

    if DOWLOAD_PICS and DELETE_PICS_WHEN_DONE:
        shutil.rmtree(images_path) 
