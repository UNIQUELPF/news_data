import scrapy
from scrapy_playwright.page import PageMethod
from news_scraper.items import NewsHeadlineItem
from datetime import datetime
from bs4 import BeautifulSoup
import psycopg2
import re
from news_scraper.utils import get_dynamic_cutoff

class NewsCNSpider(scrapy.Spider):
    name = 'news_cn'
    allowed_domains = ['news.cn']
    
    # 定义频道及其对应的起始URL和选择器配置
    CHANNELS = {
        'finance': {
            'url': 'https://www.news.cn/fortune/index.htm',
            'list_selector': '#recommendDepth .xpage-content-list',
            'item_selector': '.column-center-item',
            'wait_selector': '#recommendDepth',
            'table': 'news_finance'
        },
        'money': {
            'url': 'https://www.news.cn/money/index.html',
            'list_selector': 'ul.infoList',
            'item_selector': 'li',
            'wait_selector': 'ul.infoList',
            'table': 'news_money'
        },
        'silkroad': {
            'urls': {
                '丝路聚焦': 'https://www.news.cn/silkroad/jj/index.html',
                '丝路议程': 'https://www.news.cn/silkroad/slyc/index.html',
                '丝路客观': 'https://www.news.cn/silkroad/slgc/index.html',
                '丝路商机': 'https://www.news.cn/silkroad/slsj/index.html',
                '丝路人文': 'https://www.news.cn/silkroad/slrw/index.html',
            },
            'list_selector': 'ul#autoData',
            'item_selector': 'li',
            'wait_selector': 'ul#autoData',
            'table': 'news_silkroad'
        }
    }

    custom_settings = {
        'CONCURRENT_REQUESTS_PER_DOMAIN': 3,
        'DOWNLOAD_DELAY': 1,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
    }

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(NewsCNSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider.channel_cutoffs = {}
        for channel, config in spider.CHANNELS.items():
            cutoff = get_dynamic_cutoff(crawler.settings, config['table'], is_string_format=True)
            if channel == 'silkroad' and cutoff == "20251231":
                # Special early cutoff for silkroad's first run
                spider.channel_cutoffs[channel] = "20251120"
            else:
                spider.channel_cutoffs[channel] = cutoff
        return spider

    def __init__(self, *args, **kwargs):
        super(NewsCNSpider, self).__init__(*args, **kwargs)

    def check_url_exists(self, url, channel):
        table = self.CHANNELS[channel]['table']
        db_settings = self.settings.get('POSTGRES_SETTINGS')
        try:
            conn = psycopg2.connect(**db_settings)
            cur = conn.cursor()
            cur.execute(f"SELECT 1 FROM {table} WHERE url = %s", (url,))
            exists = cur.fetchone() is not None
            cur.close()
            conn.close()
            return exists
        except Exception as e:
            self.logger.error(f"Failed to check URL existence for {channel}: {e}")
            return False

    def start_requests(self):
        for channel, config in self.CHANNELS.items():
            cutoff_date_str = self.channel_cutoffs[channel]
            is_first_run = (cutoff_date_str < datetime.now().strftime("%Y%m%d"))
            
            urls = [config['url']] if 'url' in config else []
            if 'urls' in config:
                urls = [(u, m) for m, u in config['urls'].items()]
            else:
                urls = [(u, None) for u in urls]

            for url_info in urls:
                url, module_name = url_info
                
                cutoff_date = self.channel_cutoffs[channel]
                is_first_run = (cutoff_date < datetime.now().strftime("%Y%m%d"))
                
                js_script = f"""
                async () => {{
                    let attempts = 0;
                    let stopSignalCount = 0;
                    while (attempts < 60) {{
                        window.scrollTo(0, document.body.scrollHeight);
                        await new Promise(r => setTimeout(r, 1500));
                        
                        const links = Array.from(document.querySelectorAll('a[href*="/2025"], a[href*="/2024"]'));
                        // 对于丝路频道，检查是否包含早于截止日期的内容
                        if (links.length > 0) {{
                            const earlyLinks = links.filter(l => {{
                                const m = l.href.match(/\\/(\\d{{8}})\\//);
                                return m && m[1] < "{cutoff_date}";
                            }});
                            // 如果发现旧内容，不立刻停止，而是计数。只有连续多次或大量发现才停止。
                            if (earlyLinks.length > 5) {{
                                stopSignalCount++;
                            }}
                            if (stopSignalCount >= 3) {{
                                console.log("Detected substantial early content over multiple scrolls, stopping.");
                                break;
                            }}
                        }}

                        const loadMore = document.querySelector('.xpage-more-btn.look') || 
                                         document.querySelector('.xpage-more-btn') || 
                                         document.querySelector('#loadMore') || 
                                         document.querySelector('#moreBtn') || 
                                         document.querySelector('.more');
                        if (loadMore && loadMore.offsetParent !== null) {{
                            loadMore.click();
                            await new Promise(r => setTimeout(r, 2000));
                        }} else {{
                            break;
                        }}
                        attempts++;
                    }}
                }}
                """ if is_first_run else ""

                yield scrapy.Request(
                    url,
                    meta={
                        "playwright": True,
                        "playwright_page_methods": [
                            PageMethod("wait_for_selector", config['wait_selector']),
                            PageMethod("evaluate", js_script) if js_script else PageMethod("wait_for_timeout", 1000),
                        ],
                        "channel": channel,
                        "module": module_name
                    },
                    callback=self.parse,
                    dont_filter=True
                )

    def parse(self, response):
        channel = response.meta['channel']
        config = self.CHANNELS[channel]
        soup = BeautifulSoup(response.text, 'html.parser')
        today_str = datetime.now().strftime("%Y%m%d")
        
        container = soup.select_one(config['list_selector'])
        if not container:
            self.logger.warning(f"Container {config['list_selector']} not found for channel {channel}")
            return

        items = container.select(config['item_selector'])
        self.logger.info(f"Found {len(items)} potential items in News {channel.capitalize()}")

        for item in items:
            link_tag = item.select_one('.tit a') or item.select_one('a')
            if link_tag:
                url = response.urljoin(link_tag.get('href'))
                title = link_tag.get_text(strip=True)
                
                # 丝路频道黑名单过滤
                if channel == 'silkroad':
                    if any(bad in title for bad in ["高清大图"]):
                        continue
                    if "index.html" in url:
                        continue
                
                if not url.endswith('.html') and not url.endswith('.htm'):
                    continue

                m = re.search(r'/(\d{8})/', url)
                item_date_str = m.group(1) if m else None
                
                cutoff_date = self.channel_cutoffs[channel]
                
                should_crawl = False
                if item_date_str and int(item_date_str) >= int(cutoff_date):
                    should_crawl = True
                
                if should_crawl:
                    if self.check_url_exists(url, channel):
                        self.logger.info(f"URL already in DB ({channel}), skipping: {url}")
                        continue
                        
                    yield scrapy.Request(
                        url,
                        callback=self.parse_detail,
                        meta={
                            'title': title, 
                            'item_date_str': item_date_str, 
                            'channel': channel,
                            'module': response.meta.get('module')
                        }
                    )

    def parse_detail(self, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        title = response.meta.get('title')
        item_date_str = response.meta.get('item_date_str')
        channel = response.meta.get('channel')
        
        publish_time_str = ""
        time_tag = soup.select_one('.header-time, .time, #pubtime, .date')
        if time_tag:
            raw_time = time_tag.get_text(strip=True)
            m = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{1,2}(:\d{1,2})?)', raw_time)
            if m:
                try:
                    dt_str = m.group(1).replace('/', '-')
                    if dt_str.count(':') == 1:
                        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                    else:
                        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    publish_time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
        
        if not publish_time_str and item_date_str:
            publish_time_str = f"{item_date_str[:4]}-{item_date_str[4:6]}-{item_date_str[6:]} 00:00:00"

        content_node = soup.find(id="detailContent") or soup.find(id="detail") or soup.select_one(".main-content")
        content_text = ""
        if content_node:
            # 丝路频道特殊清洗：只取 P 标签，剔除 SPAN (作者/来源信息)
            if channel == 'silkroad':
                # 剔除脚本和视频块
                for s in content_node.find_all(['script', 'style']):
                    s.decompose()
                if content_node.find(id="DH-PLAYERID0"):
                    content_node.find(id="DH-PLAYERID0").decompose()

                # 移除嵌套的 span (包含来源信息/图片说明)
                for span in content_node.find_all('span'):
                    span.decompose()
                
                p_tags = content_node.find_all('p')
                cleaned_lines = []
                for p in p_tags:
                    txt = p.get_text(strip=True).replace('\xa0', ' ').replace('\u2003', '')
                    if not txt: continue
                    
                    # 剔除噪声
                    if any(noise in txt for noise in ["责任编辑", "点击下载", "相关推荐", "微信扫描", "延伸阅读", "javascript:void(0)"]):
                        continue
                    
                    # 剔除仅包含记者名单的段落
                    if re.match(r'^新华社记者.*', txt) or re.match(r'^（记者.*）$', txt):
                        continue
                        
                    # 剔除开头的地方性前缀，如 "新华社开罗1月22日电"
                    txt = re.sub(r'^新华社[\u4e00-\u9fa5]+[0-9]+月[0-9]+日电\s*', '', txt)
                    txt = re.sub(r'^新华社北京[0-9]+月[0-9]+日电\s*', '', txt)
                    
                    if txt:
                        cleaned_lines.append(txt)
                content_text = "\n\n".join(cleaned_lines)
            else:
                content_text = content_node.get_text(separator='\n', strip=True)
                
                lines = content_text.split('\n')
                cleaned_lines = []
                for line in lines:
                    txt = line.strip()
                    if not txt: continue
                    if any(noise in txt for noise in ["责任编辑", "点击下载", "相关推荐", "微信扫描", "延伸阅读", "javascript:void(0)"]):
                        continue
                    cleaned_lines.append(txt)
                content_text = "\n".join(cleaned_lines)
        
        if not content_text:
            self.logger.error(f"Failed to extract content for {channel}: {response.url}")

        item = NewsHeadlineItem()
        item['type'] = 'news_headline'
        item['title'] = title
        item['url'] = response.url
        item['publish_time'] = publish_time_str
        item['publish_date'] = f"{publish_time_str[:10]}" if publish_time_str else None
        item['content'] = content_text
        item['channel'] = channel
        item['module'] = response.meta.get('module')
        item['crawl_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        yield item
